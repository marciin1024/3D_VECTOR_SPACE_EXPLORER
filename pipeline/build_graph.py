"""build_graph.py — raw corpus -> web/data/graph_data.json, one command, deterministic.

Stages: load_corpus() -> embed() -> reduce_3d() -> cluster() -> build_edges()
        -> build_structural_edges() -> export_json()

Each stage caches to pipeline/cache/ (keyed by a corpus hash where relevant),
so later stages can be iterated on without recomputing earlier ones.

Usage:
    python build_graph.py               # use caches when valid
    python build_graph.py --recompute   # ignore caches, rebuild everything
"""
import argparse
import hashlib
import json
import os
import pickle
import sys

import numpy as np

import config as C
from redact import redact, display_title

CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")
SCREENSHOTS = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "..", "report", "screenshots")
os.makedirs(CACHE, exist_ok=True)
os.makedirs(SCREENSHOTS, exist_ok=True)


# --------------------------------------------------------------------------- #
# 1.1  Corpus acquisition and cleaning (20 Newsgroups)
# --------------------------------------------------------------------------- #
def load_corpus(recompute: bool = False) -> list[dict]:
    path = os.path.join(CACHE, "corpus.pkl")
    if os.path.exists(path) and not recompute:
        with open(path, "rb") as f:
            docs = pickle.load(f)
        print(f"[1.1] cache hit: {len(docs)} documents from corpus.pkl")
        return docs

    from sklearn.datasets import fetch_20newsgroups

    print("[1.1] fetching 20 Newsgroups (noise removed)...")
    raw = fetch_20newsgroups(
        subset="all",
        categories=C.CATEGORIES,
        remove=("headers", "footers", "quotes"),   # critical: see Pitfalls 1.1
    )

    rng = np.random.RandomState(C.SEED)
    by_cat: dict[str, list[str]] = {c: [] for c in C.CATEGORIES}
    seen: set[str] = set()

    for text, label in zip(raw.data, raw.target):
        cat = raw.target_names[label]
        t = text.strip()
        # filter AFTER remove (some docs are empty post-cleaning)
        if not (C.MIN_CHARS <= len(t) <= C.MAX_CHARS):
            continue
        norm = " ".join(t.lower().split())          # dedupe on normalized text
        if norm in seen:
            continue
        seen.add(norm)
        by_cat[cat].append(t)

    docs: list[dict] = []
    for cat in C.CATEGORIES:
        pool = by_cat[cat]
        if len(pool) < C.DOCS_PER_CATEGORY:
            print(f"  WARNING: {cat} has only {len(pool)} usable docs")
        idx = rng.choice(len(pool), size=min(C.DOCS_PER_CATEGORY, len(pool)),
                         replace=False)
        for i in sorted(idx):
            text = pool[i]
            first_line = next((ln.strip() for ln in text.splitlines()
                               if ln.strip()), "untitled")
            docs.append({
                "id": len(docs),
                "title": first_line[:C.TITLE_MAX_CHARS],
                "category": cat,
                "text": text,
                "n_tokens": len(text.split()),
            })

    with open(path, "wb") as f:
        pickle.dump(docs, f)

    # statistics
    print(f"[1.1] corpus.pkl: {len(docs)} documents")
    for cat in C.CATEGORIES:
        sub = [d for d in docs if d["category"] == cat]
        mean_len = np.mean([len(d["text"]) for d in sub])
        print(f"       {cat:28s} n={len(sub):3d}  mean_chars={mean_len:7.1f}")
    return docs


def corpus_hash(docs: list[dict]) -> str:
    """Cache key: hash of sorted document ids + titles (stale-cache guard)."""
    payload = "|".join(f"{d['id']}:{d['title']}" for d in
                       sorted(docs, key=lambda d: d["id"]))
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]


# --------------------------------------------------------------------------- #
# 1.2  Vectorization with caching
# --------------------------------------------------------------------------- #
def embed(docs: list[dict], h: str, recompute: bool = False) -> np.ndarray:
    path = os.path.join(CACHE, f"embeddings_{h}.npy")
    if os.path.exists(path) and not recompute:
        E = np.load(path)
        print(f"[1.2] cache hit: embeddings {E.shape}")
    else:
        from sentence_transformers import SentenceTransformer
        print(f"[1.2] embedding {len(docs)} docs with {C.EMBEDDING_MODEL}...")
        model = SentenceTransformer(C.EMBEDDING_MODEL)
        E = model.encode(
            [d["text"] for d in docs],
            batch_size=C.EMBED_BATCH_SIZE,
            normalize_embeddings=True,   # cosine == dot product downstream
            show_progress_bar=True,
        )
        np.save(path, E)

    # sanity checks
    assert E.shape == (len(docs), 384), f"bad shape {E.shape}"
    assert np.allclose(np.linalg.norm(E, axis=1), 1.0, atol=1e-3), \
        "embeddings are not normalized!"
    print(f"[1.2] shape {E.shape} OK, norms ~1.0 OK")
    return E


# --------------------------------------------------------------------------- #
# 1.3  UMAP projection to 3D (+ 2D control preview)
# --------------------------------------------------------------------------- #
def reduce_3d(E: np.ndarray, docs: list[dict], h: str,
              recompute: bool = False) -> np.ndarray:
    path = os.path.join(CACHE, f"coords3d_{h}.npy")
    if os.path.exists(path) and not recompute:
        coords = np.load(path)
        print(f"[1.3] cache hit: coords3d {coords.shape}")
        return coords

    import umap
    print(f"[1.3] UMAP 3D (n_neighbors={C.UMAP_N_NEIGHBORS}, "
          f"min_dist={C.UMAP_MIN_DIST})...")
    coords = umap.UMAP(
        n_components=3,
        n_neighbors=C.UMAP_N_NEIGHBORS,
        min_dist=C.UMAP_MIN_DIST,
        metric=C.UMAP_METRIC,
        random_state=C.SEED,   # keep it: reproducibility > parallelism @270 docs
    ).fit_transform(E)

    # rescale for the scene: center, std ~= SCENE_STD
    coords = coords - coords.mean(axis=0)
    coords = coords * (C.SCENE_STD / coords.std())
    np.save(path, coords)

    # 2D control preview colored by true category
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    c2 = umap.UMAP(n_components=2, n_neighbors=C.UMAP_N_NEIGHBORS,
                   min_dist=C.UMAP_MIN_DIST, metric=C.UMAP_METRIC,
                   random_state=C.SEED).fit_transform(E)
    cats = sorted({d["category"] for d in docs})
    fig, ax = plt.subplots(figsize=(8, 6))
    for i, cat in enumerate(cats):
        m = np.array([d["category"] == cat for d in docs])
        ax.scatter(c2[m, 0], c2[m, 1], s=14, label=cat, alpha=0.8)
    ax.legend(fontsize=7)
    ax.set_title("UMAP 2D preview — colored by TRUE category")
    fig.tight_layout()
    out = os.path.join(SCREENSHOTS, "umap_preview.png")
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"[1.3] 2D preview -> {out}  "
          f"(done-when: >=5 of 6 categories clearly separated)")
    return coords


# --------------------------------------------------------------------------- #
# 1.4  K-Means on ORIGINAL 384-D vectors + silhouette + keyword labels
# --------------------------------------------------------------------------- #
def cluster(E: np.ndarray, docs: list[dict]) -> tuple[np.ndarray, dict]:
    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score
    import pandas as pd
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    if C.K_CLUSTERS is not None:
        best_k = C.K_CLUSTERS
        labels = KMeans(n_clusters=best_k, n_init=C.KMEANS_N_INIT,
                        random_state=C.SEED).fit_predict(E)
        best_s = silhouette_score(E, labels, metric="cosine")
        print(f"[1.4] fixed k={best_k}, silhouette={best_s:.4f}")
    else:
        scores, fits = {}, {}
        for k in C.K_RANGE:
            km = KMeans(n_clusters=k, n_init=C.KMEANS_N_INIT,
                        random_state=C.SEED)
            lab = km.fit_predict(E)
            s = silhouette_score(E, lab, metric="cosine")
            scores[k], fits[k] = s, lab
            print(f"[1.4] k={k:2d}  silhouette(cosine)={s:.4f}")
        best_k = max(scores, key=scores.get)
        best_s = scores[best_k]
        labels = fits[best_k]

        fig, ax = plt.subplots(figsize=(6, 4))
        ax.plot(list(scores), list(scores.values()), "o-")
        ax.axvline(best_k, ls="--", c="gray")
        ax.set_xlabel("k"); ax.set_ylabel("silhouette (cosine)")
        ax.set_title(f"K-Means model selection — best k={best_k}")
        fig.tight_layout()
        out = os.path.join(SCREENSHOTS, "silhouette.png")
        fig.savefig(out, dpi=150); plt.close(fig)
        print(f"[1.4] chosen k={best_k} (silhouette={best_s:.4f}) -> {out}")

    # corpus decision point
    if best_s < 0.05:
        print("[1.4] !!! silhouette < 0.05 — trigger: consider switching the "
              "corpus to arXiv abstracts (see plan 1.4). Limit: 1 iteration.")

    # contingency matrix cluster x category
    cats = [d["category"] for d in docs]
    ct = pd.crosstab(pd.Series(labels, name="cluster"),
                     pd.Series(cats, name="category"))
    print("[1.4] contingency matrix (expect a dominant diagonal):")
    print(ct.to_string())
    ct.to_csv(os.path.join(CACHE, "contingency.csv"))

    # TF-IDF keyword labels per cluster
    from sklearn.feature_extraction.text import TfidfVectorizer
    vec = TfidfVectorizer(max_features=5000, stop_words="english",
                          sublinear_tf=True)
    X = vec.fit_transform([d["text"] for d in docs])
    terms = np.array(vec.get_feature_names_out())
    cluster_labels = {}
    for cl in sorted(set(labels)):
        mean_tfidf = np.asarray(X[labels == cl].mean(axis=0)).ravel()
        top = terms[np.argsort(mean_tfidf)[::-1][:C.TFIDF_TOP_TERMS]]
        cluster_labels[str(int(cl))] = ", ".join(top)
        print(f"[1.4] cluster {cl}: {cluster_labels[str(int(cl))]}")

    return labels, cluster_labels


# --------------------------------------------------------------------------- #
# 1.5  Similarity matrix, semantic edges, per-node neighbors
# --------------------------------------------------------------------------- #
def build_edges(E: np.ndarray, docs: list[dict]) -> tuple[list, dict]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    n = len(docs)
    S = E @ E.T                       # normalized vectors => cosines
    np.fill_diagonal(S, 0.0)

    # per-node top-k semantic neighbors (for Focus+Context, O(1) in frontend)
    neighbors = {}
    topk_sets = []
    for i in range(n):
        order = np.argsort(S[i])[::-1][:C.NEIGHBORS_PER_NODE]
        neighbors[i] = [{"id": int(j), "sim": round(float(S[i, j]),
                                                    C.VALUE_DECIMALS)}
                        for j in order]
        topk_sets.append(set(int(j) for j in order[:C.TOP_K_EDGES]))

    # semantic edges: upper triangle, >= export threshold, hairball guard
    iu, ju = np.triu_indices_from(S, k=1)
    vals = S[iu, ju]
    mask = vals >= C.SIM_EXPORT_THRESHOLD
    edges = []
    for i, j, v in zip(iu[mask], ju[mask], vals[mask]):
        i, j = int(i), int(j)
        if j in topk_sets[i] or i in topk_sets[j]:   # top-k of EITHER endpoint
            edges.append({"source": i, "target": j,
                          "value": round(float(v), C.VALUE_DECIMALS),
                          "type": "semantic"})

    # Query-star guarantee: every node's top-K neighbor pair must exist as an
    # edge — the Focus+Context star renders retrieval results and must not be
    # cut by the export threshold or the top-k guard (schema v1.1: knn flag).
    have = {(min(e["source"], e["target"]), max(e["source"], e["target"]))
            for e in edges}
    added = 0
    for i in range(n):
        for nb in neighbors[i]:
            key = (min(i, nb["id"]), max(i, nb["id"]))
            if key not in have:
                have.add(key)
                edges.append({"source": key[0], "target": key[1],
                              "value": max(0.0, nb["sim"]),
                              "type": "semantic", "knn": True})
                added += 1
    print(f"[1.5] KNN guarantee: +{added} edges below threshold/guard")

    # edge budget analysis
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.hist(vals, bins=50)
    ax.set_xlabel("cosine similarity"); ax.set_ylabel("pairs")
    ax.set_title("Similarity distribution (upper triangle)")
    fig.tight_layout()
    out = os.path.join(SCREENSHOTS, "sim_histogram.png")
    fig.savefig(out, dpi=150); plt.close(fig)

    print(f"[1.5] semantic edges exported (>= {C.SIM_EXPORT_THRESHOLD}, "
          f"top-{C.TOP_K_EDGES} guard): {len(edges)}")
    for t in [round(C.SIM_EXPORT_THRESHOLD + 0.05 * i, 2) for i in range(5)]:
        cnt = sum(1 for e in edges if e["value"] >= t)
        print(f"       edges at threshold {t:.2f}: {cnt}")
    cnt06 = sum(1 for e in edges if e["value"] >= C.DEFAULT_UI_THRESHOLD)
    if cnt06 > 3000:
        print("[1.5] !!! >3000 edges at 0.6 — trigger: tighten TOP_K_EDGES "
              "to 6–8 in config.py (do NOT raise the threshold).")
    elif not (300 <= cnt06 <= 1500):
        print(f"[1.5] note: {cnt06} edges at 0.6 is outside the ~300–1500 "
              "target window — inspect the histogram.")
    return edges, neighbors


# --------------------------------------------------------------------------- #
# 1.6  Structural edges (category skeleton, NOT a clique)
# --------------------------------------------------------------------------- #
def build_structural_edges(E: np.ndarray, docs: list[dict],
                           semantic_edges: list) -> list:
    n = len(docs)
    S = E @ E.T
    np.fill_diagonal(S, -1.0)
    cats = np.array([d["category"] for d in docs])

    sem_by_pair = {(min(e["source"], e["target"]), max(e["source"], e["target"])): e
                   for e in semantic_edges}
    seen = set(sem_by_pair)
    structural = []
    for i in range(n):
        same = np.where(cats == cats[i])[0]
        same = same[same != i]
        order = same[np.argsort(S[i, same])[::-1][:C.STRUCTURAL_TOP_K]]
        for j in order:
            key = (min(i, int(j)), max(i, int(j)))
            if key in sem_by_pair:
                sem_by_pair[key]["struct"] = True   # dual-typed: semantic + structural
                continue
            if key in seen:
                continue
            seen.add(key)
            structural.append({"source": key[0], "target": key[1],
                               "value": round(float(S[i, j]), C.VALUE_DECIMALS),
                               "type": "structural"})
    skeleton = len(structural) + sum(1 for e in semantic_edges if e.get("struct"))
    print(f"[1.6] structural-only edges: {len(structural)}; category skeleton "
          f"total (incl. dual-typed): {skeleton} ({skeleton / n:.2f} per node; "
          f"done-when window: 1.5–3.0)")
    return structural


# --------------------------------------------------------------------------- #
# 1.7  Export graph_data.json (THE CONTRACT — freeze before frontend work)
# --------------------------------------------------------------------------- #
def export_json(docs, coords, labels, cluster_labels, edges) -> str:
    nodes = []
    for d, (x, y, z), cl in zip(docs, coords, labels):
        red = redact(d["text"])
        truncated = len(red) > C.TEXT_TRIM_CHARS
        nodes.append({
            "id": int(d["id"]),
            "name": display_title(d["text"], C.TITLE_MAX_CHARS),
            "category": d["category"],
            "cluster": int(cl),
            "tokens": int(d["n_tokens"]),
            "x": round(float(x), C.COORD_DECIMALS),
            "y": round(float(y), C.COORD_DECIMALS),
            "z": round(float(z), C.COORD_DECIMALS),
            "text": red[:C.TEXT_TRIM_CHARS],
            "truncated": truncated,
            "neighbors": d["neighbors"],
        })

    payload = {
        "meta": {
            "corpus": "20newsgroups",
            "k": int(len(cluster_labels)),
            "minThreshold": C.SIM_EXPORT_THRESHOLD,
            "defaultThreshold": C.DEFAULT_UI_THRESHOLD,
            "clusterLabels": cluster_labels,
        },
        "nodes": nodes,
        "links": edges,
    }

    out = os.path.normpath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), C.OUTPUT_JSON))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False,
                  separators=(",", ":"))      # compact: file size matters
    size_mb = os.path.getsize(out) / 1e6
    print(f"[1.7] wrote {out}  ({size_mb:.2f} MB; target < 2 MB)")
    return out


# --------------------------------------------------------------------------- #
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--recompute", action="store_true",
                    help="ignore all caches, rebuild from scratch")
    args = ap.parse_args()

    docs = load_corpus(recompute=args.recompute)
    h = corpus_hash(docs)
    print(f"[*]   corpus hash: {h}")

    E = embed(docs, h, recompute=args.recompute)
    coords = reduce_3d(E, docs, h, recompute=args.recompute)
    labels, cluster_labels = cluster(E, docs)
    semantic, neighbors = build_edges(E, docs)
    structural = build_structural_edges(E, docs, semantic)

    for d in docs:                       # attach precomputed neighbors
        d["neighbors"] = neighbors[d["id"]]

    export_json(docs, coords, labels, cluster_labels, semantic + structural)
    print("[*]   done. Next: python validate_json.py  (M1 gate)")


if __name__ == "__main__":
    sys.exit(main())
