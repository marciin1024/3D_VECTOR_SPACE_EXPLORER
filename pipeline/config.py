"""ALL tunable pipeline parameters live here (and only here).

Every non-obvious change of a value below should get one line in NOTES.md.
"""

SEED = 42

# --- 1.1 Corpus (20 Newsgroups) ---------------------------------------------
CATEGORIES = [
    "sci.space",
    "rec.sport.hockey",
    "comp.graphics",
    "sci.med",
    "rec.autos",
    "talk.politics.mideast",
]
DOCS_PER_CATEGORY = 45          # ~270 documents total
MIN_CHARS = 200                 # filter AFTER remove=(...) cleaning
MAX_CHARS = 3000
TITLE_MAX_CHARS = 60

# --- 1.2 Embeddings -----------------------------------------------------------
EMBEDDING_MODEL = "all-MiniLM-L6-v2"   # 384-D, truncates at 256 tokens (NOTES)
EMBED_BATCH_SIZE = 64

# --- 1.3 UMAP -----------------------------------------------------------------
UMAP_N_NEIGHBORS = 15           # tuning grid: {10, 15, 30}
UMAP_MIN_DIST = 0.1             # tuning grid: {0.1, 0.3}
UMAP_METRIC = "cosine"
SCENE_STD = 40.0                # rescale coords: centered, std ~= 40 units

# --- 1.4 K-Means --------------------------------------------------------------
K_CLUSTERS = None               # None => pick best silhouette over K_RANGE
K_RANGE = range(4, 11)          # k = 4..10
KMEANS_N_INIT = 10
TFIDF_TOP_TERMS = 4             # keyword labels per cluster ("space, orbit, nasa")

# --- 1.5 Semantic edges -------------------------------------------------------
SIM_EXPORT_THRESHOLD = 0.25     # eksport: 2002 par przed guardem top-10
DEFAULT_UI_THRESHOLD = 0.35     # ~791 par surowych; po guardzie spodziewamy się ~500–700
TOP_K_EDGES = 10                # hairball guard: edge survives if in top-k of
                                # EITHER endpoint; tighten to 6–8 if >3000 edges
NEIGHBORS_PER_NODE = 10         # precomputed node.neighbors for Focus+Context

# --- 1.6 Structural edges -----------------------------------------------------
STRUCTURAL_TOP_K = 3            # 3 semantically nearest SAME-category nodes

# --- 1.7 Export ---------------------------------------------------------------
TEXT_TRIM_CHARS = 1500          # trim node.text, set truncated flag
COORD_DECIMALS = 2
VALUE_DECIMALS = 3
OUTPUT_JSON = "../web/data/graph_data.json"
