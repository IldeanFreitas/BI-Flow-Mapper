// ─── Parser PBIX no navegador (fallback sem backend) ───────────────────────
// Quando o backend PBIXRay não está disponível (ex.: app aberto via
// `file://`), o app tenta ler o .pbix como ZIP diretamente no navegador e
// detectar conectores/queries/tabelas/medidas/visuais via regex sobre o
// texto bruto das entradas. Nenhuma função aqui toca o DOM.
import {
  CONNECTORS,
  connectorNode,
  queryNode,
  modelNode,
  measureNode,
  calcColumnNode,
  visualNode,
  edge,
  normalize,
  uniqueById,
  uniqueByName,
  uniqueEdges,
  snippetAround,
  toTitle,
} from "./graph-model.js";
import { t } from "./i18n.js";

export async function readZipEntries(input) {
  const bytes = input instanceof Uint8Array ? input : new Uint8Array(input);
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const eocdOffset = findEndOfCentralDirectory(bytes);
  if (eocdOffset < 0) throw new Error("Arquivo ZIP/PBIX invalido.");

  const totalEntries = view.getUint16(eocdOffset + 10, true);
  const centralOffset = view.getUint32(eocdOffset + 16, true);
  const entries = [];
  let offset = centralOffset;

  for (let index = 0; index < totalEntries; index += 1) {
    const signature = view.getUint32(offset, true);
    if (signature !== 0x02014b50) break;

    const compression = view.getUint16(offset + 10, true);
    const compressedSize = view.getUint32(offset + 20, true);
    const uncompressedSize = view.getUint32(offset + 24, true);
    const nameLength = view.getUint16(offset + 28, true);
    const extraLength = view.getUint16(offset + 30, true);
    const commentLength = view.getUint16(offset + 32, true);
    const localOffset = view.getUint32(offset + 42, true);
    const nameBytes = bytes.slice(offset + 46, offset + 46 + nameLength);
    const name = decodeUtf8(nameBytes);

    const localNameLength = view.getUint16(localOffset + 26, true);
    const localExtraLength = view.getUint16(localOffset + 28, true);
    const dataOffset = localOffset + 30 + localNameLength + localExtraLength;
    const compressed = bytes.slice(dataOffset, dataOffset + compressedSize);

    entries.push({
      name,
      compression,
      compressed,
      compressedSize,
      uncompressedSize
    });

    offset += 46 + nameLength + extraLength + commentLength;
  }

  return entries;
}

export function findEndOfCentralDirectory(bytes) {
  for (let offset = bytes.length - 22; offset >= 0; offset -= 1) {
    if (
      bytes[offset] === 0x50 &&
      bytes[offset + 1] === 0x4b &&
      bytes[offset + 2] === 0x05 &&
      bytes[offset + 3] === 0x06
    ) {
      return offset;
    }
  }
  return -1;
}

export async function inflateEntry(entry) {
  if (entry.compression === 0) return entry.compressed;
  if (entry.compression !== 8) return new Uint8Array();
  if (!("DecompressionStream" in window)) {
    throw new Error("Este navegador nao oferece DecompressionStream para ZIP deflate.");
  }

  const stream = new Blob([entry.compressed]).stream().pipeThrough(new DecompressionStream("deflate-raw"));
  return new Uint8Array(await new Response(stream).arrayBuffer());
}

export async function extractArtifacts(entries) {
  const artifacts = {
    entryNames: entries.map((entry) => entry.name),
    texts: [],
    mashupText: "",
    layoutText: "",
    modelText: "",
    diagnostics: []
  };

  const interesting = entries.filter((entry) => {
    const name = entry.name.toLowerCase();
    return (
      name.includes("datamashup") ||
      name.includes("layout") ||
      name.includes("model") ||
      name.includes("connections") ||
      name.endsWith(".json") ||
      name.endsWith(".xml")
    );
  });

  for (const entry of interesting) {
    const data = await inflateEntry(entry);
    addArtifactText(artifacts, entry.name, data);

    if (entry.name.toLowerCase().includes("datamashup")) {
      const nestedEntries = await extractNestedMashupEntries(data, entry.name);
      for (const nested of nestedEntries) {
        artifacts.entryNames.push(nested.name);
        addArtifactText(artifacts, nested.name, nested.data);
      }
    }
  }

  artifacts.diagnostics.push(`Entries analysed: ${artifacts.entryNames.join(", ")}`);
  if (!artifacts.mashupText.trim()) {
    artifacts.diagnostics.push("DataMashup did not generate accessible M text in this read.");
  }

  return artifacts;
}

export function addArtifactText(artifacts, name, data) {
  const text = bestEffortText(data);
  artifacts.texts.push({ name, text });

  const lower = name.toLowerCase();
  if (lower.includes("datamashup") || lower.includes("formulas/") || lower.endsWith(".m")) {
    artifacts.mashupText += `\n${text}`;
  }
  if (lower.includes("layout") || lower.includes("report/")) artifacts.layoutText += `\n${text}`;
  if (lower.includes("model") || lower.includes("datamodelschema")) artifacts.modelText += `\n${text}`;
}

export async function extractNestedMashupEntries(data, parentName) {
  const packages = findEmbeddedZipPackages(data);
  const nested = [];

  for (const [packageIndex, bytes] of packages.entries()) {
    try {
      const entries = await readZipEntries(bytes);
      for (const entry of entries) {
        const inflated = await inflateEntry(entry);
        nested.push({
          name: `${parentName}::package${packageIndex + 1}/${entry.name}`,
          data: inflated
        });
      }
    } catch (error) {
      console.warn("Falha ao abrir pacote interno do DataMashup", error);
    }
  }

  return nested;
}

export function findEmbeddedZipPackages(data) {
  const packages = [];
  const offsets = new Set();

  if (data.byteLength > 8) {
    const view = new DataView(data.buffer, data.byteOffset, data.byteLength);
    const declaredLength = view.getUint32(0, true);
    if (declaredLength > 22 && declaredLength <= data.byteLength - 4) {
      const declaredPackage = data.slice(4, 4 + declaredLength);
      if (looksLikeZip(declaredPackage)) {
        packages.push(declaredPackage);
        offsets.add(4);
      }
    }
  }

  for (let offset = 0; offset < data.byteLength - 4 && packages.length < 8; offset += 1) {
    if (
      data[offset] === 0x50 &&
      data[offset + 1] === 0x4b &&
      data[offset + 2] === 0x03 &&
      data[offset + 3] === 0x04 &&
      !offsets.has(offset)
    ) {
      const candidate = data.slice(offset);
      if (findEndOfCentralDirectory(candidate) >= 0) {
        packages.push(candidate);
        offsets.add(offset);
      }
    }
  }

  return packages;
}

export function looksLikeZip(bytes) {
  return (
    bytes.byteLength > 4 &&
    bytes[0] === 0x50 &&
    bytes[1] === 0x4b &&
    bytes[2] === 0x03 &&
    bytes[3] === 0x04
  );
}

export function bestEffortText(bytes) {
  const utf8 = decodeUtf8(bytes);
  const utf16 = decodeUtf16Le(bytes);
  const asciiStrings = extractAsciiStrings(bytes).join("\n");
  return [utf8, utf16, asciiStrings].join("\n");
}

export function decodeUtf8(bytes) {
  try {
    return new TextDecoder("utf-8", { fatal: false }).decode(bytes);
  } catch {
    return "";
  }
}

export function decodeUtf16Le(bytes) {
  try {
    return new TextDecoder("utf-16le", { fatal: false }).decode(bytes);
  } catch {
    return "";
  }
}

export function extractAsciiStrings(bytes) {
  const strings = [];
  let current = "";
  for (const byte of bytes) {
    if (byte >= 32 && byte <= 126) {
      current += String.fromCharCode(byte);
    } else if (current.length >= 4) {
      strings.push(current);
      current = "";
    } else {
      current = "";
    }
  }
  if (current.length >= 4) strings.push(current);
  return strings;
}

export function buildGraphFromArtifacts(artifacts, fileName) {
  const allText = artifacts.texts.map((item) => item.text).join("\n");
  const detectedConnectors = detectConnectors(allText);
  const queries = detectQueries(artifacts.mashupText || allText, detectedConnectors);
  const tables = detectTables(artifacts.modelText || allText, queries);
  const measures = detectMeasures(artifacts.modelText || allText);
  const calcColumns = detectCalcColumns(artifacts.modelText || allText);
  const visuals = detectVisuals(artifacts.layoutText || allText);

  const nodes = [];
  const edges = [];

  const sourceNodes = detectedConnectors.map((connector) => connectorNode(connector.name, connector));
  nodes.push(...sourceNodes);

  const queryNodes = queries.map((query) => queryNode(query.name, query.expression));
  nodes.push(...queryNodes);

  const tableNodes = tables.map(modelNode);
  nodes.push(...tableNodes);

  const measureNodes = measures.map(measureNode);
  nodes.push(...measureNodes);

  const calcColumnNodes = calcColumns.map(calcColumnNode);
  nodes.push(...calcColumnNodes);

  const visualNodes = visuals.map(visualNode);
  nodes.push(...visualNodes);

  if (sourceNodes.length && queryNodes.length) {
    queryNodes.forEach((query) => {
      const matchingSources = sourceNodes.filter((source) => query.meta.expression.includes(source.meta.pattern));
      const sources = matchingSources.length ? matchingSources : sourceNodes;
      sources.forEach((source) => edges.push(edge(source.id, query.id, "uses connector")));
    });
  }

  if (queryNodes.length && tableNodes.length) {
    tableNodes.forEach((table, index) => {
      const query = queryNodes.find((item) => normalize(item.label) === normalize(table.label)) || queryNodes[index % queryNodes.length];
      edges.push(edge(query.id, table.id, "loads table"));
    });
  }

  if (tableNodes.length && measureNodes.length) {
    measureNodes.forEach((measure, index) => {
      edges.push(edge(tableNodes[index % tableNodes.length].id, measure.id, "feeds measure"));
    });
  }

  if (tableNodes.length && calcColumnNodes.length) {
    calcColumnNodes.forEach((cc, index) => {
      edges.push(edge(tableNodes[index % tableNodes.length].id, cc.id, "defines calc column"));
    });
  }

  if (measureNodes.length && visualNodes.length) {
    visualNodes.forEach((visual, index) => {
      edges.push(edge(measureNodes[index % measureNodes.length].id, visual.id, "renders visual"));
    });
  } else if (tableNodes.length && visualNodes.length) {
    visualNodes.forEach((visual, index) => {
      edges.push(edge(tableNodes[index % tableNodes.length].id, visual.id, "renders visual"));
    });
  }

  if (!nodes.length) {
    nodes.push({
      id: "file:pbix",
      type: "source",
      label: fileName,
      icon: "PBX",
      meta: {
        note: t().loadingNoBackend,
        expression: artifacts.diagnostics.join("\n")
      }
    });
  }

  return {
    nodes: uniqueById(nodes),
    edges: uniqueEdges(edges),
    warnings: artifacts.diagnostics
  };
}

export function detectConnectors(text) {
  return uniqueByName(CONNECTORS.filter((connector) => hasConnectorCall(text, connector.pattern)));
}

export function hasConnectorCall(text, pattern) {
  if (!text || !pattern) return false;
  const escaped = pattern.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return new RegExp(`(^|[^A-Za-z0-9_])${escaped}\\s*\\(`, "i").test(text);
}

export function detectQueries(text, connectors) {
  const names = new Set();
  const queryRegex = /(?:shared\s+)?#?"?([^"=\r\n;]{2,100})"?\s*=\s*let/gi;
  let match;
  while ((match = queryRegex.exec(text))) {
    names.add(match[1].trim());
  }

  if (!names.size && connectors.length) {
    connectors.forEach((connector) => names.add(`${connector.name} Query`));
  }

  return Array.from(names).slice(0, 18).map((name) => ({
    name,
    expression: snippetAround(text, name, 900) || text.slice(0, 900)
  }));
}

export function detectTables(text, queries) {
  const names = new Set();
  const tableRegexes = [
    /"name"\s*:\s*"([^"]{2,80})"\s*,\s*"columns"/g,
    /"tables"\s*:\s*\[[\s\S]*?"name"\s*:\s*"([^"]{2,80})"/g
  ];

  tableRegexes.forEach((regex) => {
    let match;
    while ((match = regex.exec(text))) names.add(match[1]);
  });

  if (!names.size) queries.forEach((query) => names.add(query.name.replace(/\s+Query$/i, "")));
  return Array.from(names).filter(Boolean).slice(0, 20);
}

export function detectMeasures(text) {
  const names = new Set();
  const measureRegex = /"name"\s*:\s*"([^"]{2,80})"\s*,\s*"expression"\s*:/g;
  let match;
  while ((match = measureRegex.exec(text))) names.add(match[1]);
  return Array.from(names).slice(0, 16);
}

export function detectCalcColumns(text) {
  // Calculated columns appear inside "columns" arrays in the model JSON with an "expression" field.
  const names = new Set();
  const calcColRegex = /"columns"\s*:\s*\[[\s\S]*?"name"\s*:\s*"([^"]{2,80})"\s*,[\s\S]*?"expression"\s*:\s*"[^"]{2,}/g;
  let match;
  while ((match = calcColRegex.exec(text))) names.add(match[1]);
  return Array.from(names).slice(0, 16);
}

export function detectVisuals(text) {
  const names = new Set();
  const visualRegex = /"visualType"\s*:\s*"([^"]{2,80})"/g;
  let match;
  while ((match = visualRegex.exec(text))) names.add(toTitle(match[1]));
  return Array.from(names).slice(0, 16);
}
