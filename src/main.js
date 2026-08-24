// ─── Ponto de entrada ───────────────────────────────────────────────────────
// Único módulo carregado pelo <script type="module"> em index.html. Importa
// de todos os módulos de feature, define init()/bindEvents()/switchTab() (a
// única peça verdadeiramente cross-cutting — toca as 4 abas de uma vez) e
// dispara init() como efeito colateral de topo de arquivo, exatamente como
// `init();` fazia no fim do antigo app.js.
//
// Nota sobre os ciclos de import (i18n.js <-> graph-render.js/relationships.js/
// architecture.js/pages.js): são seguros porque nenhum dos módulos envolvidos
// chama uma função importada no seu próprio nível superior — só dentro de
// corpos de função, que só são executados depois que main.js (o último elo,
// que importa todo mundo) termina de instanciar o grafo de módulos inteiro e
// roda init(). Ver detalhe também nos comentários de topo de i18n.js e
// graph-render.js.
import { els } from "./dom-refs.js";
import { state } from "./graph-model.js";
import { setLocale, applyI18n } from "./i18n.js";
import { renderFilters, bindGraphEvents } from "./graph-render.js";
import { renderRelationships } from "./relationships.js";
import { renderArchitecture } from "./architecture.js";
import { renderPages } from "./pages.js";
import { renderInsights } from "./insights.js";
import { bindZoomEvents } from "./zoom.js";
import { loadDemo, loadLastPbix, bindUploadEvents, hooks as uploadHooks } from "./upload.js";
import { exportGraph, exportImage, exportDocumentation, exportHtmlDocumentation } from "./export.js";

export function init() {
  renderFilters();
  bindEvents();
  applyI18n();
  loadDemo();
}

export function bindEvents() {
  document.querySelectorAll(".lang-btn").forEach((btn) => {
    btn.addEventListener("click", () => setLocale(btn.dataset.lang));
  });
  bindLanguageKeyboardNavigation();

  bindUploadEvents(); // G9 — #pbixInput change + drag-and-drop em #uploadZone

  els.demoButton.addEventListener("click", loadDemo);
  els.pbixButton.addEventListener("click", loadLastPbix);
  els.exportButton.addEventListener("click", exportGraph);
  els.exportDocxButton.addEventListener("click", exportDocumentation);
  els.exportHtmlButton.addEventListener("click", exportHtmlDocumentation);

  els.tabMapa.addEventListener("click", () => switchTab("mapa"));
  els.tabRelacionamentos.addEventListener("click", () => switchTab("relacionamentos"));
  els.tabArquitetura.addEventListener("click", () => switchTab("arquitetura"));
  els.tabPaginas.addEventListener("click", () => switchTab("paginas"));
  els.tabInsights.addEventListener("click", () => switchTab("insights"));
  bindTabKeyboardNavigation();

  bindGraphEvents(); // lineageToggle change + busca textual (G10) + resize
  bindZoomEvents();  // botões de zoom + Ctrl/Cmd+scroll (G11)

  els.exportImageButton.addEventListener("click", exportImage);
}

function bindLanguageKeyboardNavigation() {
  const buttons = Array.from(document.querySelectorAll(".lang-btn"));
  buttons.forEach((button, currentIndex) => {
    button.addEventListener("keydown", (event) => {
      if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
      event.preventDefault();
      const offset = event.key === "ArrowRight" ? 1 : -1;
      const next = buttons[(currentIndex + offset + buttons.length) % buttons.length];
      setLocale(next.dataset.lang);
      next.focus();
    });
  });
}

function bindTabKeyboardNavigation() {
  const tabs = [els.tabMapa, els.tabRelacionamentos, els.tabArquitetura, els.tabPaginas, els.tabInsights];
  const names = ["mapa", "relacionamentos", "arquitetura", "paginas", "insights"];
  tabs.forEach((tab, currentIndex) => {
    tab.addEventListener("keydown", (event) => {
      let nextIndex = currentIndex;
      if (event.key === "ArrowRight") nextIndex = (currentIndex + 1) % tabs.length;
      else if (event.key === "ArrowLeft") nextIndex = (currentIndex - 1 + tabs.length) % tabs.length;
      else if (event.key === "Home") nextIndex = 0;
      else if (event.key === "End") nextIndex = tabs.length - 1;
      else return;
      event.preventDefault();
      switchTab(names[nextIndex]);
      tabs[nextIndex].focus();
    });
  });
}

export function switchTab(tab) {
  state.activeTab = tab;
  const isMapa            = tab === "mapa";
  const isRelacionamentos = tab === "relacionamentos";
  const isArquitetura     = tab === "arquitetura";
  const isPaginas         = tab === "paginas";
  const isInsights        = tab === "insights";

  els.tabMapa.classList.toggle("active", isMapa);
  els.tabRelacionamentos.classList.toggle("active", isRelacionamentos);
  els.tabArquitetura.classList.toggle("active", isArquitetura);
  els.tabPaginas.classList.toggle("active", isPaginas);
  els.tabInsights.classList.toggle("active", isInsights);
  els.tabMapa.setAttribute("aria-selected", isMapa ? "true" : "false");
  els.tabRelacionamentos.setAttribute("aria-selected", isRelacionamentos ? "true" : "false");
  els.tabArquitetura.setAttribute("aria-selected", isArquitetura ? "true" : "false");
  els.tabPaginas.setAttribute("aria-selected", isPaginas ? "true" : "false");
  els.tabInsights.setAttribute("aria-selected", isInsights ? "true" : "false");
  els.tabMapa.tabIndex = isMapa ? 0 : -1;
  els.tabRelacionamentos.tabIndex = isRelacionamentos ? 0 : -1;
  els.tabArquitetura.tabIndex = isArquitetura ? 0 : -1;
  els.tabPaginas.tabIndex = isPaginas ? 0 : -1;
  els.tabInsights.tabIndex = isInsights ? 0 : -1;

  els.panelMapa.classList.toggle("hidden", !isMapa);
  els.panelRelacionamentos.classList.toggle("hidden", !isRelacionamentos);
  els.panelArquitetura.classList.toggle("hidden", !isArquitetura);
  els.panelPaginas.classList.toggle("hidden", !isPaginas);
  els.panelInsights.classList.toggle("hidden", !isInsights);
  els.mapLegend.style.visibility = isMapa ? "visible" : "hidden";

  if (isRelacionamentos) renderRelationships();
  if (isArquitetura) renderArchitecture();
  if (isPaginas) renderPages();
  if (isInsights) renderInsights();
}

init();

// ─── Superfície re-exportada para os testes (tests/frontend/) ──────────────
// Cada módulo é dono do seu pedaço de DOM/estado; main.js reexporta o que os
// testes precisam acessar depois de `await import("../../src/main.js")`
// (ver tests/frontend/setup.js). Os objetos `*Hooks` são o ponto de
// indireção usado por spies (ver comentário em graph-render.js/zoom.js/
// upload.js) — substituem o antigo truque de reatribuir `dom.window.fn`.
export { state, nodeMatchesSearch, upstream, downstream, layoutGraph, buildGraphIndex } from "./graph-model.js";
export { els, setSubtitle, setLoading } from "./dom-refs.js";
export { setLocale, applyI18n, t, locale, I18N } from "./i18n.js";
export {
  renderGraph,
  renderDetails,
  selectNode,
  setGraph,
  handleSearchInput,
  hooks as searchHooks,
} from "./graph-render.js";
export {
  computeFitScale,
  clampZoom,
  applyZoom,
  zoomIn,
  zoomOut,
  fitGraph,
  hooks as zoomHooks,
} from "./zoom.js";
export { loadLastPbix, loadPbix, loadPbipFolder, filterTmdlFiles, buildTmdlFormData } from "./upload.js";
export { loadDemo, uploadHooks };
export { exportGraph, exportImage, exportDocumentation, exportHtmlDocumentation } from "./export.js";
export { renderRelationships } from "./relationships.js";
export { renderArchitecture } from "./architecture.js";
export { renderPages } from "./pages.js";
export { renderInsights } from "./insights.js";
export { localMetricsEnabled, readLocalMetrics } from "./local-metrics.js";
