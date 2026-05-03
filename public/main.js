const API = 'https://api-production-f255.up.railway.app';

const TISSUES = [
  'adipose tissue', 'adrenal gland', 'amygdala', 'appendix', 'basal ganglia',
  'blood vessel', 'bone marrow', 'breast', 'cerebellum', 'cerebral cortex', 'cervix',
  'choroid plexus', 'colon', 'duodenum', 'endometrium', 'epididymis', 'esophagus',
  'fallopian tube', 'gallbladder', 'heart muscle', 'hippocampal formation', 'hypothalamus',
  'kidney', 'liver', 'lung', 'lymph node', 'midbrain', 'ovary', 'pancreas', 'parathyroid gland',
  'pituitary gland', 'placenta', 'prostate', 'rectum', 'retina', 'salivary gland', 'seminal vesicle',
  'skeletal muscle', 'skin', 'small intestine', 'smooth muscle', 'spinal cord', 'spleen', 'stomach',
  'testis', 'thymus', 'thyroid gland', 'tongue', 'tonsil', 'urinary bladder', 'vagina'
];

// ── State ─────────────────────────────────────────────────────────────────────
let cy   = null;
let busy = false;

// ── UI helpers ────────────────────────────────────────────────────────────────
function setError(msg) {
  const el = document.getElementById('error-bar');
  el.textContent = msg;
  el.style.display = msg ? 'block' : 'none';
}

function toast(msg, ms = 1400) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.classList.add('visible');
  clearTimeout(el._tid);
  el._tid = setTimeout(() => el.classList.remove('visible'), ms);
}

function setStats() {
  document.getElementById('stat-nodes').textContent = cy.nodes().length;
  document.getElementById('stat-edges').textContent = cy.edges().length;
}

function setDetail(html) {
  document.getElementById('detail-content').innerHTML = html;
}

// ── Element builders ──────────────────────────────────────────────────────────
function nodeEl(n) {
  return {
    group: 'nodes',
    data: {
      id:           n.id,
      label:        n.label || n.id,
      x:            n.x,
      y:            n.y,
      is_clique:    n.is_clique === true,
      clique_type:  n.clique_type  ?? null,
      member_count: n.member_count ?? null,
      expression:   n.expression   ?? null,
      diseases:     n.diseases     ?? [],
    },
    position: { x: n.x * 1000, y: n.y * 1000 },
  };
}

function edgeEl(e) {
  return {
    group: 'edges',
    data: {
      id:          `${e.source_id}__${e.target_id}`,
      source:      e.source_id,
      target:      e.target_id,
      weight:      e.weight,
      is_boundary: e.is_boundary === true,
    },
  };
}

function apiToElements(data) {
  return [...data.nodes.map(nodeEl), ...data.edges.map(edgeEl)];
}

// ── API ───────────────────────────────────────────────────────────────────────
async function fetchTop() {
  const r = await fetch(`${API}/graph/top`);
  if (!r.ok) throw new Error(`/graph/top → ${r.status}`);
  return r.json();
}

async function fetchExpand(id) {
  const r = await fetch(`${API}/graph/expand/${encodeURIComponent(id)}`);
  if (!r.ok) throw new Error(`/graph/expand → ${r.status}`);
  return r.json();
}

async function fetchParent(id) {
  const r = await fetch(`${API}/graph/parent/${encodeURIComponent(id)}`);
  if (!r.ok) throw new Error(`/graph/parent → ${r.status}`);
  return r.json();
}

async function getSuggestions(query) {
  const r = await fetch(`${API}/search/disease/suggest?query=${encodeURIComponent(query)}`);
  return r.ok ? r.json() : [];
}

async function findDiseaseNodes(diseaseName) {
  const r = await fetch(`${API}/search/disease/find?disease_name=${encodeURIComponent(diseaseName)}`);
  if (!r.ok) throw new Error('Search failed');
  return r.json();
}

// ── Highlights ────────────────────────────────────────────────────────────────
function clearAll() {
  cy.elements().removeClass(
    'search-hit search-clique-hit search-dim nbr-focus nbr-hit nbr-edge nbr-dim'
  );
}

function highlightNeighborhood(node) {
  clearAll();
  const nbrs = node.neighborhood();
  cy.elements().addClass('nbr-dim');
  node.removeClass('nbr-dim').addClass('nbr-focus');
  nbrs.nodes().removeClass('nbr-dim').addClass('nbr-hit');
  nbrs.edges().removeClass('nbr-dim').addClass('nbr-edge');
}

function highlightNodes(cliqueIds) {
  clearAll();
  const targets = cy.nodes().filter(n => cliqueIds.includes(n.id()));
  if (targets.length) {
    cy.elements().addClass('search-dim');
    targets.removeClass('search-dim').addClass('search-clique-hit');
    cy.animate({ fit: { eles: targets, padding: 50 }, duration: 400 });
  }
  return targets.length;
}

// ── Gene search ───────────────────────────────────────────────────────────────
function initGeneSearch() {
  const input     = document.getElementById('gene-search-input');
  const statusEl  = document.getElementById('gene-search-status');

  async function run(raw) {
    const query = raw.trim();
    if (!query) { clearAll(); statusEl.textContent = ''; return; }

    statusEl.textContent = 'searching…';
    try {
      const data = await fetchParent(query);
      if (data.clique?.id) {
        const target = cy.getElementById(data.clique.id);
        if (target.length) {
          clearAll();
          cy.elements().addClass('search-dim');
          target.removeClass('search-dim').addClass('search-clique-hit');
          cy.animate({ fit: { eles: target, padding: 80 }, duration: 400 });
          statusEl.textContent = `found: ${data.clique.id}`;
        } else {
          statusEl.textContent = 'not in current view';
        }
        return;
      }
    } catch (e) {
      // not a clique/parent — try as a leaf node
    }

    // fallback: search visible nodes by label/id
    const lc = query.toLowerCase();
    const matches = cy.nodes().filter(n =>
      n.id().toLowerCase().includes(lc) ||
      (n.data('label') || '').toLowerCase().includes(lc)
    );

    if (matches.length) {
      clearAll();
      cy.elements().addClass('search-dim');
      matches.removeClass('search-dim').addClass('search-hit');
      cy.animate({ fit: { eles: matches, padding: 50 }, duration: 400 });
      statusEl.textContent = `${matches.length} match${matches.length > 1 ? 'es' : ''}`;
    } else {
      statusEl.textContent = 'not found';
      clearAll();
    }
  }

  document.getElementById('gene-search-btn').addEventListener('click', () => run(input.value));
  document.getElementById('gene-search-clear').addEventListener('click', () => {
    input.value = '';
    clearAll();
    statusEl.textContent = '';
    input.focus();
  });
  input.addEventListener('keydown', e => { if (e.key === 'Enter') run(input.value); });
}

// ── Disease search ────────────────────────────────────────────────────────────
function initDiseaseSearch() {
  const input    = document.getElementById('disease-search-input');
  const statusEl = document.getElementById('disease-search-status');
  const dropdown = document.getElementById('disease-search-dropdown');

  // Autocomplete
  input.addEventListener('input', async (e) => {
    const val = e.target.value;
    if (val.length < 2) { dropdown.style.display = 'none'; return; }

    const suggestions = await getSuggestions(val);
    if (!suggestions.length) { dropdown.style.display = 'none'; return; }

    dropdown.innerHTML = suggestions
      .map(s => `<div class="option">${s}</div>`)
      .join('');
    dropdown.style.display = 'block';
  });

  // Click a suggestion
  dropdown.addEventListener('click', async (e) => {
    if (!e.target.classList.contains('option')) return;
    input.value = e.target.textContent;
    dropdown.style.display = 'none';
    await run(input.value);
  });

  // Close dropdown when clicking outside
  document.addEventListener('click', (e) => {
    if (!e.target.closest('#disease-search-section')) {
      dropdown.style.display = 'none';
    }
  });

  async function run(raw) {
    const query = raw.trim();
    if (!query) { clearAll(); statusEl.textContent = ''; return; }

    statusEl.textContent = 'searching…';
    try {
      const result = await findDiseaseNodes(query);
      if (result.associated_cliques?.length) {
        const found = highlightNodes(result.associated_cliques);
        statusEl.textContent = found
          ? `${found} cluster${found > 1 ? 's' : ''} found`
          : 'no visible clusters match';
      } else {
        statusEl.textContent = 'no results';
        clearAll();
      }
    } catch (err) {
      statusEl.textContent = 'search failed';
      clearAll();
    }
  }

  document.getElementById('disease-search-btn').addEventListener('click', () => run(input.value));
  document.getElementById('disease-search-clear').addEventListener('click', () => {
    input.value = '';
    dropdown.style.display = 'none';
    clearAll();
    statusEl.textContent = '';
    input.focus();
  });
  input.addEventListener('keydown', e => {
    if (e.key === 'Enter') { dropdown.style.display = 'none'; run(input.value); }
    if (e.key === 'Escape') { dropdown.style.display = 'none'; }
  });
}

// ── Expand clique ─────────────────────────────────────────────────────────────
async function expandClique(node) {
  if (busy) return;
  busy = true;
  const cliqueId = node.id();
  node.addClass('expanding');
  toast('expanding…');

  try {
    const data = await fetchExpand(cliqueId);
    const expandedIds = new Set(data.nodes.map(n => n.id));

    // Record external neighbors before removing the clique node
    const external = [];
    node.connectedEdges().forEach(e => {
      const otherId = e.source().id() === cliqueId ? e.target().id() : e.source().id();
      if (!expandedIds.has(otherId)) {
        external.push({ otherId, weight: e.data('weight'), is_boundary: e.data('is_boundary') });
      }
    });

    cy.remove(node);

    // New nodes
    cy.add(data.nodes.filter(n => !cy.getElementById(n.id).length).map(nodeEl));

    // Internal edges
    cy.add(
      data.edges
        .filter(e => !e.is_boundary)
        .filter(e => !cy.getElementById(`${e.source_id}__${e.target_id}`).length)
        .map(edgeEl)
    );

    // Boundary edges (only if the other end is already visible)
    cy.add(
      data.edges
        .filter(e => e.is_boundary)
        .filter(e => cy.getElementById(e.target_id).length)
        .filter(e => !cy.getElementById(`${e.source_id}__${e.target_id}`).length)
        .map(edgeEl)
    );

    // Re-attach external edges to the geometrically closest new node
    external.forEach(({ otherId, weight, is_boundary }) => {
      const other = cy.getElementById(otherId);
      if (!other.length) return;
      const op = other.position();
      let closestId = null, closestDist = Infinity;
      data.nodes.forEach(n => {
        const el = cy.getElementById(n.id);
        if (!el.length) return;
        const d = Math.hypot(el.position().x - op.x, el.position().y - op.y);
        if (d < closestDist) { closestDist = d; closestId = n.id; }
      });
      if (!closestId) return;
      const fwd = `${closestId}__${otherId}`;
      const rev = `${otherId}__${closestId}`;
      if (!cy.getElementById(fwd).length && !cy.getElementById(rev).length) {
        cy.add({ group: 'edges', data: { id: fwd, source: closestId, target: otherId, weight, is_boundary } });
      }
    });

    setStats();
    toast(`+${data.nodes.length} nodes`);
  } catch (err) {
    setError(`expand failed: ${err.message}`);
  } finally {
    busy = false;
  }
}

// ── Repack clique ─────────────────────────────────────────────────────────────
async function repackClique(node) {
  if (busy) return;
  busy = true;
  toast('repacking…');

  try {
    const data    = await fetchParent(node.id());
    const parent  = data.clique;
    const members = new Set(data.member_ids);

    // Collect external connections before removal
    const external = [];
    cy.nodes().filter(n => members.has(n.id())).connectedEdges().forEach(e => {
      const srcIn = members.has(e.source().id());
      const tgtIn = members.has(e.target().id());
      if (srcIn !== tgtIn) {
        external.push({
          otherId:     srcIn ? e.target().id() : e.source().id(),
          weight:      e.data('weight'),
          is_boundary: e.data('is_boundary'),
        });
      }
    });

    cy.remove(cy.nodes().filter(n => members.has(n.id())));

    cy.add({
      group: 'nodes',
      data: {
        id: parent.id, label: parent.id,
        x: parent.x,  y: parent.y,
        is_clique:    true,
        clique_type:  parent.clique_type  ?? null,
        member_count: parent.member_count ?? null,
        expression:   parent.expression   ?? null,
        diseases:     [],
      },
      position: { x: parent.x * 1000, y: parent.y * 1000 },
    });

    external.forEach(({ otherId, weight, is_boundary }) => {
      const id = `${parent.id}__${otherId}`;
      if (!cy.getElementById(id).length) {
        cy.add({ group: 'edges', data: { id, source: parent.id, target: otherId, weight, is_boundary } });
      }
    });

    setStats();
    toast('repacked');
  } catch (err) {
    setError(`repack failed: ${err.message}`);
  } finally {
    busy = false;
  }
}

// ── Detail panel ──────────────────────────────────────────────────────────────
function renderDetail(node) {
  const n = node.data();

  const exprSummary = arr => {
    if (!arr?.length) return '—';
    const vals = arr.filter(v => v != null);
    if (!vals.length) return '—';
    const avg = vals.reduce((a, b) => a + b, 0) / vals.length;
    return `avg ${avg.toFixed(2)} · min ${Math.min(...vals).toFixed(2)} · max ${Math.max(...vals).toFixed(2)}`;
  };

  const exprRows = arr => {
    if (!arr?.length) return '<div class="muted">no data</div>';
    return arr
      .map((v, i) => ({ name: TISSUES[i] ?? `[${i}]`, val: v != null ? Number(v) : null }))
      .sort((a, b) => (b.val ?? -Infinity) - (a.val ?? -Infinity))
      .map(({ name, val }) => `
        <div class="expr-row">
          <span>${name}</span>
          <strong>${val != null ? val.toFixed(2) : '—'}</strong>
        </div>`).join('');
  };

  const diseaseRows = list => {
    if (!list?.length) return '<div class="muted">no associations</div>';
    return list.map(d => `
      <div class="disease-row">
        <span class="disease-name">${d.disease_name}</span>
        <span class="disease-p">p = ${d.p_value.toExponential(2)}</span>
      </div>`).join('');
  };

  setDetail(`
    ${n.is_clique ? `<div class="clique-badge">${n.clique_type || 'CLIQUE'} · ${n.member_count ?? '?'} members</div>` : ''}
    <div class="kv"><span>id</span><span class="val mono">${n.id.slice(0, 20)}</span></div>
    <div class="kv"><span>label</span><span class="val">${(n.label || '—').slice(0, 18)}</span></div>
    <div class="kv"><span>degree</span><span class="val">${node.degree()}</span></div>
    <div class="kv"><span>expr</span><span class="val small">${exprSummary(n.expression)}</span></div>
    <div class="section-head">Disease associations</div>
    <div class="disease-list">${diseaseRows(n.diseases)}</div>
    <div class="section-head">Expression by tissue</div>
    <div class="expr-list">${exprRows(n.expression)}</div>
    <div class="hint">${n.is_clique ? '▸ double-click to expand' : '▸ right-click to repack'}</div>
  `);
}

// ── Cytoscape init ────────────────────────────────────────────────────────────
function initCy(elements) {
  cy = cytoscape({
    container: document.getElementById('cy'),
    elements,
    layout: { name: 'preset' },
    wheelSensitivity: 0.3,
    minZoom: 0.01,
    maxZoom: 20,
    style: [
      {
        selector: 'node',
        style: {
          width: 18, height: 18,
          'background-color': '#4a9eff',
          'border-width': 0,
          label: '',
          'transition-property': 'background-color, border-color, width, height, opacity',
          'transition-duration': '150ms',
        },
      },
      {
        selector: 'node[?is_clique]',
        style: {
          width:  'mapData(member_count, 2, 12, 12, 30)',
          height: 'mapData(member_count, 2, 12, 12, 30)',
          'background-color': '#00e5ff',
          'border-width': 1.5,
          'border-color': '#00e5ff55',
          'shadow-blur': 8,
          'shadow-color': '#00e5ff',
          'shadow-opacity': 0.5,
          'shadow-offset-x': 0, 'shadow-offset-y': 0,
          cursor: 'pointer',
        },
      },
      { selector: 'node.expanding',  style: { opacity: 0.25 } },
      { selector: 'node:selected',   style: { 'border-width': 2, 'border-color': '#fff', 'background-color': '#fff' } },
      {
        selector: 'edge',
        style: {
          width: 'mapData(weight, 0, 5, 0.4, 2)',
          'line-color': '#1e3a4a',
          opacity: 0.6,
          'curve-style': 'straight',
        },
      },
      {
        selector: 'edge[?is_boundary]',
        style: { 'line-color': '#ff6b35', opacity: 0.3, 'line-style': 'dashed', 'line-dash-pattern': [4, 4] },
      },
      { selector: 'node.search-hit',
        style: { 'background-color': '#ffe040', 'border-width': 2.5, 'border-color': '#ffcc00', 'z-index': 999 } },
      { selector: 'node.search-clique-hit',
        style: { 'background-color': '#ffe040', 'border-width': 3, 'border-color': '#ff9900',
                 'shadow-blur': 14, 'shadow-color': '#ffcc00', 'shadow-opacity': 0.9,
                 'shadow-offset-x': 0, 'shadow-offset-y': 0, 'z-index': 999 } },
      { selector: 'node.search-dim, edge.search-dim', style: { opacity: 0.08 } },
      { selector: 'node.nbr-focus',
        style: { 'border-width': 2.5, 'border-color': '#fff', 'background-color': '#fff', 'z-index': 999 } },
      { selector: 'node.nbr-hit',
        style: { 'background-color': '#4aff91', 'border-width': 1.5, 'border-color': '#00ff6a', 'z-index': 998 } },
      { selector: 'edge.nbr-edge',
        style: { 'line-color': '#4aff91', opacity: 0.9, width: 1.5, 'z-index': 997 } },
      { selector: 'node.nbr-dim, edge.nbr-dim', style: { opacity: 0.06 } },
    ],
  });

  setStats();

  cy.on('tap', 'node', evt => {
    highlightNeighborhood(evt.target);
    renderDetail(evt.target);
  });

  cy.on('dbltap', 'node', evt => {
    if (evt.target.data('is_clique') === true) expandClique(evt.target);
  });

  cy.on('cxttap', 'node', evt => {
    repackClique(evt.target);
  });

  cy.on('tap', evt => {
    if (evt.target !== cy) return;
    clearAll();
    setDetail('<span class="muted">click a node</span>');
    document.getElementById('gene-search-status').textContent = '';
    document.getElementById('disease-search-status').textContent = '';
  });
}

// ── Boot ──────────────────────────────────────────────────────────────────────
(async () => {
  try {
    const data = await fetchTop();
    initCy(apiToElements(data));
    document.getElementById('loading').style.display = 'none';
  } catch (err) {
    document.getElementById('loading').style.display = 'none';
    setError(`failed to load: ${err.message}`);
    return;
  }

  initGeneSearch();
  initDiseaseSearch();

  document.getElementById('fit-btn').addEventListener('click', () => cy.fit(undefined, 40));
})();