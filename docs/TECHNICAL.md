# Technical documentation

Setup, configuration and limitations of the 3D Semantic Vector Space Explorer. For the overview and findings see the [README](../README.md); the full write-up is in [`report/Final_Report.pdf`](../report/Final_Report.pdf).

Final project for Scientific and Large Data Visualization, University of Pisa, 2026.

## How to use

| Action | Control |
|---|---|
| Rotate / zoom / pan | left-drag / scroll / right-drag |
| Simulate a query | click a sphere |
| Jump to a retrieved document | click an entry in the side panel |
| Back to the overview | Esc, click the background, or *Reset camera* |
| Filter | right panel: cluster checkboxes, edge type, similarity threshold |
| Explanation of the encoding | *About* button |

## Quick start

Requirements: a WebGL-capable desktop browser, plus Python 3.11 if you want to rebuild the data. The frontend needs no internet connection and no npm: all JS libraries are vendored in `web/vendor/`.

**Run the app.** The generated `web/data/graph_data.json` is committed (0.44 MB), so this is enough:

```bash
cd web
python -m http.server 8000          # then open http://localhost:8000
```

Always serve over HTTP: opening `index.html` as a file (`file://`) is blocked by the browser (ES modules and data loading).

**Rebuild the data (optional)**

```bash
python3.11 -m venv .venv
source .venv/bin/activate           # Windows: .\.venv\Scripts\Activate.ps1
pip install -r pipeline/requirements.txt

cd pipeline
python build_graph.py --recompute   # full deterministic rebuild, ~80 s
python validate_json.py             # must end with "VALIDATION GREEN"
python check_pii.py                 # must end with "PII CHECK GREEN"
```

The first run also downloads the 20 Newsgroups corpus and about 91 MB of model weights. Later runs reuse cached stages (`python build_graph.py`, seconds). Check that `build_graph.py` ends with `[*] done.` before trusting the validators: after a crash they would check the previous file.

## Tested on

- Chrome, Firefox and Safari (identical 10-step scenario, all passed).
- Performance on a GTX 1650 Ti laptop: 125+ FPS while orbiting.
- On hybrid-graphics laptops make sure the browser runs on the dedicated GPU (Windows: Settings, Display, Graphics, High performance). On the integrated GPU orbiting drops to about 35 FPS.
- Determinism: same seed gives a byte-identical `graph_data.json` (SHA-256, two independent `--recompute` runs).

## Structure

```
pipeline/            Python data pipeline
  config.py          ALL tunable parameters
  build_graph.py     corpus -> embeddings -> UMAP -> K-Means -> edges -> JSON
  redact.py          removes sender lines and e-mail addresses from displayed text
  validate_json.py   schema validator (graph_data.json contract, v1.1)
  check_pii.py       fails if the JSON still contains e-mail addresses or sender lines
  requirements.txt   pinned Python dependencies
  cache/             intermediate artifacts, keyed by corpus hash (not committed)
web/                 static frontend (no build step)
  index.html
  js/                main.js (bootstrap, focus+context), state.js (app state +
                     applyState), ui.js (panels, legends, About), scales.js
                     (visual encoding)
  css/               style.css
  vendor/            three.module.js, 3d-force-graph.min.js, d3.min.js
                     (vendored, pinned, offline-capable) + LICENSES.txt
  data/              graph_data.json (generated, committed)
report/              final report, screenshots/, demo_nodes.md
docs/                this file
package.json         npm versions of the libraries that were vendored into web/vendor/
NOTES.md             decision log kept throughout the project
```

## Configuration

**Pipeline.** All tunable parameters live in `pipeline/config.py`:

| Constant | Value | Meaning |
|---|---|---|
| `CATEGORIES`, `DOCS_PER_CATEGORY` | 6 x 45 | corpus selection (270 docs) |
| `MIN_CHARS` / `MAX_CHARS` | 200 / 3000 | document length filter |
| `UMAP_N_NEIGHBORS` / `UMAP_MIN_DIST` | 15 / 0.1 | 3D projection |
| `K_RANGE` | 4 to 10 | K-Means search range (k chosen by silhouette, result 6) |
| `SIM_EXPORT_THRESHOLD` | 0.25 | minimum cosine for exported semantic edges |
| `DEFAULT_UI_THRESHOLD` | 0.35 | initial slider value |
| `TOP_K_EDGES` | 10 | hairball guard (edge kept if in top-k of either endpoint) |
| `NEIGHBORS_PER_NODE` | 10 | precomputed neighbours stored on each node |
| `STRUCTURAL_TOP_K` | 3 | same-category skeleton edges per node |
| `SEED` | 42 | determinism (same seed gives byte-identical JSON) |

The similarity thresholds were derived from the empirical distribution of the corpus (median cosine 0.025, 99th percentile 0.41), not from a priori values; see the report, section 2.5.

**Frontend**

| Where | Constant | Meaning |
|---|---|---|
| `js/scales.js` | `TIERS` = [0.35, 0.45, 0.55], `WIDTHS` = [0.5, 1.2, 2.5] | edge-width tiers |
| `js/scales.js` | radius range [2, 8], sqrt scale | sphere size ~ document length |
| `js/main.js` | `KNN_N` = 8 | retrieved context size in a query |
| `js/main.js` | `BG_COLOR` = #101418 | scene background |
| `js/state.js` | 0.08 / 0.03 | opacity of dimmed nodes / edges in focus mode |

## Data and privacy

Embeddings, clusters, neighbours and TF-IDF labels are computed from the cleaned corpus text. Before export, `redact.py` replaces sender/routing lines (`From:`, `To:`, `Cc:`, `Sender:`, `Reply-To:`) and e-mail addresses in the fields shown in the app (`name`, `text`) with `[redacted]` / `[email]`. A document whose first line was a sender line gets the next non-header line as its `name`. Because redaction happens after the analysis, it changes no numbers in the report. Posts can still contain names inside their body text.

## Known limitations

- **Static, precomputed corpus** (270 documents). Changing the corpus requires re-running the pipeline and re-calibrating the thresholds.
- **Node selection as query:** the RAG query is simulated by clicking an existing document; free-text querying (client-side embedding) is out of scope.
- **256-token truncation:** `all-MiniLM-L6-v2` embeds only the beginning of long documents; sphere size still reflects the full length.
- **Semantic is not spatial:** UMAP plus the force layout preserve neighbourhoods only approximately. A document's nearest semantic neighbours can be far apart in the scene (the gold query star makes this visible).
- **Color-vision deficiency:** under deuteranopia/protanopia simulation the red/orange/green clusters become hard to distinguish; spatial separation and keyword labels act as redundant channels.
- **Library version pair locked** (three@0.169.0 + 3d-force-graph@1.73.0): newer three.js versions break the bundled renderer.
- **Desktop only** (mouse and keyboard); no touch or mobile support.
- **Scale:** designed for about 300 nodes; thousands would need instanced rendering and GPU-side similarity computation.
- **Small user study:** 7 participants, indicative rather than conclusive.
