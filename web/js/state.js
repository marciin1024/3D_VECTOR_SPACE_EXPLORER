// state.js — single app state + applyState() (task 4.1).
// RULE: no interaction touches the scene directly; mutate state, call applyState().
import { colorScale, tier, WIDTHS, radiusScale } from './scales.js';

export const state = {
  mode: 'idle',              // 'idle' | 'focus'
  focusNodeId: null,
  neighborIds: new Set(),
  hiddenClusters: new Set(),
  edgeView: 'both',          // 'both' | 'semantic' | 'structural'
  simThreshold: 0.35,        // set from meta.defaultThreshold at init
};

let G = null;
let nodeById = new Map();
export function bindGraph(graphInstance) {
  G = graphInstance;
  nodeById = new Map(G.graphData().nodes.map(n => [n.id, n]));
}

const isFocus = () => state.mode === 'focus';
const inFocusSet = id => id === state.focusNodeId || state.neighborIds.has(id);

// Single rule for node opacity — used both by applyState() and at mesh
// creation time (meshes are re-created when a hidden cluster is shown again)
export function nodeOpacity(n) {
  return !isFocus() || inFocusSet(n.id) ? 1.0 : 0.08;
}

// Single rule for node size: the query node is enlarged in focus mode so it
// stays visible at the hub of the star (short docs are tiny spheres)
export function nodeScale(n) {
  const r = radiusScale(n.tokens);
  return isFocus() && n.id === state.focusNodeId ? Math.max(r * 2, 6) : r;
}

const linkEnd = e => (typeof e === 'object' ? e.id : e);  // library replaces
// source/target with node objects (2.1 pitfall) — normalize both cases.

function nodeVisible(n) { return !state.hiddenClusters.has(n.cluster); }

function linkVisible(l) {
  const s = linkEnd(l.source), t = linkEnd(l.target);
  const sN = nodeById.get(s);
  const tN = nodeById.get(t);
  if (!sN || !tN || !nodeVisible(sN) || !nodeVisible(tN)) return false;

  // Focus mode: the query star bypasses threshold and edge-view filters —
  // it renders a retrieval result, not a graph subset (cluster hiding still
  // applies: algebra rule 1)
  if (isFocus()) {
    const onFocusPath = (s === state.focusNodeId && state.neighborIds.has(t)) ||
                        (t === state.focusNodeId && state.neighborIds.has(s));
    if (onFocusPath) return true;
  }

  // dual-typed edges (struct flag) count as structural in the structural view
  if (state.edgeView === 'semantic'   && l.type !== 'semantic') return false;
  if (state.edgeView === 'structural' && !(l.type === 'structural' || l.struct)) return false;
  // structural view shows the full category skeleton: the "same category"
  // relation is metadata, so the similarity threshold does not apply to it
  if (state.edgeView === 'structural') return true;
  return l.type === 'structural' || l.value >= state.simThreshold;
}

export function applyState() {
  // Focus rule: if the focused node got filtered out, drop focus (algebra rule 3)
  if (isFocus()) {
    const f = G.graphData().nodes.find(n => n.id === state.focusNodeId);
    if (!f || !nodeVisible(f)) {
      state.mode = 'idle'; state.focusNodeId = null; state.neighborIds.clear();
    }
  }

  G.nodeVisibility(n => nodeVisible(n));
  G.linkVisibility(l => linkVisible(l));

    // Node opacity + size via stored meshes (library keeps mesh in __threeObj).
  // Re-run on the next frame too: after a visibility change the library
  // re-creates meshes, which would otherwise miss this pass.
  const syncNodes = () => G.graphData().nodes.forEach(n => {
    const mesh = n.__threeObj;
    if (!mesh) return;
    mesh.material.opacity = nodeOpacity(n);
    mesh.scale.setScalar(nodeScale(n));
  });
  syncNodes();
  requestAnimationFrame(syncNodes);

  // Edge styling: re-set accessors to trigger a style recompute
  G.linkColor(l => {
    const s = linkEnd(l.source), t = linkEnd(l.target);
    if (isFocus()) {
      const onFocusPath = (s === state.focusNodeId && state.neighborIds.has(t)) ||
                          (t === state.focusNodeId && state.neighborIds.has(s));
      if (onFocusPath) return 'rgba(255,200,80,1.0)';       // highlighted query edges
      return l.type === 'structural' ? 'rgba(153,153,153,0.03)'
                                     : 'rgba(120,160,220,0.03)';
    }
    if (l.type === 'structural') return 'rgba(153,153,153,0.35)';
    const a = 0.15 + 0.65 * (l.value - 0.25) / 0.45;
    return `rgba(120,160,220,${a.toFixed(3)})`;
  });
  G.linkWidth(l => {
    const s = linkEnd(l.source), t = linkEnd(l.target);
    if (isFocus() && ((s === state.focusNodeId && state.neighborIds.has(t)) ||
                      (t === state.focusNodeId && state.neighborIds.has(s))))
      return WIDTHS[2];
    return l.type === 'structural' ? 0.4 : WIDTHS[tier(l.value)];
  });
}

export function countVisibleLinks() {
  return G.graphData().links.filter(linkVisible).length;
}