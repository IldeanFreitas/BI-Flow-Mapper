// ─── Painel de Relacionamentos (aba "Relationships") ───────────────────────
// Dona de #relEmpty/#relContent/#relDiagram/#relTable.
import { escapeHtml } from "./dom-utils.js";
import { els } from "./dom-refs.js";
import { state } from "./graph-model.js";
import { t } from "./i18n.js";

export function translateCrossFilter(val) {
  const T = t();
  const v = (val || "").toLowerCase();
  if (v.includes("bidi") || v.includes("both")) return T.demoCross2;
  return T.demoCross1;
}

export function renderRelationships() {
  const rels = state.relationships;

  if (!rels || rels.length === 0) {
    els.relEmpty.classList.remove("hidden");
    els.relContent.classList.add("hidden");
    return;
  }

  els.relEmpty.classList.add("hidden");
  els.relContent.classList.remove("hidden");

  renderRelDiagram(rels);
  renderRelTable(rels);
}

export function renderRelTable(rels) {
  const rows = rels.map((rel) => {
    const activeIcon = rel.active ? "✓" : "○";
    const activeCls  = rel.active ? "style=\"color:#28805a\"" : "style=\"color:#aaa\"";
    return `
      <tr>
        <td>${escapeHtml(rel.fromTable)}</td>
        <td style="color:var(--muted);font-size:12px">${escapeHtml(rel.fromColumn)}</td>
        <td>${escapeHtml(rel.toTable)}</td>
        <td style="color:var(--muted);font-size:12px">${escapeHtml(rel.toColumn)}</td>
        <td><span class="cardinality-badge">${escapeHtml(rel.cardinality)}</span></td>
        <td><span class="cross-filter-badge">${escapeHtml(translateCrossFilter(rel.crossFilter))}</span></td>
        <td ${activeCls}>${activeIcon}</td>
      </tr>`;
  }).join("");

  els.relTable.innerHTML = `
    <table class="rel-table" aria-label="${t().relTableAriaLabel}">
      <thead>
        <tr>
          <th>${t().relFromTable}</th>
          <th>${t().relFromCol}</th>
          <th>${t().relToTable}</th>
          <th>${t().relToCol}</th>
          <th>${t().relCardinality}</th>
          <th>${t().relCrossFilter}</th>
          <th>${t().relActive}</th>
        </tr>
      </thead>
      <tbody>
        ${rows || `<tr class="rel-empty-row"><td colspan="7">${t().relNoData}</td></tr>`}
      </tbody>
    </table>`;
}

export function renderRelDiagram(rels) {
  const tableNames = [...new Set(rels.flatMap((r) => [r.fromTable, r.toTable]))].sort();
  const count = tableNames.length;
  if (count === 0) { els.relDiagram.innerHTML = ""; return; }

  // ── Layout: force-directed seed — tables in a smart grid ──────────────────
  const NODE_W  = 180;
  const NODE_H  = 52;
  const COLS    = Math.min(count, Math.ceil(Math.sqrt(count * 1.8)));
  const ROWS    = Math.ceil(count / COLS);
  const CELL_W  = 260;
  const CELL_H  = 130;
  const PAD_X   = 48;
  const PAD_Y   = 48;
  const SVG_W   = Math.max(760, COLS * CELL_W + PAD_X * 2);
  const SVG_H   = Math.max(320, ROWS * CELL_H + PAD_Y * 2) + 60;

  const pos = {};
  tableNames.forEach((name, i) => {
    const col = i % COLS;
    const row = Math.floor(i / COLS);
    pos[name] = {
      x: PAD_X + col * CELL_W + (CELL_W - NODE_W) / 2,
      y: PAD_Y + row * CELL_H + (CELL_H - NODE_H) / 2,
      cx: PAD_X + col * CELL_W + CELL_W / 2,
      cy: PAD_Y + row * CELL_H + CELL_H / 2,
    };
  });

  // ── Crow's foot end markers ──────────────────────────────────────────────
  // One side (from) → many side (to) for M:1 / 1:M / 1:1 / M:M
  function crowsFoot(id, type, color) {
    // type: "one" | "many" | "one-mandatory" | "many-mandatory"
    if (type === "many") {
      return `<marker id="${id}" viewBox="-2 -6 14 12" refX="12" refY="0"
        markerWidth="14" markerHeight="12" orient="auto">
        <line x1="0" y1="-5" x2="10" y2="0" stroke="${color}" stroke-width="1.8"/>
        <line x1="0" y1="5"  x2="10" y2="0" stroke="${color}" stroke-width="1.8"/>
        <line x1="0" y1="0"  x2="10" y2="0" stroke="${color}" stroke-width="1.8"/>
      </marker>`;
    }
    // "one" — single vertical bar
    return `<marker id="${id}" viewBox="-2 -6 12 12" refX="10" refY="0"
      markerWidth="12" markerHeight="12" orient="auto">
      <line x1="8" y1="-5" x2="8" y2="5"  stroke="${color}" stroke-width="1.8"/>
      <line x1="4" y1="-5" x2="4" y2="5"  stroke="${color}" stroke-width="1.8"/>
    </marker>`;
  }

  // Parse cardinality string (e.g. "M:1", "1:M", "1:1", "M:M") → {from, to}
  function parseCard(card) {
    const parts = String(card).split(":");
    const fromSide = parts[0] === "1" ? "one" : "many";
    const toSide   = (parts[1] || "") === "1" ? "one" : "many";
    return { fromSide, toSide };
  }

  // ── Build edge paths ─────────────────────────────────────────────────────
  const defs = [];
  const edges = [];
  const labels = [];

  rels.forEach((rel, i) => {
    const fp = pos[rel.fromTable];
    const tp = pos[rel.toTable];
    if (!fp || !tp) return;

    const active  = rel.active !== false;
    const color   = active ? "#0078D4" : "#A19F9D";
    const dash    = active ? "" : `stroke-dasharray="6,4"`;
    const { fromSide, toSide } = parseCard(rel.cardinality);

    const midFromId = `mf${i}`;
    const midToId   = `mt${i}`;
    defs.push(crowsFoot(midFromId, fromSide, color));
    defs.push(crowsFoot(midToId,   toSide,   color));
    const translatedCF = translateCrossFilter(rel.crossFilter);

    // Connection points: pick nearest edge of each node
    const fcx = fp.cx; const fcy = fp.cy;
    const tcx = tp.cx; const tcy = tp.cy;
    const dx  = tcx - fcx;
    const dy  = tcy - fcy;

    // Exit/enter from left or right depending on relative position
    let x1, y1, x2, y2, cp1x, cp1y, cp2x, cp2y;
    const sameRow = Math.abs(dy) < CELL_H * 0.5;

    if (sameRow) {
      // Horizontal connection
      if (dx > 0) {
        x1 = fp.x + NODE_W; y1 = fp.y + NODE_H / 2;
        x2 = tp.x;           y2 = tp.y + NODE_H / 2;
      } else {
        x1 = fp.x;           y1 = fp.y + NODE_H / 2;
        x2 = tp.x + NODE_W;  y2 = tp.y + NODE_H / 2;
      }
      const gap = Math.abs(x2 - x1) * 0.45;
      cp1x = x1 + (dx > 0 ? gap : -gap); cp1y = y1;
      cp2x = x2 - (dx > 0 ? gap : -gap); cp2y = y2;
    } else {
      // Vertical / diagonal: exit bottom or top
      if (dy > 0) {
        x1 = fp.x + NODE_W / 2; y1 = fp.y + NODE_H;
        x2 = tp.x + NODE_W / 2; y2 = tp.y;
      } else {
        x1 = fp.x + NODE_W / 2; y1 = fp.y;
        x2 = tp.x + NODE_W / 2; y2 = tp.y + NODE_H;
      }
      const gap = Math.abs(y2 - y1) * 0.45;
      cp1x = x1; cp1y = y1 + (dy > 0 ? gap : -gap);
      cp2x = x2; cp2y = y2 - (dy > 0 ? gap : -gap);
    }

    edges.push(`
      <path d="M ${x1} ${y1} C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${x2} ${y2}"
        fill="none" stroke="${color}" stroke-width="${active ? 2 : 1.5}" ${dash}
        marker-start="url(#${midFromId})"
        marker-end="url(#${midToId})"/>`);

    // Cardinality pill label at midpoint
    const mx = (x1 + x2) / 2;
    const my = (y1 + y2) / 2;
    const cardText = String(rel.cardinality);
    const labelW = cardText.length * 7.5 + 14;
    const labelH = 20;

    // Cross-filter icon (↔ or →)
    const cfIcon = (rel.crossFilter || "").toLowerCase().includes("bidi") ||
                   (rel.crossFilter || "").toLowerCase().includes("both") ? "⇄" : "→";

    labels.push(`
      <g transform="translate(${mx - labelW / 2}, ${my - labelH / 2 - 2})">
        <rect width="${labelW}" height="${labelH}" rx="4"
              fill="${active ? "#EFF6FF" : "#F3F2F1"}"
              stroke="${color}" stroke-width="1" opacity="0.97"/>
        <text x="${labelW / 2}" y="${labelH / 2 + 4.5}" text-anchor="middle"
              font-family="'Cascadia Code','Consolas',monospace"
              font-size="10.5" font-weight="700" fill="${color}">${escapeHtml(cardText)}</text>
      </g>
      <text x="${mx}" y="${my + labelH / 2 + 11}" text-anchor="middle"
            font-family="Segoe UI,Arial,sans-serif" font-size="9.5"
            fill="${active ? "#0078D4" : "#A19F9D"}" opacity="0.75">${cfIcon} ${escapeHtml(translatedCF)}</text>`);
  });

  // ── Table node cards ─────────────────────────────────────────────────────
  // Collect columns referenced per table
  const colsByTable = {};
  rels.forEach((rel) => {
    [rel.fromTable, rel.toTable].forEach((tbl) => { if (!colsByTable[tbl]) colsByTable[tbl] = new Set(); });
    if (rel.fromColumn) colsByTable[rel.fromTable].add(rel.fromColumn);
    if (rel.toColumn)   colsByTable[rel.toTable].add(rel.toColumn);
  });

  const tableCards = tableNames.map((name) => {
    const { x, y } = pos[name];
    const cols = [...(colsByTable[name] || [])].slice(0, 4);
    const cardH = NODE_H + cols.length * 18;
    const shortName = name.length > 22 ? name.slice(0, 20) + "…" : name;

    // Column rows
    const colRows = cols.map((col, ci) => {
      const cy = NODE_H + 4 + ci * 18;
      const isKey = col.toLowerCase().includes("id") || col.toLowerCase().includes("key");
      return `
        <line x1="0" y1="${cy - 1}" x2="${NODE_W}" y2="${cy - 1}" stroke="#E1DFDD" stroke-width="1"/>
        <text x="10" y="${cy + 11}" font-family="Segoe UI,Arial,sans-serif"
              font-size="10" fill="${isKey ? "#0078D4" : "#605E5C"}">
          ${isKey ? "🔑 " : ""}${escapeHtml(col.length > 26 ? col.slice(0, 24) + "…" : col)}
        </text>`;
    }).join("");

    return `
      <g transform="translate(${x}, ${y})">
        <!-- Drop shadow -->
        <rect x="3" y="3" width="${NODE_W}" height="${cardH}" rx="8"
              fill="rgba(0,0,0,0.08)"/>
        <!-- Card background -->
        <rect width="${NODE_W}" height="${cardH}" rx="8"
              fill="white" stroke="#C8C6C4" stroke-width="1"/>
        <!-- Header bar -->
        <rect width="${NODE_W}" height="${NODE_H}" rx="8" fill="#107C10"/>
        <rect y="${NODE_H - 8}" width="${NODE_W}" height="8" fill="#107C10"/>
        <!-- Table icon -->
        <rect x="10" y="10" width="26" height="26" rx="5" fill="rgba(255,255,255,0.18)"/>
        <text x="23" y="28" text-anchor="middle"
              font-family="Segoe UI,Arial,sans-serif" font-size="13">🗄</text>
        <!-- Table name -->
        <text x="${NODE_W / 2 + 6}" y="29" text-anchor="middle"
              font-family="Segoe UI,Arial,sans-serif" font-size="11.5"
              font-weight="700" fill="white">${escapeHtml(shortName)}</text>
        <!-- Column rows -->
        ${colRows}
      </g>`;
  }).join("");

  // ── Legend ────────────────────────────────────────────────────────────────
  const legendY = SVG_H - 26;
  const legend = `
    <g transform="translate(${PAD_X}, ${legendY})">
      <line x1="0" y1="8" x2="28" y2="8" stroke="#0078D4" stroke-width="2"
            marker-end="url(#leg-many)" marker-start="url(#leg-one)"/>
      <text x="34" y="12" font-family="Segoe UI,Arial,sans-serif" font-size="10" fill="#605E5C">${t().relActive}</text>
      <line x1="90" y1="8" x2="118" y2="8" stroke="#A19F9D" stroke-width="1.5"
            stroke-dasharray="5,3"/>
      <text x="124" y="12" font-family="Segoe UI,Arial,sans-serif" font-size="10" fill="#605E5C">${t().relInactive}</text>
      <defs>
        <marker id="leg-many" viewBox="-2 -6 14 12" refX="12" refY="0"
          markerWidth="12" markerHeight="10" orient="auto">
          <line x1="0" y1="-4" x2="9" y2="0" stroke="#0078D4" stroke-width="1.5"/>
          <line x1="0" y1="4"  x2="9" y2="0" stroke="#0078D4" stroke-width="1.5"/>
          <line x1="0" y1="0"  x2="9" y2="0" stroke="#0078D4" stroke-width="1.5"/>
        </marker>
        <marker id="leg-one" viewBox="-2 -6 12 12" refX="10" refY="0"
          markerWidth="10" markerHeight="10" orient="auto-start-reverse">
          <line x1="6" y1="-4" x2="6" y2="4" stroke="#0078D4" stroke-width="1.5"/>
          <line x1="2" y1="-4" x2="2" y2="4" stroke="#0078D4" stroke-width="1.5"/>
        </marker>
      </defs>
    </g>`;

  els.relDiagram.innerHTML = `
    <svg viewBox="0 0 ${SVG_W} ${SVG_H}" width="${SVG_W}" height="${SVG_H}"
         xmlns="http://www.w3.org/2000/svg"
         style="display:block;font-family:Segoe UI,Arial,sans-serif">
      <defs>${defs.join("")}</defs>
      ${edges.join("")}
      ${tableCards}
      ${labels.join("")}
      ${legend}
    </svg>`;
}

// ─── Fim Relacionamentos ───────────────────────────────────────────────────────
