// ─── Internationalisation ─────────────────────────────────────────────────────
// Único dicionário com todas as strings por chave, EN + PT-BR (ver skill
// `biflowmapper-i18n`). Toda string nova visível ao usuário entra aqui —
// nunca hardcode texto direto num template.
//
// Este módulo forma um ciclo de import com graph-render.js/relationships.js/
// architecture.js/pages.js (setLocale() precisa re-renderizar todas as abas).
// É seguro: nenhum desses módulos chama uma função importada no seu próprio
// nível superior — só dentro de corpos de função executados depois que todo
// o grafo de módulos já terminou de ser avaliado (ver comentário em main.js).
import { els, setSubtitle } from "./dom-refs.js";
import { state, TYPE_LABELS_KEYS } from "./graph-model.js";
import { renderFilters, renderGraph } from "./graph-render.js";
import { renderRelationships } from "./relationships.js";
import { renderArchitecture } from "./architecture.js";
import { renderPages } from "./pages.js";

export const I18N = {
  "en-US": {
    // Sidebar brand
    appSubtitle: "Power BI lineage explorer",

    // Upload zone
    uploadTitle: "Select PBIX",
    uploadCopy: "The file is analysed locally in the browser.",

    // Toolbar buttons
    btnDemo: "Demo",
    btnDemoTitle: "Load demo",
    btnPbix: "PBIX",
    btnPbixTitle: "Return to loaded PBIX",
    btnJson: "JSON",
    btnJsonTitle: "Export JSON",
    btnPng: "Export image",
    btnPngTitle: "Export PNG image",
    btnDocx: "Export documentation",
    btnDocxTitle: "Export Word documentation",
    docxNoPbix: "Load a PBIX file before exporting documentation.",
    docxGenerating: "Generating documentation...",
    docxError: "Could not export the documentation. See console for details.",

    // Summary panel
    panelSummary: "Summary",
    metricSources: "Sources",
    metricQueries: "Queries",
    metricNodes: "Nodes",
    metricImpact: "Impact",

    // Filters panel
    panelFilters: "Filters",
    filterSearchLabel: "Search",
    filterSearchPlaceholder: "Name, DAX or M expression…",

    // Lineage panel
    panelLineage: "Lineage",
    lineageToggleStrong: "Filter by lineage",
    lineageToggleSpan: "Click a node to see its full lineage only",

    // Details panel
    panelDetails: "Details",
    detailsPlaceholder: "Select a node to see its origin, dependencies and impact.",

    // Workspace header
    workspaceTitle: "Lineage Map",
    workspaceSubtitle: "Load a PBIX or use the demo to get started.",

    // Tabs
    tabMap: "Map",
    tabRelationships: "Relationships",
    tabArchitecture: "Architecture",
    tabPages: "Pages",

    // Legend
    legendSource: "Source",
    legendQuery: "Query",
    legendModel: "Model",
    legendMeasure: "Measure",
    legendCalcColumn: "Calc. Column",
    legendVisual: "Visual",
    // Empty states
    emptyTitle: "Start with your PBIX file",
    emptyBody: "The app detects connectors, queries, tables and report signals when this information exists in the package.",
    relEmptyTitle: "No relationships found",
    relEmptyBody: "Load a PBIX file analysed by the backend to see model relationships.",

    archEmptyTitle: "No data sources found",
    archEmptyBody: "Load a PBIX file to see the connection architecture diagram.",
    pagesEmptyTitle: "No pages found",
    pagesEmptyBody: "Load a PBIX file to see the report pages.",
    pagesVisualsLabel: (n) => `${n} visual${n !== 1 ? "s" : ""}`,
    pagesCanvasLabel: (w, h) => `${w} × ${h} px`,
    archPbiLabel: "Power BI Dataset",
    archNoQueries: "No queries mapped",
    archSourcesCount: (n) => `${n} data source${n !== 1 ? "s" : ""} connected`,

    // Node type labels
    typeSource: "Source",
    typeQuery: "Query",
    typeModel: "Model",
    typeMeasure: "Measure",
    typeCalcColumn: "Calc. Column",
    typeVisual: "Visual",

    // Details panel content
    detailsDirectDeps: "Direct dependencies:",
    detailsImpacted: "Impacted nodes:",
    detailsAffects: "Affects:",

    // Relationship table headers
    relFromTable: "Source Table",
    relFromCol: "Source Column",
    relToTable: "Target Table",
    relToCol: "Target Column",
    relCardinality: "Cardinality",
    relCrossFilter: "Cross Filter",
    relActive: "Active",
    relInactive: "Inactive",
    relTableAriaLabel: "Relationships table",
    relNoData: "No relationships available.",

    // Loading / error messages
    loadingAnalysing: (name) => `Analysing ${name}…`,
    loadingNoBackend: "No entries found in package.",
    loadingError: "Could not read this PBIX. See console for details.",
    loadingEntries: (n, extra) => `${n} entries read from PBIX package${extra}.`,
    loadingNestedExtra: (n) => ` + ${n} internal DataMashup entries`,

    // Export image footer
    exportTimestamp: () => new Date().toLocaleString("en-US"),

    // Demo data
    demoTitle: "Demo Lineage",
    demoSubtitle: "Demo with sources, queries, model, measures and visuals.",
    demoQuery1Expr: "Sql.Database(...) with fiscal calendar merge",
    demoQuery2Expr: "Excel.Workbook(...) for monthly targets",
    demoQuery3Expr: "Web.Contents(...) for exchange rates",
    demoCross1: "Single",
    demoCross2: "Bidirectional",
    demoCross3: "Single",
    demoCross4: "Single",
    demoCross5: "Single",

    // Language toggle
    langToggleLabel: "Language",

    // Zoom controls (G11)
    zoomInLabel: "Zoom in",
    zoomOutLabel: "Zoom out",
    zoomFitLabel: "Fit to screen",
    zoomControlsLabel: "Zoom controls",
  },

  "pt-BR": {
    appSubtitle: "Power BI lineage explorer",

    uploadTitle: "Selecionar PBIX",
    uploadCopy: "O arquivo é analisado localmente no navegador.",

    btnDemo: "Exemplo",
    btnDemoTitle: "Carregar exemplo",
    btnPbix: "PBIX",
    btnPbixTitle: "Voltar ao PBIX carregado",
    btnJson: "JSON",
    btnJsonTitle: "Exportar JSON",
    btnPng: "Exportar imagem",
    btnPngTitle: "Exportar imagem PNG",
    btnDocx: "Exportar documentacao",
    btnDocxTitle: "Exportar documentacao Word",
    docxNoPbix: "Carregue um arquivo PBIX antes de exportar a documentacao.",
    docxGenerating: "Gerando documentacao...",
    docxError: "Nao foi possivel exportar a documentacao. Veja o console para detalhes.",

    panelSummary: "Resumo",
    metricSources: "Fontes",
    metricQueries: "Queries",
    metricNodes: "Nós",
    metricImpact: "Impacto",

    panelFilters: "Filtros",
    filterSearchLabel: "Buscar",
    filterSearchPlaceholder: "Nome, DAX ou expressão M…",

    panelLineage: "Linhagem",
    lineageToggleStrong: "Filtrar por linhagem",
    lineageToggleSpan: "Clique em um nó para ver apenas a sua linhagem completa",

    panelDetails: "Detalhes",
    detailsPlaceholder: "Selecione um nó para ver origem, dependências e impacto.",

    workspaceTitle: "Lineage Map",
    workspaceSubtitle: "Carregue um PBIX ou use o exemplo para iniciar.",

    tabMap: "Mapa",
    tabRelationships: "Relacionamentos",
    tabArchitecture: "Arquitetura",
    tabPages: "Páginas",

    legendSource: "Fonte",
    legendQuery: "Query",
    legendModel: "Modelo",
    legendMeasure: "Medida",
    legendCalcColumn: "Col. Calculada",
    legendVisual: "Visual",

    emptyTitle: "Comece pelo arquivo PBIX",
    emptyBody: "O app detecta conectores, queries, tabelas e sinais de relatório quando essas informações existem no pacote.",
    relEmptyTitle: "Nenhum relacionamento encontrado",
    relEmptyBody: "Carregue um arquivo PBIX analisado pelo backend para ver os relacionamentos do modelo.",

    archEmptyTitle: "Nenhuma fonte de dados encontrada",
    archEmptyBody: "Carregue um arquivo PBIX para ver o diagrama de arquitetura de conexões.",
    pagesEmptyTitle: "Nenhuma página encontrada",
    pagesEmptyBody: "Carregue um arquivo PBIX para ver as páginas do relatório.",
    pagesVisualsLabel: (n) => `${n} visual${n !== 1 ? "is" : ""}`,
    pagesCanvasLabel: (w, h) => `${w} × ${h} px`,
    archPbiLabel: "Dataset Power BI",
    archNoQueries: "Nenhuma query mapeada",
    archSourcesCount: (n) => `${n} fonte${n !== 1 ? "s" : ""} de dados conectada${n !== 1 ? "s" : ""}`,

    typeSource: "Fonte",
    typeQuery: "Query",
    typeModel: "Modelo",
    typeMeasure: "Medida",
    typeCalcColumn: "Col. Calculada",
    typeVisual: "Visual",

    detailsDirectDeps: "Dependências diretas:",
    detailsImpacted: "Nós impactados:",
    detailsAffects: "Afeta:",

    relFromTable: "Tabela Origem",
    relFromCol: "Coluna Origem",
    relToTable: "Tabela Destino",
    relToCol: "Coluna Destino",
    relCardinality: "Cardinalidade",
    relCrossFilter: "Filtro Cruzado",
    relActive: "Ativo",
    relInactive: "Inativo",
    relTableAriaLabel: "Tabela de relacionamentos",
    relNoData: "Nenhum relacionamento disponível.",

    loadingAnalysing: (name) => `Analisando ${name}…`,
    loadingNoBackend: "Nenhuma entrada encontrada no pacote.",
    loadingError: "Não foi possível ler esse PBIX. Veja o console para detalhes.",
    loadingEntries: (n, extra) => `${n} entradas lidas do pacote PBIX${extra}.`,
    loadingNestedExtra: (n) => ` + ${n} entradas internas do DataMashup`,

    exportTimestamp: () => new Date().toLocaleString("pt-BR"),

    demoTitle: "Demo Linhagem",
    demoSubtitle: "Exemplo com fontes, queries, modelo, medidas e visuais.",
    demoQuery1Expr: "Sql.Database(...) com merge em calendário fiscal",
    demoQuery2Expr: "Excel.Workbook(...) para metas mensais",
    demoQuery3Expr: "Web.Contents(...) para cotações",
    demoCross1: "Simples",
    demoCross2: "Bidirecional",
    demoCross3: "Simples",
    demoCross4: "Simples",
    demoCross5: "Simples",

    langToggleLabel: "Idioma",

    // Controles de zoom (G11)
    zoomInLabel: "Aproximar",
    zoomOutLabel: "Afastar",
    zoomFitLabel: "Ajustar à tela",
    zoomControlsLabel: "Controles de zoom",
  }
};

// Active locale — default EN-US, persisted in localStorage
export let locale = (localStorage.getItem("bifm-locale") || "en-US");
document.documentElement.lang = locale; // G8 — sincroniza <html lang> já no load com o idioma persistido

export function t() {
  return I18N[locale] || I18N["en-US"];
}

export function setLocale(newLocale) {
  locale = newLocale;
  localStorage.setItem("bifm-locale", locale);
  document.documentElement.lang = locale; // G8 — WCAG 3.1.1: <html lang> segue o idioma ativo
  applyI18n();
  renderFilters();          // re-renders filter labels
  renderGraph();            // re-renders node subtitles and details
  if (state.activeTab === "relacionamentos") renderRelationships();
  if (state.activeTab === "arquitetura") renderArchitecture();
  if (state.activeTab === "paginas") renderPages();
}

export function applyI18n() {
  const T = t();

  // Brand
  document.querySelector(".brand-block p").textContent         = T.appSubtitle;

  // Upload zone
  document.querySelector(".upload-title").textContent          = T.uploadTitle;
  document.querySelector(".upload-copy").textContent           = T.uploadCopy;

  // Toolbar
  els.demoButton.title = T.btnDemoTitle;
  els.demoButton.querySelector(".btn-text").textContent        = T.btnDemo;
  els.pbixButton.title = T.btnPbixTitle;
  els.pbixButton.querySelector(".btn-text").textContent        = T.btnPbix;
  els.exportButton.title = T.btnJsonTitle;
  els.exportButton.querySelector(".btn-text").textContent      = T.btnJson;
  els.exportImageButton.title = T.btnPngTitle;
  els.exportImageButton.querySelector(".btn-text").textContent = T.btnPng;
  els.exportDocxButton.title = T.btnDocxTitle;
  els.exportDocxButton.querySelector(".btn-text").textContent  = T.btnDocx;

  // Panels headings
  document.getElementById("panelHeadSummary").textContent      = T.panelSummary;
  document.getElementById("panelHeadFilters").textContent      = T.panelFilters;
  document.getElementById("panelHeadLineage").textContent      = T.panelLineage;
  document.getElementById("panelHeadDetails").textContent      = T.panelDetails;

  // Metrics labels
  document.getElementById("metricSources").textContent        = T.metricSources;
  document.getElementById("metricQueries").textContent        = T.metricQueries;
  document.getElementById("metricNodes").textContent          = T.metricNodes;
  document.getElementById("metricImpact").textContent         = T.metricImpact;

  // Lineage toggle
  document.querySelector(".toggle-text strong").textContent    = T.lineageToggleStrong;
  document.querySelector(".toggle-text span").textContent      = T.lineageToggleSpan;

  // Details placeholder (only if no node is selected)
  if (!state.selectedId) {
    els.details.innerHTML = `<p>${T.detailsPlaceholder}</p>`;
  }

  // Workspace header
  // Only reset title/subtitle when they still show the default text
  if (
    els.title.textContent === I18N["en-US"].workspaceTitle ||
    els.title.textContent === I18N["pt-BR"].workspaceTitle
  ) {
    els.title.textContent = T.workspaceTitle;
  }
  if (
    els.subtitle.textContent === I18N["en-US"].workspaceSubtitle ||
    els.subtitle.textContent === I18N["pt-BR"].workspaceSubtitle
  ) {
    setSubtitle(T.workspaceSubtitle);
  }

  // Tabs
  els.tabMapa.textContent             = T.tabMap;
  els.tabRelacionamentos.textContent  = T.tabRelationships;
  els.tabArquitetura.textContent      = T.tabArchitecture;
  els.tabPaginas.textContent          = T.tabPages;

  const pagesEmptyStrong = els.pagesEmpty.querySelector("strong");
  const pagesEmptySpan   = els.pagesEmpty.querySelector("span");
  if (pagesEmptyStrong) pagesEmptyStrong.textContent = T.pagesEmptyTitle;
  if (pagesEmptySpan)   pagesEmptySpan.textContent   = T.pagesEmptyBody;

  // Legend
  const legendSpans = els.mapLegend.querySelectorAll("span");
  const legendKeys  = ["legendSource","legendQuery","legendModel","legendMeasure","legendVisual"];
  legendSpans.forEach((span, i) => {
    const dot = span.querySelector("i");
    span.textContent = " " + T[legendKeys[i]];
    span.prepend(dot);
  });

  // Empty states
  const emptyStrong = els.emptyState.querySelector("strong");
  const emptySpan   = els.emptyState.querySelector("span");
  if (emptyStrong) emptyStrong.textContent = T.emptyTitle;
  if (emptySpan)   emptySpan.textContent   = T.emptyBody;

  const relEmptyStrong = els.relEmpty.querySelector("strong");
  const relEmptySpan   = els.relEmpty.querySelector("span");
  if (relEmptyStrong) relEmptyStrong.textContent = T.relEmptyTitle;
  if (relEmptySpan)   relEmptySpan.textContent   = T.relEmptyBody;

  const archEmptyStrong = els.archEmpty.querySelector("strong");
  const archEmptySpan   = els.archEmpty.querySelector("span");
  if (archEmptyStrong) archEmptyStrong.textContent = T.archEmptyTitle;
  if (archEmptySpan)   archEmptySpan.textContent   = T.archEmptyBody;

  // Search field (G10)
  const searchLabelEl = document.getElementById("nodeSearchLabel");
  if (searchLabelEl)   searchLabelEl.textContent   = T.filterSearchLabel;
  if (els.nodeSearch)  els.nodeSearch.setAttribute("placeholder", T.filterSearchPlaceholder);

  // Zoom controls (G11)
  if (els.zoomInButton)  { els.zoomInButton.title  = T.zoomInLabel;  els.zoomInButton.setAttribute("aria-label", T.zoomInLabel); }
  if (els.zoomOutButton) { els.zoomOutButton.title = T.zoomOutLabel; els.zoomOutButton.setAttribute("aria-label", T.zoomOutLabel); }
  if (els.zoomFitButton) { els.zoomFitButton.title = T.zoomFitLabel; els.zoomFitButton.setAttribute("aria-label", T.zoomFitLabel); }
  if (els.zoomControls)  els.zoomControls.setAttribute("aria-label", T.zoomControlsLabel);

  // Lang toggle button state
  document.querySelectorAll(".lang-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.lang === locale);
  });
}

// TYPE_LABELS is now dynamic — always call typeLabels() instead of TYPE_LABELS directly
export function typeLabels() {
  const T = t();
  return {
    source:      T.typeSource,
    query:       T.typeQuery,
    model:       T.typeModel,
    measure:     T.typeMeasure,
    calc_column: T.typeCalcColumn,
    visual:      T.typeVisual,
  };
}

// Reexportado por conveniência — vários módulos já importavam essa lista
// junto com typeLabels() antes da modularização.
export { TYPE_LABELS_KEYS };

// ─── End Internationalisation ─────────────────────────────────────────────────
