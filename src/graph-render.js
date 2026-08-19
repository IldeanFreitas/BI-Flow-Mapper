// ─── Render do grafo principal (aba "Mapa") ────────────────────────────────
// Dona da região do DOM #graphCanvas/#edgeLayer/#nodeDetails/#typeFilters.
// Padrão `render<Algo>()`: cada função é dona de uma região do DOM, chamada a
// partir de switchTab()/selectNode() (main.js) ou diretamente pelos handlers
// de evento definidos aqui.
//
// Ciclo com i18n.js: este módulo importa t()/typeLabels() de i18n.js, que por
// sua vez importa renderFilters()/renderGraph() daqui para setLocale(). Seguro
// — nenhuma das duas pontas chama a outra no nível superior do módulo, só
// dentro de corpos de função (ver nota em main.js).
import { escapeHtml } from "./dom-utils.js";
import { els, setSubtitle } from "./dom-refs.js";
import { state, layoutGraph, upstream, downstream, nodeMatchesSearch, labelForId, initials } from "./graph-model.js";
import { t, typeLabels } from "./i18n.js";
import { applyZoom } from "./zoom.js";

export function renderFilters() {
  els.typeFilters.innerHTML = "";
  Object.entries(typeLabels()).forEach(([type, label]) => {
    const item = document.createElement("label");
    item.innerHTML = `<input type="checkbox" ${state.enabledTypes.has(type) ? "checked" : ""} data-type="${type}" /> ${label}`;
    item.querySelector("input").addEventListener("change", (event) => {
      if (event.target.checked) state.enabledTypes.add(type);
      else state.enabledTypes.delete(type);
      renderGraph();
    });
    els.typeFilters.appendChild(item);
  });
}

// ─── Busca textual (G10) ────────────────────────────────────────────────────
// nodeMatchesSearch() mora em graph-model.js (função pura, sem DOM). Aqui só
// fica o fiapo que liga o <input> ao re-render debounced.

// hooks.renderGraph é o único ponto de indireção deste módulo: o callback do
// debounce chama através deste objeto mutável em vez do identificador
// `renderGraph` direto, para que testes possam interceptar/envolver a chamada
// (mesma técnica documentada em zoom.js).
export const hooks = { renderGraph };

// Debounce leve (180ms) para não re-renderizar o grafo a cada tecla digitada
// em modelos grandes. state.searchTerm é atualizado de imediato (refletido em
// runtime mesmo antes do render), só o renderGraph() é adiado.
const SEARCH_DEBOUNCE_MS = 180;
let searchDebounceTimer = null;

export function handleSearchInput(rawValue) {
  state.searchTerm = rawValue;
  if (searchDebounceTimer) clearTimeout(searchDebounceTimer);
  searchDebounceTimer = setTimeout(() => {
    searchDebounceTimer = null;
    hooks.renderGraph();
  }, SEARCH_DEBOUNCE_MS);
}

// ─── Fim Busca textual ──────────────────────────────────────────────────────

export function setGraph(graph, title, subtitle) {
  state.graph = layoutGraph(graph);
  state.selectedId = null;
  els.title.textContent = title;
  setSubtitle(subtitle);
  applyZoom(1); // G11 — cada novo grafo carregado começa em 100%, sem herdar zoom de um grafo anterior
  renderGraph();
}

export function renderGraph() {
  const graph = state.graph;
  const impactIds = state.selectedId ? downstream(state.selectedId, graph.edges) : new Set();

  // ── Modo Filtro de Linhagem ──────────────────────────────────────────────
  if (state.lineageFilter && state.selectedId) {
    const ancestorIds = upstream(state.selectedId, graph.edges);
    const lineageIds  = new Set([state.selectedId, ...ancestorIds, ...impactIds]);

    // Apenas nós da linhagem, que passam no filtro de tipo e no termo de busca (G10)
    const lineageNodes = graph.nodes.filter(
      (n) => lineageIds.has(n.id) && state.enabledTypes.has(n.type) && nodeMatchesSearch(n, state.searchTerm)
    );

    renderLineageGraph(lineageNodes, graph.edges, impactIds, ancestorIds);
    els.emptyState.classList.add("hidden");
    updateMetrics(impactIds);
    renderDetails();
    return;
  }

  // ── Modo Normal ─────────────────────────────────────────────────────────
  // G10 — além do filtro de tipo (checkbox), aplica o termo de busca textual
  const visibleNodes = graph.nodes.filter(
    (n) => state.enabledTypes.has(n.type) && nodeMatchesSearch(n, state.searchTerm)
  );
  const visibleIds   = new Set(visibleNodes.map((n) => n.id));

  // Re-pack the shared measure/calc_column column so there's no gap when
  // one type is hidden by the filter. Work on cloned positions so the
  // canonical layout (used by edge rendering) stays intact.
  const MEASURE_X = 42 + 3 * 250; // column index 3 = measure
  const sharedVisible = visibleNodes.filter(
    (n) => n.type === "measure" || n.type === "calc_column"
  );
  // Sort by their canonical y so relative order is preserved
  sharedVisible.sort((a, b) => a.y - b.y);
  const repacked = new Map(); // id → {x, y} overrides
  sharedVisible.forEach((n, row) => {
    repacked.set(n.id, { x: MEASURE_X, y: 42 + row * 120 });
  });

  // Apply overrides: mutate node positions temporarily for this render pass
  // (we restore after building cards and edges via a snapshot)
  const snapshot = new Map(
    graph.nodes
      .filter((n) => repacked.has(n.id))
      .map((n) => [n.id, { x: n.x, y: n.y }])
  );
  graph.nodes.forEach((n) => {
    if (repacked.has(n.id)) { n.x = repacked.get(n.id).x; n.y = repacked.get(n.id).y; }
  });

  // Recompute canvas height for the repacked column
  const maxVisibleRows = Math.max(
    1,
    ...["source","query","model","visual"].map(
      (t) => visibleNodes.filter((n) => n.type === t).length
    ),
    sharedVisible.length
  );
  const canvasH = Math.max(680, maxVisibleRows * 120 + 120);

  els.graphCanvas.innerHTML = "";
  els.graphCanvas.style.minWidth  = `${graph.width || 960}px`;
  els.graphCanvas.style.minHeight = `${canvasH}px`;
  els.edgeLayer.setAttribute("width",  graph.width || 960);
  els.edgeLayer.setAttribute("height", canvasH);
  els.edgeLayer.style.minWidth  = `${graph.width || 960}px`;
  els.edgeLayer.style.minHeight = `${canvasH}px`;

  visibleNodes.forEach((node) => {
    const card = buildNodeCard(node, impactIds);
    els.graphCanvas.appendChild(card);
  });



  renderEdges(
    graph.edges.filter((e) => visibleIds.has(e.from) && visibleIds.has(e.to)),
    graph.nodes,
    impactIds
  );

  // Restore canonical positions so lineage mode / exports are unaffected
  graph.nodes.forEach((n) => {
    if (snapshot.has(n.id)) { n.x = snapshot.get(n.id).x; n.y = snapshot.get(n.id).y; }
  });

  els.emptyState.classList.toggle("hidden", visibleNodes.length > 0);
  updateMetrics(impactIds);
  renderDetails();
}

// Renderiza apenas os nós da linhagem, reposicionados verticalmente por coluna
export function renderLineageGraph(lineageNodes, allEdges, impactIds, ancestorIds) {
  const CARD_W  = 220;
  const CARD_H  = 74;
  const GAP_X   = 250;
  const GAP_Y   = 100;  // compacto verticalmente
  const PAD     = 42;

  const order = ["source", "query", "model", "measure", "visual"];

  // Agrupa por coluna (tipo)
  const columns = new Map(order.map((t) => [t, []]));
  lineageNodes.forEach((n) => {
    const col = columns.get(n.type) || columns.get("measure"); // calc_column → measure col
    if (col) col.push(n);
  });

  // Posiciona cada nó na sua coluna com espaçamento compacto
  const positioned = lineageNodes.map((n) => ({ ...n })); // cópia para não mutar o grafo original
  const byId = new Map(positioned.map((n) => [n.id, n]));

  // First pass: position normal types
  columns.forEach((nodes, type) => {
    const colIdx = order.indexOf(type);
    // For measure column we'll do a second pass to interleave calc_column
    if (type !== "measure") {
      nodes.forEach((origNode, row) => {
        const n = byId.get(origNode.id);
        if (n) { n.x = PAD + colIdx * GAP_X; n.y = PAD + row * GAP_Y; }
      });
    }
  });

  // Second pass: measure column — measures first, then calc_columns
  const measureColIdx = order.indexOf("measure");
  const measureNodesInLineage = lineageNodes.filter((n) => n.type === "measure");
  const calcColNodesInLineage  = lineageNodes.filter((n) => n.type === "calc_column");
  [...measureNodesInLineage, ...calcColNodesInLineage].forEach((origNode, row) => {
    const n = byId.get(origNode.id);
    if (n) { n.x = PAD + measureColIdx * GAP_X; n.y = PAD + row * GAP_Y; }
  });

  const maxRows = Math.max(
    1,
    ...Array.from(columns.entries())
      .filter(([type]) => type !== "measure")
      .map(([, col]) => col.length),
    measureNodesInLineage.length + calcColNodesInLineage.length
  );
  const w = Math.max(960,  order.length * GAP_X + PAD * 2);
  const h = Math.max(400,  maxRows * GAP_Y + PAD * 2);

  els.graphCanvas.innerHTML = "";
  els.graphCanvas.style.minWidth  = `${w}px`;
  els.graphCanvas.style.minHeight = `${h}px`;
  els.edgeLayer.setAttribute("width",  w);
  els.edgeLayer.setAttribute("height", h);
  els.edgeLayer.style.minWidth  = `${w}px`;
  els.edgeLayer.style.minHeight = `${h}px`;

  const lineageIds = new Set(positioned.map((n) => n.id));

  positioned.forEach((node) => {
    const card = buildNodeCard(node, impactIds, ancestorIds);
    els.graphCanvas.appendChild(card);
  });

  renderEdges(
    allEdges.filter((e) => lineageIds.has(e.from) && lineageIds.has(e.to)),
    positioned,
    impactIds
  );
}

// Constrói um card de nó (extraído para reutilizar nos dois modos)
export function buildNodeCard(node, impactIds, ancestorIds = new Set()) {
  const card = document.createElement("button");
  card.type = "button";
  card.className = `node-card ${node.type}`;
  if (node.id === state.selectedId)  card.classList.add("selected");
  if (impactIds.has(node.id))        card.classList.add("impacted");
  if (ancestorIds.has(node.id))      card.classList.add("ancestor");
  if (
    state.selectedId &&
    node.id !== state.selectedId &&
    !impactIds.has(node.id) &&
    !state.lineageFilter          // no modo normal mantém dimmed
  ) {
    card.classList.add("dimmed");
  }
  card.style.left = `${node.x}px`;
  card.style.top  = `${node.y}px`;
  card.dataset.nodeId = node.id;
  // G8 — mantém a semântica nativa de <button>; a lista é role="list" no container (#graphCanvas)
  card.setAttribute("aria-pressed", node.id === state.selectedId ? "true" : "false");
  const iconText = escapeHtml(node.icon || initials(node.label));
  const iconUrl = node.iconUrl ? escapeHtml(node.iconUrl) : "";
  const iconMarkup = iconUrl
    ? `<span class="connector-icon has-image"><img src="${iconUrl}" alt="" loading="lazy" onerror="this.classList.add('hidden-icon')" /><span class="icon-fallback">${iconText}</span></span>`
    : `<span class="connector-icon"><span class="icon-fallback">${iconText}</span></span>`;
  card.innerHTML = `
    ${iconMarkup}
    <span>
      <span class="node-title">${escapeHtml(node.label)}</span>
      <span class="node-subtitle">${typeLabels()[node.type] || node.type}</span>
    </span>
  `;
  card.addEventListener("click", () => selectNode(node.id));
  return card;
}

export function renderEdges(edges, nodes, impactIds) {
  const byId = new Map(nodes.map((node) => [node.id, node]));
  const lines = edges.map((edgeItem) => {
    const from = byId.get(edgeItem.from);
    const to = byId.get(edgeItem.to);
    if (!from || !to) return "";
    const x1 = from.x + 220;
    const y1 = from.y + 37;
    const x2 = to.x;
    const y2 = to.y + 37;
    const mid = x1 + Math.max(40, (x2 - x1) / 2);
    const active = state.selectedId && (edgeItem.from === state.selectedId || impactIds.has(edgeItem.to));
    const stroke = active ? "#b23a48" : "#8c98a3";
    const width = active ? 3 : 2;
    return `<path d="M ${x1} ${y1} C ${mid} ${y1}, ${mid} ${y2}, ${x2} ${y2}" fill="none" stroke="${stroke}" stroke-width="${width}" marker-end="url(#arrow)" />`;
  });

  els.edgeLayer.innerHTML = `
    <defs>
      <marker id="arrow" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
        <path d="M 0 0 L 10 5 L 0 10 z" fill="#8c98a3"></path>
      </marker>
    </defs>
    ${lines.join("")}
  `;
}

export function selectNode(id) {
  state.selectedId = state.selectedId === id ? null : id;
  renderGraph();
}

export function renderDetails() {
  const node = state.graph.nodes.find((item) => item.id === state.selectedId);
  if (!node) {
    els.details.innerHTML = `<p>${t().detailsPlaceholder}</p>`;
    return;
  }

  const incoming = state.graph.edges.filter((edgeItem) => edgeItem.to === node.id).length;
  const affected = Array.from(downstream(node.id, state.graph.edges));
  const sample = node.meta.expression ? `<code>${escapeHtml(node.meta.expression.slice(0, 1200))}</code>` : "";

  els.details.innerHTML = `
    <h3>${escapeHtml(node.label)}</h3>
    <div class="node-meta">${typeLabels()[node.type] || node.type}</div>
    <p>${t().detailsDirectDeps} ${incoming}</p>
    <p>${t().detailsImpacted} ${affected.length}</p>
    ${affected.length ? `<p>${t().detailsAffects} ${affected.map((id) => escapeHtml(labelForId(id))).join(", ")}</p>` : ""}
    ${sample}
  `;
}

export function updateMetrics(impactIds) {
  els.sourceCount.textContent = state.graph.nodes.filter((node) => node.type === "source").length;
  els.queryCount.textContent = state.graph.nodes.filter((node) => node.type === "query").length;
  els.nodeCount.textContent = state.graph.nodes.length;
  els.impactCount.textContent = impactIds.size;
}

// Wireup dos eventos específicos deste módulo (filtros de tipo já são
// vinculados dentro de renderFilters() a cada render; aqui só o que precisa
// ser vinculado uma única vez) — chamado por main.js.bindEvents().
export function bindGraphEvents() {
  els.lineageToggle.addEventListener("change", () => {
    state.lineageFilter = els.lineageToggle.checked;
    if (!state.lineageFilter) state.selectedId = null;
    renderGraph();
  });

  // G10 — busca textual: debounced, ver handleSearchInput()
  els.nodeSearch.addEventListener("input", (event) => {
    handleSearchInput(event.target.value);
  });

  window.addEventListener("resize", () => renderGraph());
}
