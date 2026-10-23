// scales.js — ALL D3 scales and visual constants in one module (task 3.1).
// No magic numbers in rendering code: Phase 3/4 and report §3 refer here.
// d3 is global (CDN script in index.html).

// Color: cluster id -> Tableau10 (color-blind-safe, categorical; Ware: color
// is the fastest pre-attentive channel for categorical discrimination).
export const colorScale = d3.scaleOrdinal(d3.schemeTableau10);

// Size: token count -> sphere radius via sqrt, so perceived AREA scales
// linearly with the underlying value (Cleveland & McGill).
export const radiusScale = d3.scaleSqrt().range([2, 8]); // domain set from data

export function initScales(nodes) {
  radiusScale.domain(d3.extent(nodes, n => n.tokens));
}

// Edge tiers — recalibrated to the empirical similarity range 0.25–0.7
// (NOTES 1.5), replacing the proposal's a priori 0.6/0.7/0.85.
export const TIERS  = [0.35, 0.45, 0.55];
export const WIDTHS = [0.5, 1.2, 2.5];

export function tier(value) {          // -> 0 | 1 | 2
  if (value >= TIERS[2]) return 2;
  if (value >= TIERS[1]) return 1;
  return 0;
}