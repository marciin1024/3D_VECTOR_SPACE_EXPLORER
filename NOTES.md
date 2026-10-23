# NOTES — decision log

> Rule: after every task, 2–3 sentences — what was decided, why, screenshot if
> there is anything to show. Final report (§ Phase 6) assembles itself from here.

## Phase 0 — Environment (2026-07-03)

- (0.1) Repo initialized locally (starter scaffold), branch renamed master → main,
  pushed to GitHub as a private repo (this public repo is a clean export of that history). 
  Empty dirs (cache/, screenshots/) not tracked by git — created automatically 
  by build_graph.py at first run.
- (0.2) venv with Python 3.11 instead of conda (README updated accordingly).
  Model all-MiniLM-L6-v2 (~91 MB) downloaded and cached on first run. Smoke test
  passed on first attempt: shape (1, 384); cos(similar pair) = 0.531 vs
  cos(unrelated) = -0.005 — model semantically sane.
- (0.3) Frontend skeleton (3d-force-graph@1 + d3@7, pinned CDN) verified in Chrome
  and Firefox: sample ~80-node tree renders, orbit/zoom/pan and Reset camera work,
  console clean. Note: Firefox console noise came from the MetaMask extension
  (moz-extension://), not the app — remember this during Phase 5 cross-browser
  testing. Chrome: harmless favicon 404, silenced with an inline SVG icon.
  Safari test deferred — need access to a Mac (plan: task 5.1). 
  → CDN loading later replaced by vendored copies (3.2, audit)

## Phase 1 — Pipeline (2026-07-03)

- (1.1) 20NG corpus: 270 docs, perfectly balanced 45×6, headers/footers/quotes
  removed, dedup on normalized text. Corpus hash 4a3ee3ab674b.
- (1.2) all-MiniLM-L6-v2, normalize_embeddings=True (cosine == dot product
  downstream). 256-token truncation accepted as a deliberate decision for a
  200–3000 char corpus. Cache keyed by corpus hash works (second run: cache hit).
- (1.3) UMAP 3D (n_neighbors=15, min_dist=0.1, cosine, seed=42); 2D preview
  shows clear category separation — default parameters kept, tuning grid not
  needed. Coords centered, std ≈ 40.
- (1.4) k=6 chosen by silhouette (0.1437), matches the 6 source categories;
  contingency matrix strongly diagonal (hockey 45/45). TF-IDF cluster labels
  readable ("space, earth…", "game, team, hockey, nhl"…). Silhouette >> 0.05
  trigger — corpus decision closed: 20NG stays, no arXiv switch needed.
- (1.5) Similarity thresholds recalibrated from the proposal's a priori 0.5/0.6
  to export=0.25 / default UI=0.35 after inspecting the empirical distribution
  (median 0.025, p90 0.178, p99 0.411 — MiniLM on short noisy 20NG posts yields
  low absolute cosines; the proposal's 0.5–0.85 range would leave 16 edges).
  Result: 1295 edges exported, 661 at the default threshold (target 300–1500).
  Consequence for Phase 3: edge-width tiers rescaled to TIERS = [0.35, 0.45, 0.55].
  → edge counts superseded by schema v1.1 in 4.2 (1868 semantic incl. knn);
  thresholds and tiers unchanged.
- (1.6) After recalibration most same-category top-3 pairs were already covered
  by semantic edges; switched to dual-typing (semantic edge carries struct=True)
  instead of dropping them. Category skeleton: 601 edges, 2.23/node (window
  1.5–3.0). Consequence for Phase 4 (task 4.3): structural-view visibility test
  is l.type === 'structural' || l.struct.
- (1.7) M1 GATE CLOSED: validator green (270 nodes, 1295 semantic + 99
  structural-only links, 0.40 MB); determinism verified — 4× --recompute →
  identical SHA256 (9C83DA7C…); full rebuild ~80 s. Schema frozen; any future
  change is a versioned event. Tag: m1. → structural-only count changed to 15 in schema v1.1 (4.2).
- Bugfix during 1.6 rework: missing `return structural` after refactor caused
  TypeError at export — caught because the crash happened before export, so the
  "green" validator run was validating a stale file. Lesson: validate only after
  a clean full-run exit.

## Phase 2 — Vertical slice (2026-07-03)

- (2.1) Real graph_data.json renders; rawData copy kept (library mutates
  source/target). Temporary nodeAutoColorBy colors — poor gray/blue contrast
  confirms the need for Tableau10 in Phase 3.
- (2.2) Plan's default forces (0.1·value, charge −30) collapsed UMAP separation;
  recalibrated to gentle physics: link strength 0.03·(value−0.25)/0.45, charge
  −10, cooldown 15 s. Layout settles in seconds, structure preserved; frozen
  fallback not needed. Center overlap (sci/comp) reflects real semantic
  proximity. → knn edges (4.2) get strength 0.
- (2.3) FPS pitfall: Chrome initially ran on the Intel iGPU (hybrid laptop) —
  orbit 33–36 FPS, misleadingly in the 30–50 decision band. After forcing the
  dGPU (Windows Settings → Display → Graphics → High performance):
  rest 140–144 / orbit 100–105 / zoom 144. No data cuts needed (top-k stays 10).
  Demo-day checklist item: verify dGPU on the presentation machine.
  iGPU numbers double as the "weaker hardware" data point for task 5.1.

## Phase 3 — Visual encoding (2026-07-03)

- (3.1) scales.js created: Tableau10 ordinal scale for clusters (Ware:
  pre-attentive categorical channel), scaleSqrt [2,8] for radius so perceived
  area ~ token count (Cleveland & McGill), edge tiers recalibrated to
  TIERS=[0.35,0.45,0.55] / WIDTHS=[0.5,1.2,2.5] per the empirical similarity
  range from 1.5. Single source of truth — no magic numbers in render code.
- (3.2) Version saga (≈2 h, timebox hit): (1) three r160+ removed the UMD build
  (CDN file exists but is a stub — no global THREE); (2) r159 UMD conflicts with
  current 3d-force-graph (missing THREE.Timer); (3) esm.sh with ?external=three
  failed to resolve re-exports (Timer) regardless of version; (4) npm dist .mjs
  is not self-contained (bare specifiers: three/webgpu, examples/jsm,
  three-forcegraph); (5) Windows http.server serves .mjs as text/plain (rejected
  by strict module MIME checks). FINAL: vendored locally — 3d-force-graph.min.js
  (UMD, self-contained, global ForceGraph3D) + three@0.169 as an ES module via
  import map for our own meshes. Two Three instances by design; benign for
  Mesh/Geometry/Material (the 270× "Material: onBuild() removed" warnings are
  cosmetic). App now fully offline-capable (demo-proof). → not true until d3 was 
  vendored (audit, Phase 4). Watch item for 3.3:
  if edge materials misbehave, align our three version with the bundled one
  (npm ls three → bundled: 0.185.1 via three-render-objects; our vendored module:
  0.169.0 — 16 releases apart, explains the cosmetic onBuild warnings; upgrade 
  attempted in 3.3/step 0 — failed, reverted).
- (3.2) Done-when verified: directional shading visible, all 6 Tableau10
  cluster colors mutually distinguishable (red/orange pair flagged for the
  color-blindness check in 3.4), sqrt-scaled sizes clearly separate short vs
  long docs (politics.mideast cluster visibly "heavier" — highest mean length).
  Shared unit SphereGeometry scaled per node. Orbit FPS after spheres: 90
  (rest ~140) — ample headroom for edge cylinders in 3.3.
- (3.3/step 0) Attempted aligning our three to the bundle's declared 0.185.1 —
  BACKFIRED: the prebuilt .min.js renderer actually calls material.onBuild(),
  removed in newer three, so 0.185 materials crash the render loop
  (t.onBuild is not a function → black screen). Also learned: three ≥ r170
  splits the build into three.module.js + three.core.js (relative import) —
  vendoring needs both files. REVERTED to 0.169.0 (monolithic build); the 270
  cosmetic onBuild warnings are the accepted cost of the working pair.
  Version pair LOCKED for the rest of the project:
  three@0.169.0 + 3d-force-graph@1.73.0.
- (3.3) Multi-relational edges DONE with variant A (per-edge rgba alpha) —
  verified by a red-color test that linkColor honors both the color and the
  alpha channel; variant B (shared linkMaterial tiers) not needed. Structural:
  gray rgba(153,153,153,0.35), width 0.4. Semantic: rgba(120,160,220, α) with
  α = 0.15 + 0.65·(value−0.25)/0.45 mapped to the empirical similarity range,
  widths via TIERS [0.35,0.45,0.55] → WIDTHS [0.5,1.2,2.5]. Orbit FPS with
  cylinders: ~95 (threshold 40) — no tier-2-only fallback needed  → at that 
  time edges were additionally dimmed by the library's global linkOpacity 0.2; 
  fixed in 4.1/4.2.
- (3.4) Hairball test: cluster structure readable from the default camera at
  threshold 0.35 — no change needed. Color-blindness (DevTools emulation,
  deuteranopia + protanopia): yellow/teal/blue stay separable, but
  red/orange/green collapse into a brown-olive range — a known limitation of
  any 6-category categorical palette. DECISION (option a): keep Tableau10 and
  rely on redundant channels — spatial separation (UMAP layout) and keyword
  cluster labels in the legend (done in 4.3); documented as a limitation
  (report §5, Ware's redundant-encoding guideline). Screenshots saved.
- (3.4) Background A/B: #000 vs #101418 visually indistinguishable on the
  laptop display. Graphite #101418 chosen: matches the CSS loading background
  (seamless transition) and is safer on projectors (black-level bloom).
- (3.4) Outside-person perceptual test (N=5, cold, no explanation; backgrounds:
  2 IT, 3 non-IT):
  · colors → 4/5; 
  · sizes  → 3/5; 
  · edges  → 5/5
  Takeaway: grouping read pre-attentively by all; size ambiguous
  (importance vs length) → the 5.2 About overlay must state "size = document
  length" explicitly.

## Phase 4 — Interactions

- (4.1) state.js created: single state object (mode, focusNodeId, neighborIds,
  hiddenClusters, edgeView, simThreshold) + one applyState() that recomputes
  ALL scene visibility and styling after every state change. Discipline: no
  interaction touches the scene directly — this eliminates the "stuck dimmed
  graph" class of bugs by construction. All edge styling moved from main.js
  (3.3 block) into applyState() — single source of truth; verified the refactor
  changed nothing visually. Console test passed: hiding/showing cluster 4 via
  state + applyState works deterministically. Focus algebra rule built in: if
  the focused node's cluster gets hidden, focus auto-clears (rule 3 of 4.5).
- (4.1/4.2) linkOpacity(1) discovery: the library's global linkOpacity
  (default 0.2) multiplies our per-edge rgba alpha — this was the cause of the
  "milky/khaki" edge colors observed since 3.3. With linkOpacity(1) our alpha
  range 0.15–0.8 renders as designed and focus-highlight gold
  rgba(255,200,80,1.0) is clean.
- (4.2) focusNode(n) extracted from onNodeClick (single procedure for click,
  console-driven testing, and the 4.4 side-panel neighbor navigation, per plan).
  Interaction: click → dimming (0.08) + gold query star + camera fly-in (1 s)
  + query label; exit via Esc / background click / Reset. Clicks on dimmed
  nodes are ignored while in focus.
- (4.2) Camera framing required an adaptive offset: measured neighbor spreads
  (e.g. "Greetings…": 52–142 units, max ≈ 3× min) show that semantic top-8
  neighbors are NOT spatially compact — UMAP+force preserve neighborhoods only
  approximately, so cosine-nearest ≠ scene-nearest. Fixed offsets (70, 120,
  130) all failed on either central or peripheral nodes. Final solution:
  compute the subgraph's actual radius and back off 3.0× along the current
  viewing direction — multiplier derived from the camera's 40° vertical FOV
  (r / tan 20° ≈ 2.75r + margin); an earlier 2.2× was too tight vertically on
  widescreen. Report observation: the visualization itself exposes the
  semantic-vs-spatial gap.
- (4.2) BUG: the query star was incomplete (e.g. node 112: only 1/8 edges
  visible). Diagnosis: 4/8 focus↔neighbor pairs had NO edge in the data
  (export threshold 0.25 + top-10 guard; top-k is asymmetric), 3 more fell
  below the UI threshold 0.35. Root cause: a retrieval result ≠ a graph subset.
  Fix = SCHEMA v1.1 (first versioned change since M1): the pipeline now
  guarantees every node.neighbors pair exists as an edge (knn:true flag);
  linkVisible lets the focus star bypass the threshold and edge-type filters
  (cluster hiding still applies — algebra rule 1). knn edges are display-only:
  link force strength 0, so the layout is unchanged.
- (4.2) Schema v1.1 regeneration: +573 knn edges (semantic 1295 → 1868);
  default-threshold view unchanged (661 edges at 0.35). Structural-only edges
  dropped 99 → 15 because knn pairs absorbed more same-category pairs as
  dual-typed; skeleton total unchanged (601, 2.23/node). Validator green.
  Pitfall repeated: one regeneration attempt crashed (IndentationError) and the
  validator then passed on the stale file — always check that build_graph.py
  reaches "[*] done." before trusting the validator.
- (4.2) Cross-cluster analysis: 59/270 nodes have ≥3/8 cross-cluster
  neighbors. The 8/8 extremes ("Sigh.", "…a couple of questions…") are
  short/generic docs whose embeddings carry weak topical signal → quasi-random
  neighbors. Report §5 observation: cross-ratio inversely tracks document
  specificity — the same weak-query pathology known from production RAG.
- (4.2) Protocol result: 10/10 test nodes show the complete 8-arm star fully
  in frame; rapid click→click→deselect sequences leave no stale highlights.
  Orbit FPS after +573 knn edges: 125+ (no impact). Demo nodes saved to
  report/demo_nodes.md — centerpiece: id 112 ("…flattening out a globe"),
  a comp.graphics query whose context spans two clusters.
- (4.2 → 4.4 TODO) Focus node can be visually lost at the star's hub when it's
  a short document (small sphere). Plan: enlarge the focused node (~2×) or add
  a bright outline in focus mode.
- (4.3) Filter panel done: cluster legend generated from meta.clusterLabels
  (TF-IDF labels + counts, same colorScale as spheres), cluster toggles,
  edge-type switch, threshold slider 0.25–0.75 with live edge counter
  (676 at 0.35 in "both"; 601 in "structural"). Filters use visibility only,
  no graphData() rebuild — layout never restarts. Slider smooth at 125+ FPS,
  no debounce needed. Focus combinations verified: star survives slider and
  edge-type changes, focus auto-clears when its own cluster is hidden,
  neighbor arms disappear/return with their cluster. In focus mode background
  edges are dimmed to α=0.03, so edge-type switching is barely perceptible
  there — intentional (Focus+Context); revisit after the 4.5 colleague test.
- (4.3) BUG (stuck full-opacity nodes): hiding then re-showing a cluster during
  focus brought its nodes back at full brightness — the library re-creates
  meshes for re-shown nodes after applyState() has run. Fix: single
  nodeOpacity(n) rule used both in applyState() and at mesh creation
  (nodeThreeObject), plus a next-frame re-sync.
- (4.3) Structural view ignores the similarity threshold: the "same category"
  relation is metadata, not similarity (shows the full 601-edge skeleton;
  before the fix it showed only 346). Slider max set to 0.75 instead of the
  plan's 0.95 — above ~0.7 the data has almost no edges. Node lookup in
  linkVisible switched from find() to a Map (slider calls applyState on every
  input event).
- (audit) d3 was still loaded from unpkg — the "fully offline" claim in 3.2
  was false until now. Vendored d3@7 (web/vendor/d3.min.js); verified with
  Wi-Fi off: the app loads fully from localhost. Note: DevTools "Offline"
  throttling is NOT a valid test — it also blocks localhost.
- (audit) Determinism re-verified for schema v1.1: 2× --recompute →
  identical SHA256 (03469B8D…), 0.44 MB, validator green. README updated:
  setup steps (venv + requirements), data generation before first run,
  vendored libs (offline), current structure.
- (4.4) Details on demand done: hover tooltip (title, category, cluster label,
  tokens; HTML-escaped), pointer cursor over nodes, left side panel with full
  document text (textContent — safe for < > & in 20NG posts) and the top-8
  retrieved context list with cosine values; clicking a list entry calls the
  same focusNode() → semantic navigation across the graph. Entries whose
  cluster is hidden are greyed out and not clickable; the list re-renders on
  filter changes. Query node enlarged in focus mode (nodeScale: max(2r, 6)) —
  resolves the 4.2 TODO. Exit paths unified: Esc / background / panel × /
  Reset button all call resetFocus(), which closes the panel too (bug: it
  initially did not — closeDetails() was missing). Dark color-scheme for
  native scrollbars/controls.
- (4.5) Interaction combination matrix:

| # | Scenario | Expected | Result |
|---|---|---|---|
| 1 | Focus + hide a neighbor's cluster | focus stays; those arms vanish; list entries greyed |✓|
| 2 | Focus + hide the focus node's own cluster | focus clears; label + panel close; camera returns |✓|
| 3 | Focus + move threshold slider | star stays complete; only background changes |✓|
| 4 | Focus + switch edge type (semantic/structural) | star stays complete |✓|
| 5 | Reset (Esc) with active filters | focus clears; filters STAY as set |✓|
| 6 | Rapid node→node→node clicking | clean switch; no stale dimming/gold edges |✓|
| 7 | Click a dimmed node during focus | ignored (no change) |✓|
| 8 | Drag slider, then immediately click a node | focus works; slider value kept |✓|
| 9 | Panel navigation 5× in a row | each hop: camera, star, panel, label update |✓|
| 10 | Panel navigation + then hide target's cluster | focus clears cleanly |✓|
| 11 | Hide ALL clusters, then focus attempt | nothing to click; no errors |✓|
| 12 | Hide all, show all again (in focus and idle) | re-shown nodes have correct opacity/size |✓|
| 13 | Esc / background click in idle | nothing happens, no errors |✓|
| 14 | Reset camera in idle after orbiting | camera returns; nothing else changes |✓|

- (4.5) Informal test with a non-technical family member: 3 min of free exploration.

## Phase 5 — Testing & polish

- (5.1) Netlify deploy: vendor/three/build/three.module.js was missing from the
  drag-and-drop upload (nested folder lost) → 404 → modules never started
  (endless spinner). Flattened vendor/ to three files (three.module.js,
  3d-force-graph.min.js, d3.min.js); import map updated. Local + Netlify OK.

- (5.1) Cross-browser test (identical scenario in each browser):

  | # | Step | Chrome | Firefox | Safari |
  |---|---|---|---|---|
  | 1 | Load: spinner → graph; About opens on first visit |✓|✓|✓|
  | 2 | Orbit / zoom / pan smooth |✓|✓|✓|
  | 3 | Hover 5 nodes: tooltip appears, pointer cursor |✓|✓|✓|
  | 4 | Click a node: camera fly-in, dimming, gold star, label, side panel |✓|✓|✓|
  | 5 | Navigate to a neighbor from the side list (3 hops) |✓|✓|✓|
  | 6 | Esc: everything back to overview |✓|✓|✓|
  | 7 | Hide 2 clusters; edge type switch; slider full range |✓|✓|✓|
  | 8 | Hide all clusters → empty state → Reset filters |✓|✓|✓|
  | 9 | Resize the window: graph follows |✓|✓|✓|
  | 10 | 2 min free clicking; console: no red errors |✓|✓|✓|

- (5.2) UX polish driven by the 3.4/4.5 results: size was the weakest channel
  (3/5 guessed) → explicit size legend in the panel (min / median / max words,
  same radiusScale) and the About text states "size = document length, not
  importance". Colors (4/5) and edges (5/5) needed no change. The non-technical
  tester found every feature unaided (4.5), so the About overlay stays short:
  what you see, one "try it" sentence framing the click as a RAG query,
  controls. Opens on first visit (localStorage), then via the About button.
  Also: loading screen with title + spinner, project title in the panel
  header, empty state with "Reset filters", viewport resize handling.
- (5.2) Onboarding test (fresh person, never saw the project): read the About
  overlay and discovered the focus interaction unaided in < 1 min;
  found all features (query, side list navigation, filters, reset) and
  described the visualization as understandable. Done-when met.

- (5.3) Code cleanup: removed dev-only globals, Phase-0 sample-data mode, unused
  rawData copy and imports; constants hoisted (KNN_N, BG_COLOR); onBuild warnings
  silenced; vendor/ flattened; validator message updated + schema v1.1 flag
  check (knn/struct must be bool). README completed: setup, data generation,
  structure, configuration tables, known limitations.
- (5.3) Fresh-clone test: cloned into a clean folder, followed ONLY the README
  (venv → pip install → pipeline → validator → http.server) — passed without
  any fix. M5 reached: CODE FREEZE — from now on bug fixes only, and only if
  they break the demo scenario.

## Phase 6 — Report & demo

- Final report delivered as report/Final_Report.pdf; this log was its source.

## Pre-publication audit

- (privacy) The 20NG posts contained sender lines and e-mail addresses in the
  text shown in the app and in the report figures. Fix: pipeline/redact.py
  redacts `name` and `text` at export (after embedding, clustering and
  edges), so no analysis number changes. Verified: all non-display fields
  identical to the previous export (compare script), display fields changed
  in 41 texts and 7 names. check_pii.py fails the build if any address or
  sender line remains. Report Fig. 11 regenerated.
- (privacy) Determinism re-verified after the change: 2× --recompute →
  identical SHA256 (FD057AA0…), validator and PII check green.

## Future Work (anti-goals parked here)

- live free-text querying · semantic zooming · custom shaders · mobile · >300 nodes
