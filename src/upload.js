// ─── Upload (PBIX real, drag-and-drop, demo) ───────────────────────────────
// G9 — drag-and-drop real: reaproveita loadPbix(), mesmo caminho do
// <input type="file">.
import { els, setSubtitle } from "./dom-refs.js";
import { t } from "./i18n.js";
import { state, cloneGraph, connectorNode, queryNode, modelNode, measureNode, calcColumnNode, visualNode, edge } from "./graph-model.js";
import { setGraph } from "./graph-render.js";
import { buildArchitectureData } from "./architecture.js";
import { readZipEntries, extractArtifacts, buildGraphFromArtifacts } from "./pbix-parser.js";

// hooks.loadPbix é o único ponto de indireção deste módulo: os listeners de
// #pbixInput (change) e #uploadZone (drop) chamam através deste objeto
// mutável em vez do identificador `loadPbix` direto, para que testes possam
// substituir a implementação por uma spy (mesma técnica de zoom.js/
// graph-render.js) sem depender de comportamento específico de bundler.
export const hooks = { loadPbix };

export async function loadPbix(file) {
  setSubtitle(t().loadingAnalysing(file.name));
  state.lastPbixFile = file;
  els.exportDocxButton.disabled = false;
  const backendGraph = await analyzeWithBackend(file);
  if (backendGraph) {
    state.relationships = backendGraph.relationships || [];
    state.pages        = backendGraph.pages        || [];
    console.log("[BIFlowMapper] relationships recebidos:", state.relationships.length, state.relationships);
    console.log("[BIFlowMapper] warnings:", backendGraph.warnings);
    state.architecture = buildArchitectureData(backendGraph);
    rememberPbix(backendGraph, file.name, "");
    setGraph(backendGraph, file.name, "");
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

// Wireup de #pbixInput (change) e #uploadZone (dragenter/dragover/dragleave/
// drop) — chamado por main.js.bindEvents().
export function bindUploadEvents() {
  els.input.addEventListener("change", async (event) => {
    const file = event.target.files[0];
    if (!file) return;
    await hooks.loadPbix(file);
  });

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
