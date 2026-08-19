// ─── Arquitetura (aba "Architecture") ──────────────────────────────────────
// Dona de #archEmpty/#archContent/#archDiagram.
import { escapeHtml } from "./dom-utils.js";
import { els } from "./dom-refs.js";
import { state, initials } from "./graph-model.js";
import { t } from "./i18n.js";

/**
 * Builds architecture data: for each source node, collects the queries that
 * depend on it and extracts the connection path from the M expression
 * (the value after "Source =" or the first connector call arguments).
 */
export function buildArchitectureData(graph) {
  const nodes = graph.nodes || [];
  const edges = graph.edges || [];

  const sourceNodes = nodes.filter((n) => n.type === "source");
  const queryNodes  = nodes.filter((n) => n.type === "query");

  // Map source id -> queries that depend on it
  const sourceToQueries = new Map(sourceNodes.map((s) => [s.id, []]));

  edges.forEach((e) => {
    if (sourceToQueries.has(e.from)) {
      const query = queryNodes.find((q) => q.id === e.to);
      if (query) sourceToQueries.get(e.from).push(query);
    }
  });

  return sourceNodes.map((source) => {
    const queriesForSource = sourceToQueries.get(source.id) || [];

    const queries = queriesForSource.map((q) => {
      const expr = (q.meta && q.meta.expression) ? q.meta.expression : "";
      const precomputed = (q.meta && q.meta.connectionPath) ? q.meta.connectionPath : null;
      return {
        name: q.label,
        connectionPath: precomputed !== null ? precomputed : extractConnectionPath(expr, source),
        expression: expr,
      };
    });

    // If no queries are linked but source has its own pattern, show a path
    const sourceExpr = (source.meta && source.meta.expression) ? source.meta.expression : "";
    const fallbackPath = queries.length === 0 && sourceExpr
      ? extractConnectionPath(sourceExpr, source)
      : "";

    return {
      sourceId:   source.id,
      sourceName: source.label,
      iconUrl:    source.iconUrl || "",
      icon:       source.icon || initials(source.label),
      color:      (source.meta && source.meta.color) ? source.meta.color : "#2176ae",
      fallbackPath,
      queries,
    };
  });
}

/**
 * Extracts the human-readable connection path from an M expression.
 * Looks for:
 *   1. Source = ConnectorFunction("arg1", "arg2", ...)  — first string args
 *   2. File.Path = "..." or path = "..."
 *   3. url = "..."
 *   4. Fallback: first quoted string in the expression
 */
export function extractConnectionPath(expr, source) {
  if (!expr) return "";

  // Pattern: ConnectorFunction("server", "database") or ("url") — get args
  const pattern = (source.meta && source.meta.pattern) ? source.meta.pattern : "";
  if (pattern) {
    const escaped = pattern.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    // Match ConnectorFunc("arg1"[, "arg2"])
    const callRx = new RegExp(escaped + '\\s*\\(([^)]{0,400})\\)', 'i');
    const callMatch = expr.match(callRx);
    if (callMatch) {
      const argsStr = callMatch[1];
      const args = [];
      const argRx = /"([^"]{1,300})"/g;
      let m;
      while ((m = argRx.exec(argsStr)) !== null) args.push(m[1]);
      if (args.length) return args.join(" › ");
    }
  }

  // "Source = SomeFunc("path")" — generic
  const sourceAssign = expr.match(/[Ss]ource\s*=\s*\w[\w.]*\s*\(([^)]{0,400})\)/);
  if (sourceAssign) {
    const args = [];
    const argRx = /"([^"]{1,300})"/g;
    let m;
    while ((m = argRx.exec(sourceAssign[1])) !== null) args.push(m[1]);
    if (args.length) return args.join(" › ");
  }

  // File path or URL patterns
  const pathPatterns = [
    /(?:FilePath|file_path|FileName|path)\s*=\s*"([^"]{1,400})"/i,
    /(?:url|URL|Url)\s*=\s*"([^"]{1,400})"/i,
    /https?:\/\/[^\s"']{4,200}/,
    /[A-Za-z]:[\\\/][^"'\r\n]{4,200}/,
    /\\\\[^"'\r\n]{4,200}/,
  ];
  for (const rx of pathPatterns) {
    const m = expr.match(rx);
    if (m) return m[1] || m[0];
  }

  // First quoted string of reasonable length
  const firstQuoted = expr.match(/"([^"]{3,200})"/);
  if (firstQuoted) return firstQuoted[1];

  return "";
}

export function renderArchitecture() {
  const arch = state.architecture;

  if (!arch || arch.length === 0) {
    els.archEmpty.classList.remove("hidden");
    els.archContent.classList.add("hidden");
    return;
  }

  els.archEmpty.classList.add("hidden");
  els.archContent.classList.remove("hidden");

  renderArchDiagram(arch);
}

export function renderArchDiagram(arch) {
  const CONNECTOR_COLORS = {
    "SQL Server":    "#0078D4",
    "Excel":         "#217346",
    "Web":           "#6f52b8",
    "SharePoint":    "#0b6a0b",
    "SharePoint Files": "#0b6a0b",
    "OData":         "#b23a48",
    "CSV":           "#d39200",
    "Folder":        "#4d6b7c",
    "JSON":          "#7a5c1f",
    "Analysis Services": "#5266b8",
    "Oracle":        "#c3423f",
    "PostgreSQL":    "#35668d",
    "MySQL":         "#c7762f",
    "Snowflake":     "#4197b5",
    "Databricks":    "#d64d39",
    "Power Platform Dataflows": "#4f7bd9",
    "Azure Blob Storage": "#0078D4",
    "Azure Data Lake": "#0078D4",
    "Google Analytics": "#d39200",
    "Salesforce":    "#2b8f9f",
    "SAP BW":        "#5266b8",
  };

  // Build source card HTML for each source
  const sourceCards = arch.map((src) => {
    const color = CONNECTOR_COLORS[src.sourceName] || src.color || "#2176ae";

    // Icon markup
    const iconMarkup = src.iconUrl
      ? `<img src="${escapeHtml(src.iconUrl)}" alt="" loading="lazy" onerror="this.style.display='none';this.nextElementSibling.style.display='block'" /><span class="arch-icon-text" style="display:none">${escapeHtml(src.icon)}</span>`
      : `<span class="arch-icon-text">${escapeHtml(src.icon)}</span>`;

    // Queries list
    let queriesHtml;
    if (src.queries && src.queries.length > 0) {
      queriesHtml = src.queries.map((q) => {
        const pathDisplay = q.connectionPath
          ? `<span class="arch-query-label">${escapeHtml(q.name)}</span><span class="arch-query-text">${escapeHtml(q.connectionPath)}</span>`
          : `<span class="arch-query-label">${escapeHtml(q.name)}</span>`;
        return `
          <div class="arch-query-item">
            <span class="arch-query-bullet"></span>
            <span>${pathDisplay}</span>
          </div>`;
      }).join("");
    } else if (src.fallbackPath) {
      queriesHtml = `
        <div class="arch-query-item">
          <span class="arch-query-bullet"></span>
          <span class="arch-query-text">${escapeHtml(src.fallbackPath)}</span>
        </div>`;
    } else {
      queriesHtml = `<div class="arch-no-queries">${escapeHtml(t().archNoQueries)}</div>`;
    }

    return `
      <div class="arch-source-card" style="border-top-color:${color}" data-source-id="${escapeHtml(src.sourceId)}">
        <div class="arch-source-header">
          <div class="arch-source-icon" style="background:${color}">
            ${iconMarkup}
          </div>
          <span class="arch-source-name">${escapeHtml(src.sourceName)}</span>
        </div>
        <div class="arch-queries-list">
          ${queriesHtml}
        </div>
      </div>`;
  }).join("");

  // Power BI target node
  const pbiNode = `
    <div class="arch-pbi-node">
      <div class="arch-pbi-badge">
        <img class="arch-pbi-logo" src="image/Power_BI_Logo.png" alt="Power BI"
             onerror="this.style.display='none';this.nextElementSibling.style.display='grid'" />
        <div class="arch-pbi-logo-fallback" style="display:none">PBI</div>
        <div>
          <div>Power BI</div>
          <div class="arch-pbi-label">${escapeHtml(t().archPbiLabel)}</div>
        </div>
      </div>
      <div style="font-size:11px;color:var(--muted);margin-top:4px">${escapeHtml(t().archSourcesCount(arch.length))}</div>
    </div>`;

  els.archDiagram.innerHTML = `
    <div class="arch-layout" id="archLayoutRoot">
      <div class="arch-sources-col" id="archSourcesCol">
        ${sourceCards}
      </div>
      <div class="arch-center-col" id="archCenterCol">
        <svg id="archSvg" class="arch-svg-layer" xmlns="http://www.w3.org/2000/svg"></svg>
      </div>
      <div class="arch-pbi-col" id="archPbiCol">
        ${pbiNode}
      </div>
    </div>`;

  // Draw SVG connector lines after DOM paint
  requestAnimationFrame(() => drawArchConnectors(arch));
}

export function drawArchConnectors(arch) {
  const layout   = document.getElementById("archLayoutRoot");
  const sourcesCol = document.getElementById("archSourcesCol");
  const pbiCol   = document.getElementById("archPbiCol");
  const svg      = document.getElementById("archSvg");
  if (!layout || !sourcesCol || !pbiCol || !svg) return;

  const layoutRect   = layout.getBoundingClientRect();
  const pbiRect      = pbiCol.getBoundingClientRect();
  const sourceCards  = sourcesCol.querySelectorAll(".arch-source-card");

  // Destination: left-center of the PBI badge
  const pbiX = pbiRect.left - layoutRect.left;
  const pbiY = pbiRect.top  - layoutRect.top + pbiRect.height / 2;

  // Set SVG to fill the center column
  const centerCol = document.getElementById("archCenterCol");
  const centerRect = centerCol.getBoundingClientRect();
  svg.setAttribute("width",  centerRect.width);
  svg.setAttribute("height", centerRect.height);
  svg.style.width  = centerRect.width  + "px";
  svg.style.height = centerRect.height + "px";

  const CONNECTOR_COLORS = {
    "SQL Server":  "#0078D4", "Excel": "#217346", "Web": "#6f52b8",
    "SharePoint":  "#0b6a0b", "SharePoint Files": "#0b6a0b",
    "OData":       "#b23a48", "CSV": "#d39200", "Folder": "#4d6b7c",
    "JSON":        "#7a5c1f", "Analysis Services": "#5266b8",
    "Oracle":      "#c3423f", "PostgreSQL": "#35668d", "MySQL": "#c7762f",
    "Snowflake":   "#4197b5", "Databricks": "#d64d39",
    "Power Platform Dataflows": "#4f7bd9",
    "Azure Blob Storage": "#0078D4", "Azure Data Lake": "#0078D4",
    "Google Analytics": "#d39200", "Salesforce": "#2b8f9f", "SAP BW": "#5266b8",
  };

  let paths = "";
  sourceCards.forEach((card, i) => {
    const cardRect = card.getBoundingClientRect();
    const srcX = cardRect.right  - layoutRect.left;
    const srcY = cardRect.top    - layoutRect.top + cardRect.height / 2;

    // Translate to SVG coordinate space (center col)
    const svgOffX = centerRect.left - layoutRect.left;
    const svgOffY = centerRect.top  - layoutRect.top;
    const x1 = srcX  - svgOffX;
    const y1 = srcY  - svgOffY;
    const x2 = pbiX  - svgOffX;
    const y2 = pbiY  - svgOffY;
    const cp = (x2 - x1) * 0.55;

    const srcName = arch[i] ? arch[i].sourceName : "";
    const color   = CONNECTOR_COLORS[srcName] || (arch[i] ? arch[i].color : "#8c98a3") || "#8c98a3";

    paths += `<path d="M ${x1} ${y1} C ${x1 + cp} ${y1}, ${x2 - cp} ${y2}, ${x2} ${y2}"
        fill="none" stroke="${color}" stroke-width="2.5" stroke-opacity="0.7"
        marker-end="url(#arch-arrow)"/>`;
  });

  svg.innerHTML = `
    <defs>
      <marker id="arch-arrow" viewBox="0 0 10 10" refX="10" refY="5"
              markerWidth="6" markerHeight="6" orient="auto-start-reverse">
        <path d="M 0 0 L 10 5 L 0 10 z" fill="#1B2A38" opacity="0.7"/>
      </marker>
    </defs>
    ${paths}`;
}

// ─── Fim Arquitetura ──────────────────────────────────────────────────────────
