// ui.js — control panel (cluster legend + toggles, edge-type switch,
// similarity threshold slider with live edge counter; task 4.3),
// details-on-demand side panel (4.4), size legend, About overlay and
// empty state (5.2).
// Legends use the SAME colorScale / radiusScale as the spheres
// (single source of truth).
import { colorScale, radiusScale } from './scales.js';
import { state } from './state.js';

export function buildPanel(meta, nodes, onChange) {
  // --- Clusters: generated from meta.clusterLabels, never hardcoded ---
  const list = document.getElementById('cluster-list');
  const counts = d3.rollup(nodes, v => v.length, n => n.cluster);
  Object.entries(meta.clusterLabels)
    .sort((a, b) => Number(a[0]) - Number(b[0]))
    .forEach(([id, label]) => {
      const cl = Number(id);
      const row = document.createElement('label');
      row.className = 'cluster-row';

      const cb = document.createElement('input');
      cb.type = 'checkbox';
      cb.checked = true;
      cb.addEventListener('change', () => {
        if (cb.checked) state.hiddenClusters.delete(cl);
        else state.hiddenClusters.add(cl);
        onChange();
      });

      const swatch = document.createElement('span');
      swatch.className = 'swatch';
      swatch.style.background = colorScale(cl);

      const text = document.createElement('span');
      text.className = 'cluster-label';
      text.textContent = label;

      const count = document.createElement('span');
      count.className = 'cluster-count';
      count.textContent = counts.get(cl) ?? 0;

      row.append(cb, swatch, text, count);
      list.append(row);
    });

  // --- Edge type switch ---
  // The structural view ignores the similarity threshold (category relation is
  // metadata), so the slider is disabled there to avoid a "dead" control.
  const slider = document.getElementById('threshold');
  const hint = document.getElementById('threshold-hint');
  const syncSlider = () => {
    const structural = state.edgeView === 'structural';
    slider.disabled = structural;
    hint.style.display = structural ? 'block' : 'none';
  };
  document.querySelectorAll('input[name="edge-view"]').forEach(radio => {
    radio.addEventListener('change', () => {
      state.edgeView = radio.value;
      syncSlider();
      onChange();
    });
  });

  // --- Similarity threshold slider (range from the JSON contract) ---
  const valueEl = document.getElementById('threshold-value');
  slider.min = meta.minThreshold;
  slider.value = state.simThreshold;
  valueEl.textContent = state.simThreshold.toFixed(2);
  slider.addEventListener('input', () => {        // 'input', not 'change': live
    state.simThreshold = Number(slider.value);
    valueEl.textContent = state.simThreshold.toFixed(2);
    onChange();
  });

  // --- 5.2: empty-state "Reset filters" restores all panel controls ---
  document.getElementById('reset-filters').addEventListener('click', () => {
    state.hiddenClusters.clear();
    list.querySelectorAll('input[type="checkbox"]').forEach(cb => { cb.checked = true; });
    state.edgeView = 'both';
    document.querySelector('input[name="edge-view"][value="both"]').checked = true;
    state.simThreshold = meta.defaultThreshold;
    slider.value = state.simThreshold;
    valueEl.textContent = state.simThreshold.toFixed(2);
    syncSlider();
    onChange();
  });

  syncSlider();
}

export function setEdgeCount(n) {
  document.getElementById('edge-count').textContent = n;
}

// --- 4.4: details-on-demand side panel ---
// All document text goes in via textContent (20NG posts contain < > &).
export function openDetails(n, { meta, nodeById, knnN, onNavigate, onClose }) {
  const panel = document.getElementById('details');
  panel.replaceChildren();

  const close = document.createElement('button');
  close.className = 'details-close';
  close.textContent = '×';
  close.title = 'Close (Esc)';
  close.addEventListener('click', onClose);

  const title = document.createElement('h3');
  title.textContent = n.name;

  const metaRow = document.createElement('div');
  metaRow.className = 'details-meta';
  const swatch = document.createElement('span');
  swatch.className = 'swatch';
  swatch.style.background = colorScale(n.cluster);
  metaRow.append(swatch, document.createTextNode(
    ` ${meta.clusterLabels[n.cluster]} · ${n.category} · ${n.tokens} tokens`));

  const text = document.createElement('div');
  text.className = 'details-text';
  text.textContent = n.text + (n.truncated ? '\n\n[… text truncated]' : '');

  const heading = document.createElement('h4');
  heading.textContent = `Retrieved context — top ${knnN} by cosine similarity`;

  const list = document.createElement('ol');
  list.className = 'details-neighbors';
  n.neighbors.slice(0, knnN).forEach(nb => {
    const m = nodeById.get(nb.id);
    if (!m) return;
    const hidden = state.hiddenClusters.has(m.cluster);
    const li = document.createElement('li');
    li.className = hidden ? 'nb hidden' : 'nb';

    const sw = document.createElement('span');
    sw.className = 'swatch';
    sw.style.background = colorScale(m.cluster);
    const sim = document.createElement('span');
    sim.className = 'nb-sim';
    sim.textContent = nb.sim.toFixed(2);
    const t = document.createElement('span');
    t.className = 'nb-title';
    t.textContent = m.name;
    li.append(sw, sim, t);

    if (hidden) li.title = 'Cluster hidden by filter';
    else li.addEventListener('click', () => onNavigate(m));
    list.append(li);
  });

  panel.append(close, title, metaRow, text, heading, list);
  panel.scrollTop = 0;
  panel.classList.add('open');
}

export function closeDetails() {
  document.getElementById('details').classList.remove('open');
}

// --- 5.2: size legend (explicit, because size was the least-guessed channel
// in the 3.4 test: 3/5). Circles use the same radiusScale as the spheres. ---
export function buildSizeLegend(nodes) {
  const el = document.getElementById('size-legend');
  const toks = nodes.map(n => n.tokens).sort(d3.ascending);
  const picks = [toks[0], d3.quantile(toks, 0.5), toks[toks.length - 1]].map(Math.round);
  const PX = 2.2;                                    // scene units -> legend px
  const maxR = radiusScale(picks[2]) * PX;
  const svgNS = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(svgNS, 'svg');
  svg.setAttribute('width', 240);
  svg.setAttribute('height', maxR * 2 + 22);
  picks.forEach((t, i) => {
    const cx = 30 + i * 85;
    const c = document.createElementNS(svgNS, 'circle');
    c.setAttribute('cx', cx);
    c.setAttribute('cy', maxR);
    c.setAttribute('r', radiusScale(t) * PX);
    c.setAttribute('fill', '#9aa4ae');
    const label = document.createElementNS(svgNS, 'text');
    label.setAttribute('x', cx);
    label.setAttribute('y', maxR * 2 + 16);
    label.setAttribute('text-anchor', 'middle');
    label.textContent = `${t} words`;
    svg.append(c, label);
  });
  el.replaceChildren(svg);
}

// --- 5.2: About overlay — opens on the first visit, then via the button ---
export function initAbout() {
  const about = document.getElementById('about');
  const open = () => about.classList.add('open');
  const close = () => {
    about.classList.remove('open');
    try { localStorage.setItem('vse-about-seen', '1'); } catch { /* private mode */ }
  };
  document.getElementById('about-btn').addEventListener('click', open);
  document.getElementById('about-close').addEventListener('click', close);
  about.addEventListener('click', e => { if (e.target === about) close(); });
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && about.classList.contains('open')) close();
  });
  let seen = false;
  try { seen = localStorage.getItem('vse-about-seen') === '1'; } catch { /* ignore */ }
  if (!seen) open();
}

// --- 5.2: empty state when every cluster is hidden ---
export function setEmptyState(visibleNodeCount) {
  document.getElementById('empty-state').style.display =
    visibleNodeCount === 0 ? 'flex' : 'none';
}