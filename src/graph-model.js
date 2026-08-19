// ─── Modelo de grafo — funções puras, sem DOM ──────────────────────────────
// `state` é o único objeto de estado global do app: mutado diretamente pelos
// outros módulos (sem framework reativo) e sempre re-renderizado via chamada
// manual da função de render correspondente. Só existe UMA instância — todo
// módulo que precisa de estado compartilhado importa este mesmo `state`.
//
// As demais exportações são funções puras (constroem/consultam objetos em
// memória, nunca tocam `document`), o que as torna testáveis isoladamente
// sem precisar de jsdom.

export const CONNECTORS = [
  { pattern: "Sql.Database", name: "SQL Server", icon: "SQL", color: "#2176ae" },
  { pattern: "Excel.Workbook", name: "Excel", icon: "XLS", iconUrl: "assets/connectors/excel-workbook-64.png", color: "#28805a" },
  { pattern: "Web.Contents", name: "Web", icon: "WEB", iconUrl: "assets/connectors/web-64.png", color: "#6f52b8" },
  { pattern: "SharePoint.Files", name: "SharePoint Files", icon: "SP", color: "#2b8f9f" },
  { pattern: "SharePoint.Contents", name: "SharePoint", icon: "SP", color: "#2b8f9f" },
  { pattern: "OData.Feed", name: "OData", icon: "OD", color: "#b23a48" },
  { pattern: "Csv.Document", name: "CSV", icon: "CSV", color: "#d39200" },
  { pattern: "Folder.Files", name: "Folder", icon: "DIR", color: "#4d6b7c" },
  { pattern: "Json.Document", name: "JSON", icon: "JSN", color: "#7a5c1f" },
  { pattern: "AnalysisServices.Database", name: "Analysis Services", icon: "AS", color: "#5266b8" },
  { pattern: "Oracle.Database", name: "Oracle", icon: "ORA", color: "#c3423f" },
  { pattern: "PostgreSQL.Database", name: "PostgreSQL", icon: "PG", color: "#35668d" },
  { pattern: "MySQL.Database", name: "MySQL", icon: "MY", color: "#c7762f" },
  { pattern: "Snowflake.Databases", name: "Snowflake", icon: "SN", color: "#4197b5" },
  { pattern: "Databricks.Catalogs", name: "Databricks", icon: "DB", color: "#d64d39" },
  { pattern: "PowerPlatform.Dataflows", name: "Power Platform Dataflows", icon: "DF", color: "#4f7bd9" },
  { pattern: "AzureStorage.Blobs", name: "Azure Blob Storage", icon: "AZ", color: "#2176ae" },
  { pattern: "AzureStorage.DataLake", name: "Azure Data Lake", icon: "ADL", color: "#2176ae" },
  { pattern: "GoogleAnalytics.Accounts", name: "Google Analytics", icon: "GA", color: "#d39200" },
  { pattern: "Salesforce.Data", name: "Salesforce", icon: "SF", color: "#2b8f9f" },
  { pattern: "SapBusinessWarehouse.Cubes", name: "SAP BW", icon: "SAP", color: "#5266b8" },
  { pattern: "Sql.Databases", name: "SQL Server", icon: "SQL", color: "#2176ae" }
];

// TYPE_LABELS_KEYS é a lista canônica de tipos de nó — i18n.js usa para
// montar typeLabels() (rótulos traduzidos) e export.js usa para inferir o
// tipo de um card a partir das classes CSS no export PNG.
export const TYPE_LABELS_KEYS = ["source", "query", "model", "measure", "calc_column", "visual"];

export const state = {
  graph: { nodes: [], edges: [] },
  relationships: [],          // dados estruturados vindos do backend
  architecture: [],           // [{source, iconUrl, icon, color, queries:[{name,expression,connectionPath}]}]
  lastPbix: null,
  lastPbixFile: null,
  selectedId: null,
  activeTab: "mapa",          // "mapa" | "relacionamentos" | "arquitetura" | "paginas"
  pages: [],                  // [{name, ordinal, visualCount, width, height}]
  lineageFilter: false,       // quando true: exibe só a linhagem do nó selecionado
  enabledTypes: new Set(TYPE_LABELS_KEYS),
  searchTerm: "",              // G10 — termo de busca textual (nome/DAX/M), normalizado no filtro
  scale: 1                     // G11 — fator de zoom aplicado a #graphViewport via transform: scale()
};

export function layoutGraph(graph) {
  const order = ["source", "query", "model", "measure", "visual"];
  const columns = new Map(order.map((type) => [type, []]));
  graph.nodes.forEach((node) => {
    if (!columns.has(node.type)) columns.set(node.type, []);
    columns.get(node.type).push(node);
  });

  // Position all types except measure and calc_column normally
  columns.forEach((nodes, type) => {
    if (type === "calc_column") return; // handled below
    const column = order.indexOf(type) >= 0 ? order.indexOf(type) : order.length;
    nodes.forEach((node, row) => {
      node.x = 42 + column * 250;
      node.y = 42 + row * 120;
    });
  });

  // measure + calc_column share the same X column, stacked as one continuous list
  const measureColIdx = order.indexOf("measure");
  const measureNodes  = columns.get("measure") || [];
  const calcColNodes  = graph.nodes.filter((n) => n.type === "calc_column");
  [...measureNodes, ...calcColNodes].forEach((node, row) => {
    node.x = 42 + measureColIdx * 250;
    node.y = 42 + row * 120;
  });

  const measureAndCalc = measureNodes.length + calcColNodes.length;
  const maxRows = Math.max(
    1,
    ...Array.from(columns.entries())
      .filter(([type]) => type !== "calc_column")
      .map(([, nodes]) => nodes.length),
    measureAndCalc
  );
  graph.width  = Math.max(960, order.length * 250 + 120);
  graph.height = Math.max(680, maxRows * 120 + 120);
  return graph;
}

// Nós ancestrais (que alimentam startId, subindo o grafo)
export function upstream(startId, edges) {
  const result = new Set();
  const queue = [startId];
  while (queue.length) {
    const current = queue.shift();
    edges
      .filter((e) => e.to === current)
      .forEach((e) => {
        if (!result.has(e.from)) {
          result.add(e.from);
          queue.push(e.from);
        }
      });
  }
  return result;
}

export function downstream(startId, edges) {
  const result = new Set();
  const queue = [startId];
  while (queue.length) {
    const current = queue.shift();
    edges
      .filter((edgeItem) => edgeItem.from === current)
      .forEach((edgeItem) => {
        if (!result.has(edgeItem.to)) {
          result.add(edgeItem.to);
          queue.push(edgeItem.to);
        }
      });
  }
  return result;
}

// ─── Busca textual (G10) ────────────────────────────────────────────────────
// Compara o termo digitado (normalizado: minúsculas, sem acento — reaproveita
// normalize(), já usada em slug()) contra o nome do nó e, quando existir, o
// texto da expressão M/DAX associada (node.meta.expression — já em memória,
// carregada do /api/analyze). Função pura, sem DOM, testável isoladamente.
export function nodeMatchesSearch(node, term) {
  const query = normalize(term || "").trim();
  if (!query) return true; // busca vazia = mostra tudo (comportamento atual)
  const expression = (node.meta && node.meta.expression) || "";
  const haystack = normalize(`${node.label || ""} ${expression}`);
  return haystack.includes(query);
}

// Faixa Unicode dos diacríticos combinantes (U+0300–U+036F) — construída via
// String.fromCharCode em vez de um literal `\uXXXX` no regex para não
// depender de como a camada de transporte decodifica escapes de string ao
// gravar o arquivo. Resultado idêntico ao antigo `/[̀-ͯ]/g` de
// app.js.
const COMBINING_DIACRITICS_RANGE = `${String.fromCharCode(0x0300)}-${String.fromCharCode(0x036f)}`;
const COMBINING_DIACRITICS_REGEX = new RegExp(`[${COMBINING_DIACRITICS_RANGE}]`, "g");

export function normalize(value) {
  return String(value).toLowerCase().normalize("NFD").replace(COMBINING_DIACRITICS_REGEX, "");
}

export function slug(value) {
  return normalize(value)
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "") || "item";
}

export function initials(value) {
  return String(value)
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 3)
    .map((part) => part[0])
    .join("")
    .toUpperCase();
}

export function toTitle(value) {
  return String(value)
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

export function snippetAround(text, term, size) {
  const index = text.toLowerCase().indexOf(term.toLowerCase());
  if (index < 0) return "";
  return text.slice(Math.max(0, index - size / 3), index + size);
}

export function uniqueById(items) {
  return Array.from(new Map(items.map((item) => [item.id, item])).values());
}

export function uniqueByName(items) {
  return Array.from(new Map(items.map((item) => [item.name, item])).values());
}

export function uniqueEdges(items) {
  return Array.from(new Map(items.map((item) => [item.id, item])).values());
}

export function edge(from, to, label = "") {
  return { id: `${from}->${to}`, from, to, label };
}

export function connectorNode(name, connector = CONNECTORS.find((item) => item.name === name) || {}) {
  return {
    id: `source:${slug(name)}`,
    type: "source",
    label: name,
    icon: connector.icon || initials(name),
    iconUrl: connector.iconUrl || "",
    meta: { pattern: connector.pattern || name, color: connector.color || "#2176ae" }
  };
}

export function queryNode(name, expression = "") {
  return {
    id: `query:${slug(name)}`,
    type: "query",
    label: name,
    icon: "M",
    meta: { expression }
  };
}

export function modelNode(name) {
  return {
    id: `model:${slug(name)}`,
    type: "model",
    label: name,
    icon: "TBL",
    meta: {}
  };
}

export function measureNode(name) {
  return {
    id: `measure:${slug(name)}`,
    type: "measure",
    label: name,
    icon: "DAX",
    meta: {}
  };
}

export function calcColumnNode(name) {
  return {
    id: `calc_column:${slug(name)}`,
    type: "calc_column",
    label: name,
    icon: "CC",
    meta: {}
  };
}

export function visualNode(name) {
  return {
    id: `visual:${slug(name)}`,
    type: "visual",
    label: name,
    icon: "VIS",
    meta: {}
  };
}

export function cloneGraph(graph) {
  return JSON.parse(JSON.stringify(graph));
}

export function labelForId(id) {
  const node = state.graph.nodes.find((item) => item.id === id);
  return node ? node.label : id;
}
