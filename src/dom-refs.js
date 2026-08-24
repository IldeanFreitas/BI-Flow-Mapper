// ─── Referências de DOM compartilhadas ─────────────────────────────────────
// `els` é consultado (document.getElementById/...) na avaliação deste módulo
// — ou seja, no momento em que ele é importado pela primeira vez. Precisa
// rodar depois que o DOM real (index.html) já existe, senão os campos ficam
// `null` (mesma restrição que existia em app.js, que dependia de rodar via
// <script> no fim do <body>).
//
// Módulo folha: não importa nada de outros módulos do app, para poder ser
// importado por qualquer um deles (i18n, graph-render, zoom, upload, export,
// relationships/architecture/pages) sem risco de ciclo.

export const els = {
  input: document.getElementById("pbixInput"),
  uploadZone: document.getElementById("uploadZone"),
  pbipFolderInput: document.getElementById("pbipFolderInput"),   // G17 — seleção de pasta .pbip/.SemanticModel
  pbipFolderZone: document.getElementById("pbipFolderZone"),
  pbipFolderLabel: document.getElementById("pbipFolderLabel"),
  loadingSpinner: document.getElementById("loadingSpinner"),     // G23 — indicador de progresso durante análise
  demoButton: document.getElementById("demoButton"),
  pbixButton: document.getElementById("pbixButton"),
  exportButton: document.getElementById("exportButton"),
  graphCanvas: document.getElementById("graphCanvas"),
  graphViewport: document.getElementById("graphViewport"),   // G11 — wrapper escalado (edgeLayer + graphCanvas)
  edgeLayer: document.getElementById("edgeLayer"),
  zoomControls: document.getElementById("zoomControls"),
  zoomInButton: document.getElementById("zoomInButton"),
  zoomOutButton: document.getElementById("zoomOutButton"),
  zoomFitButton: document.getElementById("zoomFitButton"),
  zoomLevel: document.getElementById("zoomLevel"),
  emptyState: document.getElementById("emptyState"),
  details: document.getElementById("nodeDetails"),
  typeFilters: document.getElementById("typeFilters"),
  nodeSearch: document.getElementById("nodeSearchInput"),    // G10 — busca textual
  sourceCount: document.getElementById("sourceCount"),
  queryCount: document.getElementById("queryCount"),
  nodeCount: document.getElementById("nodeCount"),
  impactCount: document.getElementById("impactCount"),
  title: document.getElementById("workspaceTitle"),
  subtitle: document.getElementById("workspaceSubtitle"),
  tabMapa: document.getElementById("tabMapa"),
  tabRelacionamentos: document.getElementById("tabRelacionamentos"),
  panelMapa: document.getElementById("panelMapa"),
  panelRelacionamentos: document.getElementById("panelRelacionamentos"),
  mapLegend: document.getElementById("mapLegend"),
  lineageConfidenceLegend: document.getElementById("lineageConfidenceLegend"),
  relEmpty: document.getElementById("relEmpty"),
  relContent: document.getElementById("relContent"),
  relDiagram: document.getElementById("relDiagram"),
  relTable: document.getElementById("relTable"),
  lineageToggle: document.getElementById("lineageToggle"),
  exportImageButton: document.getElementById("exportImageButton"),
  exportDocxButton: document.getElementById("exportDocxButton"),
  exportHtmlButton: document.getElementById("exportHtmlButton"),
  tabArquitetura: document.getElementById("tabArquitetura"),
  panelArquitetura: document.getElementById("panelArquitetura"),
  archEmpty: document.getElementById("archEmpty"),
  archContent: document.getElementById("archContent"),
  archDiagram: document.getElementById("archDiagram"),
  tabPaginas: document.getElementById("tabPaginas"),
  panelPaginas: document.getElementById("panelPaginas"),
  pagesEmpty: document.getElementById("pagesEmpty"),
  pagesContent: document.getElementById("pagesContent"),
  tabInsights: document.getElementById("tabInsights"),
  panelInsights: document.getElementById("panelInsights"),
  insightsEmpty: document.getElementById("insightsEmpty"),
  insightsContent: document.getElementById("insightsContent"),
};

export function setSubtitle(text) {
  els.subtitle.textContent = text;
  els.subtitle.hidden = !text;
}

// G23 — spinner visual junto de #workspaceSubtitle. Independente de
// setSubtitle(): o texto continua sendo o anúncio real para leitor de tela
// (aria-live="polite", já coberto pelo G8), o spinner é só reforço visual
// para quem está olhando a tela durante uma análise demorada.
export function setLoading(isLoading) {
  if (!els.loadingSpinner) return;
  els.loadingSpinner.hidden = !isLoading;
}
