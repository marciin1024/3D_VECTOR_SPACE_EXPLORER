// main.js — bootstrap: data loading, scene setup, Focus+Context (RAG query
// simulation) and wiring of the filter panel, details panel and About overlay.
// Styling rules live in state.js (applyState), visual scales in scales.js,
// DOM panels in ui.js.
import * as THREE from 'three';
import { colorScale, initScales } from './scales.js';
import { state, bindGraph, applyState, countVisibleLinks, nodeOpacity, nodeScale } from './state.js';
import { buildPanel, setEdgeCount, openDetails, closeDetails,
         buildSizeLegend, initAbout, setEmptyState } from './ui.js';

const KNN_N = 8;               // size of the retrieved context (top-k neighbors)
const BG_COLOR = '#101418';    // graphite, A/B tested against black (NOTES 3.4)

const loadingEl = document.getElementById('loading');
const graphEl = document.getElementById('graph');
const queryLabel = document.getElementById('query-label');

async function loadData() {
  const res = await fetch('data/graph_data.json');
  if (!res.ok) throw new Error(`HTTP ${res.status} while fetching graph_data.json`);
  return res.json();
}

async function init() {
  let data;
  try {
    data = await loadData();
  } catch (err) {
    loadingEl.textContent =
      `Failed to load data: ${err.message}. ` +
      `Are you running through "python -m http.server" (not file://)?`;
    loadingEl.classList.add('error');
    console.error(err);
    return;
  }

  initScales(data.nodes);
  const G = ForceGraph3D()(graphEl).graphData(data);
  const initialCameraPos = { ...G.cameraPosition() };

  // Layout: UMAP-seeded positions + gentle forces (NOTES 2.2). Link attraction
  // grows with similarity (empirical range 0.25–0.7); knn edges (schema v1.1)
  // are display-only and get strength 0 so they never move the layout.
  G.d3Force('link').strength(l =>
    l.knn ? 0 :
    l.type === 'semantic' ? 0.03 * (l.value - 0.25) / 0.45 : 0.005);
  G.d3Force('charge').strength(-10);
  G.cooldownTime(15000);              // freeze physics after 15 s

  // Nodes: lit spheres sharing one unit geometry, scaled per node.
  // Opacity and size come from the single rules in state.js.
  const sphereGeom = new THREE.SphereGeometry(1, 16, 12);
  G.nodeThreeObject(n => {
    const material = new THREE.MeshLambertMaterial({
      color: colorScale(n.cluster), transparent: true, opacity: nodeOpacity(n),
    });
    // The bundled renderer still calls material.onBuild(), which three@0.169
    // only stubs with a deprecation warning — a no-op silences it (NOTES 4.5).
    material.onBuild = () => {};
    const mesh = new THREE.Mesh(sphereGeom, material);
    mesh.scale.setScalar(nodeScale(n));
    return mesh;
  });

  G.backgroundColor(BG_COLOR);
  G.linkOpacity(1);                   // per-edge alpha lives in rgba colors (state.js)

  bindGraph(G);
  state.simThreshold = data.meta.defaultThreshold;
  applyState();

  // Details on demand: tooltip (HTML-escaped) + pointer cursor
  const esc = s => String(s).replace(/[&<>"']/g, c =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  G.nodeLabel(n => `<div class="tip"><b>${esc(n.name)}</b><br>` +
    `${esc(n.category)} · ${esc(data.meta.clusterLabels[n.cluster])} · ${n.tokens} tok.</div>`);
  G.onNodeHover(n => { graphEl.style.cursor = n ? 'pointer' : null; });

  const nodeById = new Map(data.nodes.map(m => [m.id, m]));
  const detailsCtx = {
    meta: data.meta, nodeById, knnN: KNN_N,
    onNavigate: m => focusNode(m),        // side-list click = same procedure as a node click
    onClose: () => resetFocus(),
  };

  // Focus+Context: a click simulates a RAG query
  G.onNodeClick(n => {
    if (state.mode === 'focus' && !isInFocusSet(n)) return;   // dimmed nodes ignored
    focusNode(n);
  });

  function isInFocusSet(n) {
    return n.id === state.focusNodeId || state.neighborIds.has(n.id);
  }

  function focusNode(n) {
    state.mode = 'focus';
    state.focusNodeId = n.id;
    state.neighborIds = new Set(n.neighbors.slice(0, KNN_N).map(nb => nb.id));
    applyState();

    // Camera: back off along the current viewing direction by the subgraph's
    // actual radius — semantic neighbors are not spatially compact (NOTES 4.2).
    const cam = G.cameraPosition();
    const spread = Math.max(60, ...[...state.neighborIds]
      .map(id => nodeById.get(id))
      .filter(Boolean)
      .map(m => Math.hypot(m.x - n.x, m.y - n.y, m.z - n.z)));
    const offset = spread * 3.0;      // vertical FOV 40° → r / tan(20°) ≈ 2.75r + margin
    const dx = cam.x - n.x, dy = cam.y - n.y, dz = cam.z - n.z;
    const len = Math.hypot(dx, dy, dz) || 1;
    G.cameraPosition({
      x: n.x + (dx / len) * offset,
      y: n.y + (dy / len) * offset,
      z: n.z + (dz / len) * offset,
    }, n, 1000);

    queryLabel.textContent =
      `Query: "${n.name}" → retrieved ${state.neighborIds.size} context documents`;
    queryLabel.style.display = 'block';
    openDetails(n, detailsCtx);
  }

  function resetFocus() {
    if (state.mode !== 'focus') return;
    state.mode = 'idle';
    state.focusNodeId = null;
    state.neighborIds.clear();
    applyState();
    G.cameraPosition(initialCameraPos, undefined, 1000);
    queryLabel.style.display = 'none';
    closeDetails();
  }

  // Exit paths: background click, Esc, panel ×, Reset button (in focus)
  G.onBackgroundClick(resetFocus);
  document.addEventListener('keydown', e => { if (e.key === 'Escape') resetFocus(); });
  document.getElementById('reset-camera').addEventListener('click', () => {
    if (state.mode === 'focus') resetFocus();
    else G.cameraPosition(initialCameraPos, undefined, 800);
  });

  // Every panel change goes through refresh() → applyState(). If a filter hides
  // the focused node, applyState() drops focus (algebra rule 3); here the
  // label, details panel and camera are synced to that.
  function refresh() {
    const wasFocus = state.mode === 'focus';
    applyState();
    if (wasFocus && state.mode !== 'focus') {
      queryLabel.style.display = 'none';
      closeDetails();
      G.cameraPosition(initialCameraPos, undefined, 1000);
    } else if (state.mode === 'focus') {
      openDetails(nodeById.get(state.focusNodeId), detailsCtx);   // reflect filters in the list
    }
    setEmptyState(data.nodes.filter(n => !state.hiddenClusters.has(n.cluster)).length);
    setEdgeCount(countVisibleLinks());
  }

  buildPanel(data.meta, data.nodes, refresh);
  buildSizeLegend(data.nodes);
  setEdgeCount(countVisibleLinks());
  initAbout();

  // Follow the viewport (projector resolutions differ from the laptop)
  window.addEventListener('resize', () => {
    G.width(window.innerWidth).height(window.innerHeight);
  });

  loadingEl.style.display = 'none';
}

init().catch(err => {
  loadingEl.textContent = `Init error: ${err.message}`;
  loadingEl.classList.add('error');
  console.error(err);
});