// ─── Upload (PBIX real, drag-and-drop, pasta .pbip, demo) ──────────────────
// G9 — drag-and-drop real: reaproveita loadPbix(), mesmo caminho do
// <input type="file">.
// G17 — seleção de pasta .pbip/.SemanticModel via <input webkitdirectory>,
// filtra os arquivos .tmdl e envia pro endpoint /api/analyze-tmdl (backend),
// reaproveitando o mesmo caminho de renderização (applyBackendGraph) usado
// pelo fluxo .pbix.
// G23 — setLoading()/setSubtitle() (src/dom-refs.js) cobrem, em try/finally,
// TODO o tempo entre o início do fetch e a resposta, tanto pro fluxo .pbix
// quanto pro fluxo .pbip/TMDL.
import { els, setSubtitle, setLoading } from "./dom-refs.js";
import { t } from "./i18n.js";
import { state, cloneGraph, connectorNode, queryNode, modelNode, measureNode, calcColumnNode, visualNode, edge } from "./graph-model.js";
import { setGraph } from "./graph-render.js";
import { buildArchitectureData } from "./architecture.js";
import { readZipEntries, extractArtifacts, buildGraphFromArtifacts } from "./pbix-parser.js";

// hooks.loadPbix/hooks.loadPbipFolder são o único ponto de indireção deste
// módulo: os listeners de #pbixInput (change), #uploadZone (drop) e
// #pbipFolderInput (change) chamam através deste objeto mutável em vez do
// identificador direto, para que testes possam substituir a implementação
// por uma spy (mesma técnica de zoom.js/graph-render.js) sem depender de
// comportamento específico de bundler.
export const hooks = { loadPbix, loadPbipFolder };

// Aplica no DOM o mesmo shape de grafo devolvido por /api/analyze e
// /api/analyze-tmdl — ponto único de renderização pro backend, reaproveitado
// pelos dois fluxos (G17) em vez de duplicar a lógica de setGraph/rememberPbix.
function applyBackendGraph(graph, title, subtitle) {
  state.relationships = graph.relationships || [];
  state.pages        = graph.pages        || [];
  state.architecture = buildArchitectureData(graph);
  rememberPbix(graph, title, subtitle);
  setGraph(graph, title, subtitle);
}

export async function loadPbix(file) {
  setSubtitle(t().loadingAnalysing(file.name));
  setLoading(true);
  state.lastPbixFile = file;
  els.exportDocxButton.disabled = false;
  try {
    const backendGraph = await analyzeWithBackend(file);
    if (backendGraph) {
      console.log("[BIFlowMapper] relationships recebidos:", (backendGraph.relationships || []).length, backendGraph.relationships);
      console.log("[BIFlowMapper] warnings:", backendGraph.warnings);
      applyBackendGraph(backendGraph, file.name, "");
      return;
    }

    state.relationships = [];
    state.architecture  = [];
    state.pages         = [];
    try {
      const arrayBuffer = await file.arrayBuffer();
      const entries = await readZipEntries(arrayBuffer);
      const artifacts = await extractArtifacts(entries);
      const graph = buildGraphFromArtifacts(artifacts, file.name);
      const nestedCount = artifacts.entryNames.length - entries.length;
      const nestedCopy = nestedCount > 0 ? t().loadingNestedExtra(nestedCount) : "";
      const subtitle = t().loadingEntries(entries.length, nestedCopy);
      state.architecture = buildArchitectureData(graph);
      rememberPbix(graph, file.name, subtitle);
      setGraph(graph, file.name, subtitle);
    } catch (error) {
      console.error(error);
      setSubtitle(t().loadingError);
    }
  } finally {
    setLoading(false);
  }
}

// ─── G17 — pasta .pbip/.SemanticModel ───────────────────────────────────────

// Filtra, de uma FileList/array de File (ou objeto File-like em teste), só os
// arquivos com extensão .tmdl — o resto da árvore (.Report/, .json, .pbip
// raiz etc.) fica fora de escopo desta rodada. Função pura, sem efeito
// colateral, isolada para ser testável com um array sintético (FileList/
// webkitdirectory são difíceis de simular em jsdom).
export function filterTmdlFiles(fileList) {
  return Array.from(fileList || []).filter((file) => {
    const path = file.webkitRelativePath || file.name || "";
    return path.toLowerCase().endsWith(".tmdl");
  });
}

// Monta o FormData multipart enviado a /api/analyze-tmdl: um campo
// "tmdl_files" por arquivo, com o path relativo dentro da pasta selecionada
// (barras normais) como filename — é isso que o parser TMDL do backend usa
// pra saber em qual tabela/pasta cada arquivo está. Função pura (não faz
// fetch), isolada para ser testável sem precisar de um FileList real.
export function buildTmdlFormData(tmdlFiles) {
  const formData = new FormData();
  tmdlFiles.forEach((file) => {
    formData.append("tmdl_files", file, file.webkitRelativePath || file.name);
  });
  return formData;
}

// Deriva um título legível pro grafo a partir do primeiro segmento do path
// relativo (ex.: "MeuModelo.pbip/MeuModelo.SemanticModel/definition/tables/
// Sales.tmdl" -> "MeuModelo.pbip"). Cai para um rótulo genérico se o
// navegador não expuser webkitRelativePath (não deveria acontecer com
// webkitdirectory, mas evita título vazio).
function derivePbipTitle(tmdlFiles) {
  const firstPath = (tmdlFiles[0] && (tmdlFiles[0].webkitRelativePath || tmdlFiles[0].name)) || "";
  return firstPath.split("/")[0] || "Model.pbip";
}

export async function analyzeTmdlWithBackend(tmdlFiles) {
  const formData = buildTmdlFormData(tmdlFiles);
  const response = await fetch("/api/analyze-tmdl", {
    method: "POST",
    body: formData
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.error || `HTTP ${response.status}`);
  }
  return await response.json();
}

// Handler de #pbipFolderInput (change): recebe o FileList inteiro da pasta
// selecionada (webkitdirectory), filtra pra só .tmdl, monta o upload
// multipart e reaproveita o mesmo caminho de renderização do fluxo .pbix
// (applyBackendGraph) — mesmo shape de grafo devolvido pelo backend.
export async function loadPbipFolder(fileList) {
  const tmdlFiles = filterTmdlFiles(fileList);
  if (tmdlFiles.length === 0) {
    setSubtitle(t().tmdlNoFilesFound);
    return;
  }

  setSubtitle(t().loadingAnalysingTmdl(tmdlFiles.length));
  setLoading(true);
  // Export docs (G23: /api/export-docx) reenvia state.lastPbixFile (o
  // arquivo .pbix bruto) pro backend — não existe nesse fluxo, que envia N
  // arquivos .tmdl em vez de um único .pbix. Limpa e desabilita
  // explicitamente pra não deixar um botão habilitado reexportar, em
  // silêncio, a documentação de um .pbix anterior que não é mais o que está
  // na tela.
  state.lastPbixFile = null;
  els.exportDocxButton.disabled = true;
  try {
    const graph = await analyzeTmdlWithBackend(tmdlFiles);
    applyBackendGraph(graph, derivePbipTitle(tmdlFiles), "");
  } catch (error) {
    console.error(error);
    setSubtitle(t().loadingErrorTmdl);
  } finally {
    setLoading(false);
  }
}

export function rememberPbix(graph, title, subtitle) {
  state.lastPbix = {
    graph: cloneGraph(graph),
    title,
    subtitle
  };
  els.pbixButton.disabled = false;
}

export function loadLastPbix() {
  if (!state.lastPbix) return;
  setGraph(cloneGraph(state.lastPbix.graph), state.lastPbix.title, state.lastPbix.subtitle);
}

export async function analyzeWithBackend(file) {
  if (window.location.protocol === "file:") return null;

  const form = new FormData();
  form.append("pbix", file, file.name);

  try {
    const response = await fetch("/api/analyze", {
      method: "POST",
      body: form
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.error || `HTTP ${response.status}`);
    }
    return await response.json();
  } catch (error) {
    console.warn("Backend PBIXRay indisponivel; usando fallback do navegador.", error);
    return null;
  }
}

export function loadDemo() {
  const demo = {
    sources: [
      connectorNode("SQL Server", { iconUrl: "assets/connectors/sql-database-64.png", icon: "SQL" }),
      connectorNode("Excel", { iconUrl: "assets/connectors/excel-workbook-64.png", icon: "XLS" }),
      connectorNode("Web", { iconUrl: "assets/connectors/web-64.png", icon: "WEB" })
    ],
    queries: [
      queryNode("Sales Query", t().demoQuery1Expr),
      queryNode("Targets Query", t().demoQuery2Expr),
      queryNode("FX Rates Query", t().demoQuery3Expr)
    ],
    tables: ["Sales", "Targets", "Exchange Rates", "Date"].map(modelNode),
    measures: ["Revenue", "Gross Margin", "Target Gap"].map(measureNode),
    calcColumns: ["YTD Category", "Margin Band"].map(calcColumnNode),
    visuals: ["Sales by Region", "Margin Trend", "Target Gap Card"].map(visualNode)
  };

  const nodes = [
    ...demo.sources,
    ...demo.queries,
    ...demo.tables,
    ...demo.measures,
    ...demo.calcColumns,
    ...demo.visuals
  ];

  const edges = [
    edge("source:sql-server", "query:sales-query"),
    edge("source:excel", "query:targets-query"),
    edge("source:web", "query:fx-rates-query"),
    edge("query:sales-query", "model:sales"),
    edge("query:targets-query", "model:targets"),
    edge("query:fx-rates-query", "model:exchange-rates"),
    edge("model:sales", "measure:revenue"),
    edge("model:sales", "measure:gross-margin"),
    edge("model:targets", "measure:target-gap"),
    edge("model:sales", "calc_column:ytd-category"),
    edge("model:sales", "calc_column:margin-band"),
    edge("measure:revenue", "visual:sales-by-region"),
    edge("measure:gross-margin", "visual:margin-trend"),
    edge("measure:target-gap", "visual:target-gap-card")
  ];

  setGraph({ nodes, edges, warnings: [] }, t().demoTitle, t().demoSubtitle);

  // Relationships for demo panel
  state.relationships = [
    { fromTable: "Sales",          fromColumn: "DateKey",      toTable: "Date",          toColumn: "DateKey",      cardinality: "M:1", crossFilter: "Single", active: true  },
    { fromTable: "Sales",          fromColumn: "ProductKey",   toTable: "Products",      toColumn: "ProductKey",   cardinality: "M:1", crossFilter: "Single", active: true  },
    { fromTable: "Targets",        fromColumn: "DateKey",      toTable: "Date",          toColumn: "DateKey",      cardinality: "M:1", crossFilter: "Single", active: true  },
    { fromTable: "Exchange Rates", fromColumn: "CurrencyCode", toTable: "Targets",       toColumn: "CurrencyCode", cardinality: "M:1", crossFilter: "Both",   active: true  },
    { fromTable: "Sales",          fromColumn: "RegionKey",    toTable: "Exchange Rates", toColumn: "RegionKey",   cardinality: "M:M", crossFilter: "Single", active: false },
  ];

  // Architecture demo data
  state.architecture = [
    {
      sourceId: "source:sql-server",
      sourceName: "SQL Server",
      iconUrl: "assets/connectors/sql-database-64.png",
      icon: "SQL",
      color: "#2176ae",
      queries: [
        { name: "Sales Query",   connectionPath: "Sql.Database(\"contoso.database.windows.net\", \"SalesDB\")",    expression: t().demoQuery1Expr },
      ]
    },
    {
      sourceId: "source:excel",
      sourceName: "Excel",
      iconUrl: "assets/connectors/excel-workbook-64.png",
      icon: "XLS",
      color: "#28805a",
      queries: [
        { name: "Targets Query", connectionPath: "https://company.sharepoint.com/sites/finance/Targets.xlsx", expression: t().demoQuery2Expr },
      ]
    },
    {
      sourceId: "source:web",
      sourceName: "Web",
      iconUrl: "assets/connectors/web-64.png",
      icon: "WEB",
      color: "#6f52b8",
      queries: [
        { name: "FX Rates Query", connectionPath: "https://api.exchangerate.host/latest?base=USD", expression: t().demoQuery3Expr },
      ]
    },
  ];

  // Demo pages
  state.pages = [
    { name: "Sales Overview",    ordinal: 0, visualCount: 5, width: 1280, height: 720 },
    { name: "Margin Analysis",   ordinal: 1, visualCount: 4, width: 1280, height: 720 },
    { name: "Target Tracker",    ordinal: 2, visualCount: 3, width: 1280, height: 720 },
    { name: "FX Impact",         ordinal: 3, visualCount: 2, width: 1280, height: 720 },
  ];
}

// Wireup de #pbixInput (change), #uploadZone (dragenter/dragover/dragleave/
// drop) e #pbipFolderInput (change, G17) — chamado por main.js.bindEvents().
export function bindUploadEvents() {
  els.input.addEventListener("change", async (event) => {
    const file = event.target.files[0];
    if (!file) return;
    await hooks.loadPbix(file);
  });

  // G17 — <input webkitdirectory>: event.target.files é o FileList inteiro
  // da árvore selecionada (não só o 1º arquivo, ao contrário de #pbixInput).
  if (els.pbipFolderInput) {
    els.pbipFolderInput.addEventListener("change", async (event) => {
      const files = event.target.files;
      if (!files || files.length === 0) return;
      await hooks.loadPbipFolder(files);
      event.target.value = ""; // permite re-selecionar a mesma pasta em seguida
    });
  }

  ["dragenter", "dragover"].forEach((eventName) => {
    els.uploadZone.addEventListener(eventName, (event) => {
      event.preventDefault();
      event.stopPropagation();
      els.uploadZone.classList.add("dragover");
    });
  });

  els.uploadZone.addEventListener("dragleave", (event) => {
    event.preventDefault();
    // Ignora dragleave disparado por elementos filhos (span de texto, seta etc.)
    if (event.target === els.uploadZone || !els.uploadZone.contains(event.relatedTarget)) {
      els.uploadZone.classList.remove("dragover");
    }
  });

  els.uploadZone.addEventListener("drop", async (event) => {
    event.preventDefault();
    event.stopPropagation();
    els.uploadZone.classList.remove("dragover");
    const file = event.dataTransfer && event.dataTransfer.files && event.dataTransfer.files[0];
    if (!file) return;
    await hooks.loadPbix(file);
  });
}
