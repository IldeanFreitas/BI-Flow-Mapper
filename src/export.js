// ─── Export (JSON / DOCX / PNG) ────────────────────────────────────────────
// Todo o export client-side: JSON do grafo, documentação Word (via backend),
// e as três imagens PNG (mapa, relacionamentos, arquitetura, páginas) —
// desenhadas em <canvas> a partir do DOM já renderizado.
import { escapeHtml } from "./dom-utils.js";
import { els } from "./dom-refs.js";
import { state, TYPE_LABELS_KEYS, slug } from "./graph-model.js";
import { t, locale } from "./i18n.js";

export function exportGraph() {
  const jsonStr = JSON.stringify(state.graph, null, 2);
  const blob = new Blob([jsonStr], { type: "application/json" });
  const filename = "bi-flow-mapper-lineage.json";

  // pywebview blocks link.click() — use the Python bridge when available
  if (window.pywebview && window.pywebview.api && window.pywebview.api.save_file) {
    const b64 = btoa(unescape(encodeURIComponent(jsonStr)));
    window.pywebview.api.save_file(b64, filename, "application/json")
      .then((result) => {
        if (result && !result.ok && result.reason !== "cancelled") {
          console.error("[BIFlowMapper] save_file error:", result.reason);
        }
      })
      .catch((err) => console.error("[BIFlowMapper] save_file exception:", err));
    return;
  }

  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

export async function exportDocumentation() {
  return exportServerDocumentation({
    endpoint: "/api/export-docx",
    button: els.exportDocxButton,
    extension: "docx",
    mimeType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    unavailableMessage: t().docxNoPbix,
    generatingMessage: t().docxGenerating,
    errorMessage: t().docxError,
    defaultButtonLabel: t().btnDocx,
    filenameSuffix: locale === "pt-BR" ? "documentacao" : "documentation"
  });
}

export async function exportHtmlDocumentation() {
  return exportServerDocumentation({
    endpoint: "/api/export-html",
    button: els.exportHtmlButton,
    extension: "html",
    mimeType: "text/html",
    unavailableMessage: t().htmlNoPbix,
    generatingMessage: t().htmlGenerating,
    errorMessage: t().htmlError,
    defaultButtonLabel: t().btnHtml,
    filenameSuffix: locale === "pt-BR" ? "documentacao" : "documentation"
  });
}

async function exportServerDocumentation({
  endpoint, button, extension, mimeType, unavailableMessage,
  generatingMessage, errorMessage, defaultButtonLabel, filenameSuffix
}) {
  if (!state.lastPbixFile) {
    alert(unavailableMessage);
    return;
  }

  const buttonText = button.querySelector(".btn-text");
  const previousText = buttonText.textContent;
  button.disabled = true;
  buttonText.textContent = generatingMessage;

  const form = new FormData();
  form.append("pbix", state.lastPbixFile, state.lastPbixFile.name);

  try {
    const response = await fetch(endpoint, {
      method: "POST",
      headers: {
        "X-BIFM-Locale": locale
      },
      body: form
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.error || `HTTP ${response.status}`);
    }

    const blob = await response.blob();
    const suggestedName =
      filenameFromDisposition(response.headers.get("Content-Disposition")) ||
      `${slug(state.lastPbixFile.name.replace(/\.[^.]+$/, ""))}_${filenameSuffix}.${extension}`;

    // pywebview blocks link.click() — use the Python bridge when available
    if (window.pywebview && window.pywebview.api && window.pywebview.api.save_file) {
      const b64 = await new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onloadend = () => resolve(reader.result.split(",")[1]);
        reader.onerror = reject;
        reader.readAsDataURL(blob);
      });
      const result = await window.pywebview.api.save_file(
        b64,
        suggestedName,
        mimeType
      );
      if (result && !result.ok && result.reason !== "cancelled") {
        throw new Error(result.reason);
      }
      return;
    }

    // Fallback: normal browser download
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = suggestedName;
    link.click();
    URL.revokeObjectURL(url);
  } catch (error) {
    console.error(error);
    alert(errorMessage);
  } finally {
    button.disabled = false;
    buttonText.textContent = previousText || defaultButtonLabel;
  }
}

export function filenameFromDisposition(value) {
  if (!value) return "";
  const utf8Match = value.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match) return decodeURIComponent(utf8Match[1]);
  const asciiMatch = value.match(/filename="?([^";]+)"?/i);
  return asciiMatch ? asciiMatch[1] : "";
}

// ── Exportar Imagem PNG ────────────────────────────────────────────────────────

export async function exportImage() {
  if (state.activeTab === "relacionamentos") return exportRelImage();
  if (state.activeTab === "arquitetura") return exportArchImage();
  if (state.activeTab === "paginas") return exportPagesImage();

  // Coleta os nós e edges atualmente visíveis no canvas DOM
  const cards = Array.from(els.graphCanvas.querySelectorAll(".node-card"));
  if (!cards.length) return;

  // Lê posição e dados de cada card diretamente do DOM
  const nodeRects = cards.map((card) => ({
    x:       parseInt(card.style.left,  10),
    y:       parseInt(card.style.top,   10),
    w:       220,
    h:       74,
    label:   card.querySelector(".node-title")?.textContent   || "",
    sub:     card.querySelector(".node-subtitle")?.textContent || "",
    icon:    card.querySelector(".icon-fallback")?.textContent?.trim() || "",
    iconUrl: card.querySelector(".connector-icon img")?.src || "",
    type:    [...card.classList].find((c) => TYPE_LABELS_KEYS.includes(c)) || "model",
    id:      card.dataset.nodeId || "",
    selected: card.classList.contains("selected"),
    impacted: card.classList.contains("impacted"),
    ancestor: card.classList.contains("ancestor"),
  }));
  const nodeById = new Map(nodeRects.map((node) => [node.id, node]));

  const iconPromises = nodeRects.map((node) => {
    if (!node.iconUrl) return Promise.resolve(null);
    return loadImageElement(node.iconUrl).catch(() => null);
  });
  const iconImages = await Promise.all(iconPromises);
  nodeRects.forEach((node, index) => { node.iconImage = iconImages[index]; });

  const TYPE_COLORS = {
    source:      "#0078D4",
    query:       "#F2C811",
    model:       "#107C10",
    measure:     "#D83B01",
    calc_column: "#9B5094",
    visual:      "#8764B8",
  };

  const PAD   = 48;
  const maxX  = Math.max(...nodeRects.map((n) => n.x + n.w)) + PAD;
  const maxY  = Math.max(...nodeRects.map((n) => n.y + n.h)) + PAD;
  const width = maxX + PAD;
  const height = maxY + PAD;
  const DPR   = 2; // resolução 2×

  const canvas = document.createElement("canvas");
  canvas.width  = width * DPR;
  canvas.height = height * DPR;

  const ctx = canvas.getContext("2d");
  ctx.scale(DPR, DPR);

  // Fundo igual ao canvas do mapa
  ctx.fillStyle = "#EEECEA";
  ctx.fillRect(0, 0, width, height);
  ctx.fillStyle = "#C8C6C4";
  const GRID = 24;
  const DOT = 1.25;
  for (let gx = 0; gx < width; gx += GRID) {
    for (let gy = 0; gy < height; gy += GRID) {
      ctx.beginPath();
      ctx.arc(gx + GRID / 2, gy + GRID / 2, DOT, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  // Lê edges do SVG atual
  const visibleIds = new Set(nodeRects.map((node) => node.id));
  const exportEdges = state.graph.edges.filter((edgeItem) => visibleIds.has(edgeItem.from) && visibleIds.has(edgeItem.to));

  exportEdges.forEach((edgeItem) => {
    const from = nodeById.get(edgeItem.from);
    const to = nodeById.get(edgeItem.to);
    if (!from || !to) return;

    const active = state.selectedId && (edgeItem.from === state.selectedId || to.impacted);
    const stroke = active ? "#b23a48" : "#8c98a3";
    const sw = active ? 3 : 2;
    drawCanvasEdge(ctx, from, to, PAD, stroke, sw);
  });

  // Desenha os nós
  nodeRects.forEach((n) => {
    const color = TYPE_COLORS[n.type] || "#2176ae";
    const x = n.x + PAD;
    const y = n.y + PAD;

    // Sombra
    ctx.save();
    ctx.shadowColor   = "rgba(23,33,43,0.13)";
    ctx.shadowBlur    = 18;
    ctx.shadowOffsetY = 6;

    // Card background
    roundRect(ctx, x, y, n.w, n.h, 8);
    ctx.fillStyle = "#ffffff";
    ctx.fill();

    ctx.restore();

    // Borda esquerda colorida
    roundRect(ctx, x, y, 5, n.h, [8, 0, 0, 8]);
    ctx.fillStyle = color;
    ctx.fill();

    // Borda de destaque (selecionado / impactado / ancestor)
    if (n.selected || n.impacted || n.ancestor) {
      const hlColor = n.impacted  ? "rgba(178,58,72,0.35)"
                    : n.ancestor  ? "rgba(33,118,174,0.3)"
                    :               "rgba(40,160,134,0.3)";
      roundRect(ctx, x - 2, y - 2, n.w + 4, n.h + 4, 10);
      ctx.strokeStyle = hlColor;
      ctx.lineWidth   = 3;
      ctx.stroke();
    }

    // Ícone colorido
    const iconSize = 36;
    const iconX    = x + 12;
    const iconY    = y + (n.h - iconSize) / 2;
    roundRect(ctx, iconX, iconY, iconSize, iconSize, 8);
    ctx.fillStyle = color;
    ctx.fill();

    if (n.iconImage) {
      const imgSize = 30;
      const imgOffset = (iconSize - imgSize) / 2;
      ctx.drawImage(n.iconImage, iconX + imgOffset, iconY + imgOffset, imgSize, imgSize);
    } else {
      ctx.fillStyle   = "#ffffff";
      ctx.font        = `800 11px Inter, Segoe UI, Arial, sans-serif`;
      ctx.textAlign   = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(n.icon.slice(0, 4), iconX + iconSize / 2, iconY + iconSize / 2);
    }

    // Label principal
    ctx.fillStyle    = "#17212b";
    ctx.font         = `700 13px Inter, Segoe UI, Arial, sans-serif`;
    ctx.textAlign    = "left";
    ctx.textBaseline = "alphabetic";
    const textX = x + 12 + iconSize + 10;
    const maxW  = n.w - iconSize - 34;
    ctx.fillText(truncateText(ctx, n.label, maxW), textX, y + 30);

    // Subtítulo
    ctx.fillStyle = "#5d6b78";
    ctx.font      = `400 11px Inter, Segoe UI, Arial, sans-serif`;
    ctx.fillText(n.sub, textX, y + 48);
  });

  // Rodapé com nome do arquivo e data
  const title     = els.title.textContent || "BI Flow Mapper";
  const timestamp = t().exportTimestamp();
  ctx.fillStyle   = "rgba(93,107,120,0.7)";
  ctx.font        = `400 11px Inter, Segoe UI, Arial, sans-serif`;
  ctx.textAlign   = "right";
  ctx.textBaseline = "alphabetic";
  ctx.fillText(`${title}  ·  ${timestamp}`, maxX + PAD - 8, maxY + PAD - 10);

  // Download — usa downloadCanvas() para compatibilidade com pywebview
  const filename = (title.replace(/[^a-z0-9]/gi, "_").toLowerCase() || "lineage") + ".png";
  downloadCanvas(canvas, filename);
}

export function exportRelImage() {
  const svg = els.relDiagram.querySelector("svg");
  if (!svg) return;

  const width = parseInt(svg.getAttribute("width") || svg.viewBox.baseVal.width, 10) || 960;
  const height = parseInt(svg.getAttribute("height") || svg.viewBox.baseVal.height, 10) || 420;
  const xml = new XMLSerializer().serializeToString(svg);
  const blob = new Blob([xml], { type: "image/svg+xml;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const img = new Image();
  img.onload = () => {
    const canvas = document.createElement("canvas");
    const DPR = 2;
    canvas.width = width * DPR;
    canvas.height = height * DPR;
    const ctx = canvas.getContext("2d");
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    ctx.drawImage(img, 0, 0, width, height);
    downloadCanvas(canvas, exportFilename());
    URL.revokeObjectURL(url);
  };
  img.onerror = () => URL.revokeObjectURL(url);
  img.src = url;
}

export async function exportArchImage() {
  const arch = state.architecture;
  if (!arch || !arch.length) return;

  // ── 1. Gather DOM measurements from the live rendered layout ──────────────
  const layout    = document.getElementById("archLayoutRoot");
  const pbiCol    = document.getElementById("archPbiCol");
  const sourcesCol = document.getElementById("archSourcesCol");
  const archSvg   = document.getElementById("archSvg");
  if (!layout || !pbiCol || !sourcesCol) {
    // Fallback: tab not yet rendered — switch to it briefly, then retry
    return;
  }

  const DPR     = 2;
  const PAD     = 32; // extra whitespace around entire diagram
  const layoutR = layout.getBoundingClientRect();

  // Measure every source card
  const cardEls = Array.from(sourcesCol.querySelectorAll(".arch-source-card"));

  // Measure PBI node
  const pbiNodeEl = pbiCol.querySelector(".arch-pbi-node");
  const pbiR = pbiNodeEl
    ? pbiNodeEl.getBoundingClientRect()
    : pbiCol.getBoundingClientRect();

  // Total canvas size = layout bounding box + padding
  const totalW = layoutR.width  + PAD * 2;
  const totalH = layoutR.height + PAD * 2;

  const canvas = document.createElement("canvas");
  canvas.width  = totalW * DPR;
  canvas.height = totalH * DPR;
  const ctx = canvas.getContext("2d");
  ctx.scale(DPR, DPR);

  // ── 2. Background — same dotted canvas as live ─────────────────────────────
  ctx.fillStyle = "#EEECEA";
  ctx.fillRect(0, 0, totalW, totalH);
  ctx.fillStyle = "#C8C6C4";
  const GRID = 24;
  for (let gx = 0; gx < totalW; gx += GRID)
    for (let gy = 0; gy < totalH; gy += GRID) {
      ctx.beginPath();
      ctx.arc(gx + GRID / 2, gy + GRID / 2, 1.25, 0, Math.PI * 2);
      ctx.fill();
    }

  // Helper: convert page rect → canvas coords
  function toCanvas(r) {
    return {
      x: r.left - layoutR.left + PAD,
      y: r.top  - layoutR.top  + PAD,
      w: r.width,
      h: r.height,
    };
  }

  // ── 3. Pre-load connector icons as Image elements ─────────────────────────
  const iconImgMap = {};
  await Promise.all(arch.map(async (src) => {
    if (!src.iconUrl) return;
    try { iconImgMap[src.iconUrl] = await loadImageElement(src.iconUrl); }
    catch { /* skip */ }
  }));
  let pbiLogoImg = null;
  try { pbiLogoImg = await loadImageElement("image/Power_BI_Logo.png"); }
  catch { /* skip */ }

  // ── 4. Draw connector curves (read from live SVG paths) ───────────────────
  const CONNECTOR_COLORS = {
    "SQL Server": "#0078D4", "Excel": "#217346", "Web": "#6f52b8",
    "SharePoint": "#0b6a0b", "SharePoint Files": "#0b6a0b",
    "OData": "#b23a48", "CSV": "#d39200", "Folder": "#4d6b7c",
    "JSON": "#7a5c1f", "Analysis Services": "#5266b8",
    "Oracle": "#c3423f", "PostgreSQL": "#35668d", "MySQL": "#c7762f",
    "Snowflake": "#4197b5", "Databricks": "#d64d39",
    "Power Platform Dataflows": "#4f7bd9",
    "Azure Blob Storage": "#0078D4", "Azure Data Lake": "#0078D4",
    "Google Analytics": "#d39200", "Salesforce": "#2b8f9f", "SAP BW": "#5266b8",
  };

  // PBI badge entry point
  const pbiC = toCanvas(pbiR);
  const pbiEntryX = pbiC.x;
  const pbiEntryY = pbiC.y + pbiC.h / 2;

  // Arrow head helper
  function drawArrowHead(x, y, angle, color) {
    const size = 9;
    ctx.save();
    ctx.translate(x, y);
    ctx.rotate(angle);
    ctx.fillStyle = color;
    ctx.globalAlpha = 0.75;
    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.lineTo(-size, -size * 0.45);
    ctx.lineTo(-size,  size * 0.45);
    ctx.closePath();
    ctx.fill();
    ctx.globalAlpha = 1;
    ctx.restore();
  }

  cardEls.forEach((cardEl, i) => {
    const cardR = toCanvas(cardEl.getBoundingClientRect());
    const srcName = arch[i] ? arch[i].sourceName : "";
    const color   = CONNECTOR_COLORS[srcName] || (arch[i] ? arch[i].color : "#8c98a3") || "#8c98a3";

    const x1 = cardR.x + cardR.w;
    const y1 = cardR.y + cardR.h / 2;
    const x2 = pbiEntryX;
    const y2 = pbiEntryY;
    const cp = (x2 - x1) * 0.55;

    ctx.save();
    ctx.strokeStyle = color;
    ctx.lineWidth   = 2.5;
    ctx.globalAlpha = 0.7;
    ctx.beginPath();
    ctx.moveTo(x1, y1);
    ctx.bezierCurveTo(x1 + cp, y1, x2 - cp, y2, x2, y2);
    ctx.stroke();
    ctx.globalAlpha = 1;
    ctx.restore();

    // Arrowhead at destination
    const angle = Math.atan2(y2 - (y1 * 0.05 + y2 * 0.95), x2 - (x1 * 0.05 + x2 * 0.95));
    drawArrowHead(x2, y2, angle, "#1B2A38");
  });

  // ── 5. Draw each source card ───────────────────────────────────────────────
  function roundRectPath(x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.lineTo(x + w - r, y);
    ctx.quadraticCurveTo(x + w, y, x + w, y + r);
    ctx.lineTo(x + w, y + h - r);
    ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
    ctx.lineTo(x + r, y + h);
    ctx.quadraticCurveTo(x, y + h, x, y + h - r);
    ctx.lineTo(x, y + r);
    ctx.quadraticCurveTo(x, y, x + r, y);
    ctx.closePath();
  }

  cardEls.forEach((cardEl, i) => {
    const src   = arch[i];
    const cardR = toCanvas(cardEl.getBoundingClientRect());
    const { x, y, w, h } = cardR;
    const color = CONNECTOR_COLORS[src.sourceName] || src.color || "#2176ae";
    const RAD   = 10;
    const TOP_BAR = 4;

    // Shadow
    ctx.save();
    ctx.shadowColor   = "rgba(23,33,43,0.13)";
    ctx.shadowBlur    = 16;
    ctx.shadowOffsetY = 5;
    roundRectPath(x, y, w, h, RAD);
    ctx.fillStyle = "#ffffff";
    ctx.fill();
    ctx.restore();

    // Border
    roundRectPath(x, y, w, h, RAD);
    ctx.strokeStyle = "#C8C6C4";
    ctx.lineWidth   = 1.5;
    ctx.stroke();

    // Top colour bar
    ctx.save();
    ctx.beginPath();
    ctx.moveTo(x + RAD, y);
    ctx.lineTo(x + w - RAD, y);
    ctx.quadraticCurveTo(x + w, y, x + w, y + RAD);
    ctx.lineTo(x + w, y + TOP_BAR);
    ctx.lineTo(x, y + TOP_BAR);
    ctx.lineTo(x, y + RAD);
    ctx.quadraticCurveTo(x, y, x + RAD, y);
    ctx.closePath();
    ctx.fillStyle = color;
    ctx.fill();
    ctx.restore();

    // ── Header: read exact dimensions from DOM elements ────────────────────
    const headerEl = cardEl.querySelector(".arch-source-header");
    const iconEl   = cardEl.querySelector(".arch-source-icon");
    const nameEl   = cardEl.querySelector(".arch-source-name");

    const headerR = headerEl ? toCanvas(headerEl.getBoundingClientRect()) : null;
    const iconR   = iconEl   ? toCanvas(iconEl.getBoundingClientRect())   : null;
    const nameR   = nameEl   ? toCanvas(nameEl.getBoundingClientRect())   : null;

    // Icon box
    if (iconR) {
      roundRectPath(iconR.x, iconR.y, iconR.w, iconR.h, 4);
      ctx.fillStyle = color;
      ctx.fill();

      const iconImg = src.iconUrl ? iconImgMap[src.iconUrl] : null;
      if (iconImg) {
        const pad = 4;
        ctx.drawImage(iconImg, iconR.x + pad, iconR.y + pad, iconR.w - pad * 2, iconR.h - pad * 2);
      } else {
        ctx.fillStyle    = "#fff";
        ctx.font         = `800 9px Segoe UI, Arial, sans-serif`;
        ctx.textAlign    = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(src.icon || "SRC", iconR.x + iconR.w / 2, iconR.y + iconR.h / 2);
      }
    }

    // Source name
    if (nameR) {
      ctx.fillStyle    = "#201F1E";
      ctx.font         = `700 13px Segoe UI, Arial, sans-serif`;
      ctx.textAlign    = "left";
      ctx.textBaseline = "middle";
      ctx.fillText(
        truncateText(ctx, src.sourceName, nameR.w),
        nameR.x, nameR.y + nameR.h / 2
      );
    }

    // Header divider line
    if (headerR) {
      ctx.strokeStyle = "#E1DFDD";
      ctx.lineWidth   = 1;
      ctx.beginPath();
      ctx.moveTo(x + 1,     headerR.y + headerR.h);
      ctx.lineTo(x + w - 1, headerR.y + headerR.h);
      ctx.stroke();
    }

    // ── Query rows ─────────────────────────────────────────────────────────
    // Helper: wraps text character-by-character (mirrors CSS overflow-wrap:anywhere)
    // Returns array of line strings that each fit within maxW.
    function wrapText(str, maxW) {
      const words = str.split(/(?<=[\/\-_. ])/); // split after natural break chars
      const lines = [];
      let current = "";
      for (const chunk of words) {
        const test = current + chunk;
        if (ctx.measureText(test).width <= maxW) {
          current = test;
        } else {
          // chunk itself wider than maxW — break character by character
          if (ctx.measureText(chunk).width > maxW) {
            // flush current first
            if (current) { lines.push(current); current = ""; }
            let part = "";
            for (const ch of chunk) {
              if (ctx.measureText(part + ch).width > maxW) {
                if (part) lines.push(part);
                part = ch;
              } else {
                part += ch;
              }
            }
            current = part;
          } else {
            if (current) lines.push(current);
            current = chunk;
          }
        }
      }
      if (current) lines.push(current);
      return lines;
    }

    const queryItems = cardEl.querySelectorAll(".arch-query-item");
    queryItems.forEach((item) => {
      const iR    = toCanvas(item.getBoundingClientRect());
      const label = item.querySelector(".arch-query-label")?.textContent?.trim() || "";
      const text  = item.querySelector(".arch-query-text")?.textContent?.trim()  || "";

      // Layout constants mirroring CSS:
      // .arch-query-item { padding: 7px 14px; gap: 8px }
      // .arch-query-bullet { width:6px; margin-top:4px }
      const ITEM_PAD_TOP = 7;
      const BULLET_X     = iR.x + 14 + 3;
      const TEXT_X       = iR.x + 14 + 6 + 8;
      const maxTextW     = (iR.x + iR.w - 14) - TEXT_X;

      // Bullet aligned with first line cap-height
      const bulletCY = iR.y + ITEM_PAD_TOP + 5;
      ctx.beginPath();
      ctx.arc(BULLET_X, bulletCY, 3, 0, Math.PI * 2);
      ctx.fillStyle = "#F2C811";
      ctx.fill();

      let lineY = iR.y + ITEM_PAD_TOP + 11; // baseline of first line

      if (label) {
        ctx.fillStyle    = "#605E5C";
        ctx.font         = `600 11px Segoe UI, Arial, sans-serif`;
        ctx.textAlign    = "left";
        ctx.textBaseline = "alphabetic";
        const labelLines = wrapText(label, maxTextW);
        labelLines.forEach((ln) => {
          ctx.fillText(ln, TEXT_X, lineY);
          lineY += 14;
        });
      }

      if (text) {
        ctx.fillStyle    = "#201F1E";
        ctx.font         = `400 10px Cascadia Code, Consolas, monospace`;
        ctx.textAlign    = "left";
        ctx.textBaseline = "alphabetic";
        const textLines = wrapText(text, maxTextW);
        textLines.forEach((ln) => {
          ctx.fillText(ln, TEXT_X, lineY);
          lineY += 13;
        });
      }

      // row separator
      ctx.strokeStyle = "#E1DFDD";
      ctx.lineWidth   = 1;
      ctx.beginPath();
      ctx.moveTo(x + 1,     iR.y + iR.h);
      ctx.lineTo(x + w - 1, iR.y + iR.h);
      ctx.stroke();
    });

    // No-queries label
    const noQ = cardEl.querySelector(".arch-no-queries");
    if (noQ) {
      const nR = toCanvas(noQ.getBoundingClientRect());
      ctx.fillStyle    = "#605E5C";
      ctx.font         = `italic 11px Segoe UI, Arial, sans-serif`;
      ctx.textAlign    = "left";
      ctx.textBaseline = "middle";
      ctx.fillText(noQ.textContent.trim(), nR.x, nR.y + nR.h / 2);
    }
  });

  // ── 6. Draw Power BI badge ─────────────────────────────────────────────────
  const pbiEl = pbiNodeEl;
  if (pbiEl) {
    const badgeEl = pbiEl.querySelector(".arch-pbi-badge");
    const bR      = badgeEl ? toCanvas(badgeEl.getBoundingClientRect()) : pbiC;

    // Shadow
    ctx.save();
    ctx.shadowColor   = "rgba(23,33,43,0.2)";
    ctx.shadowBlur    = 24;
    ctx.shadowOffsetY = 8;
    roundRectPath(bR.x, bR.y, bR.w, bR.h, 10);
    ctx.fillStyle = "#1B2A38";
    ctx.fill();
    ctx.restore();

    // Badge fill (no shadow)
    roundRectPath(bR.x, bR.y, bR.w, bR.h, 10);
    ctx.fillStyle = "#1B2A38";
    ctx.fill();

    // PBI logo
    const logoSize = 40;
    const logoX    = bR.x + 18;
    const logoY    = bR.y + (bR.h - logoSize) / 2;
    if (pbiLogoImg) {
      ctx.drawImage(pbiLogoImg, logoX, logoY, logoSize, logoSize);
    } else {
      roundRectPath(logoX, logoY, logoSize, logoSize, 6);
      ctx.fillStyle = "#F2C811";
      ctx.fill();
      ctx.fillStyle    = "#1B2A38";
      ctx.font         = `900 12px Segoe UI, Arial, sans-serif`;
      ctx.textAlign    = "center";
      ctx.textBaseline = "middle";
      ctx.fillText("PBI", logoX + logoSize / 2, logoY + logoSize / 2);
    }

    const textX = logoX + logoSize + 14;
    ctx.fillStyle    = "#ffffff";
    ctx.font         = `700 15px Segoe UI, Arial, sans-serif`;
    ctx.textAlign    = "left";
    ctx.textBaseline = "alphabetic";
    ctx.fillText("Power BI", textX, bR.y + bR.h / 2 - 2);

    ctx.fillStyle = "rgba(255,255,255,0.55)";
    ctx.font      = `600 12px Segoe UI, Arial, sans-serif`;
    ctx.fillText(t().archPbiLabel, textX, bR.y + bR.h / 2 + 16);

    // Sources count below badge
    const countEl = pbiEl.querySelector("[style*='font-size:11px']");
    if (countEl) {
      ctx.fillStyle    = "#605E5C";
      ctx.font         = `400 11px Segoe UI, Arial, sans-serif`;
      ctx.textAlign    = "center";
      ctx.textBaseline = "alphabetic";
      ctx.fillText(countEl.textContent.trim(), bR.x + bR.w / 2, bR.y + bR.h + 16);
    }
  }

  // ── 7. Footer ─────────────────────────────────────────────────────────────
  const title = els.title.textContent || "BI Flow Mapper";
  ctx.fillStyle    = "rgba(93,107,120,0.7)";
  ctx.font         = `400 11px Segoe UI, Arial, sans-serif`;
  ctx.textAlign    = "right";
  ctx.textBaseline = "alphabetic";
  ctx.fillText(`${title}  ·  ${t().exportTimestamp()}`, totalW - 12, totalH - 10);

  downloadCanvas(canvas, exportFilename());
}

export function buildArchExportSvg(arch, iconDataMap = {}, powerBiIconData = "") {
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

  const CARD_W = 260;
  const CENTER_W = 120;
  const PBI_W = 300;
  const GAP = 24;
  const PAD = 20;
  const HEADER_H = 56;
  const ROW_H = 28;
  const TOP_PAD = 24;

  const cards = arch.map((src) => {
    const queryItems = (src.queries || []).map((q) => ({
      label: q.name || "",
      path: q.connectionPath || "",
    }));
    const hasFallback = !queryItems.length && src.fallbackPath;
    const rows = queryItems.reduce((sum, item) => sum + (item.path ? 2 : 1), 0) || 1;

    return {
      sourceName: src.sourceName,
      iconUrl: src.iconUrl || "",
      iconDataUrl: iconDataMap[src.iconUrl] || "",
      icon: src.icon || (src.sourceName.match(/\b\w/g) || []).slice(0, 2).join("").toUpperCase() || "SRC",
      color: CONNECTOR_COLORS[src.sourceName] || src.color || "#2176ae",
      queries: queryItems,
      fallbackPath: src.fallbackPath,
      hasFallback,
      height: HEADER_H + Math.max(1, rows) * ROW_H,
    };
  });

  const svgHeight = Math.max(420, TOP_PAD * 2 + cards.reduce((sum, card) => sum + card.height, 0) + GAP * (cards.length - 1));
  const svgWidth = PAD * 2 + CARD_W + GAP + CENTER_W + GAP + PBI_W;

  let y = TOP_PAD;
  const cardGroups = cards.map((card) => {
    const group = {
      x: PAD,
      y,
      width: CARD_W,
      height: card.height,
      ...card,
    };
    y += card.height + GAP;
    return group;
  });

  const pbiHeight = 108;
  const pbiX = PAD + CARD_W + GAP + CENTER_W + GAP;
  const pbiY = Math.max(TOP_PAD, (svgHeight - pbiHeight) / 2);
  const pbiLabel = escapeHtml(t().archPbiLabel);
  const pbiTitle = "Power BI";

  const cardsSvg = cardGroups.map((card) => {
    const contentLines = [];
    let currentY = card.y + HEADER_H + 20;

    if (card.queries.length > 0) {
      card.queries.slice(0, 5).forEach((query) => {
        contentLines.push(`
          <circle cx="${card.x + 10}" cy="${currentY - 2}" r="3" fill="${card.color}"/>`);
        contentLines.push(`
          <text x="${card.x + 20}" y="${currentY}" font-family="Segoe UI,Arial,sans-serif" font-size="11" font-weight="700" fill="#17212b">${escapeHtml(truncateString(query.label || t().archNoQueries, 34))}</text>`);
        currentY += 18;
        if (query.path) {
          contentLines.push(`
          <text x="${card.x + 20}" y="${currentY}" font-family="Segoe UI,Arial,sans-serif" font-size="10" fill="#605E5C">${escapeHtml(truncateString(query.path, 48))}</text>`);
          currentY += 18;
        }
      });
    } else if (card.hasFallback) {
      contentLines.push(`
          <circle cx="${card.x + 10}" cy="${currentY - 2}" r="3" fill="${card.color}"/>`);
      contentLines.push(`
          <text x="${card.x + 20}" y="${currentY}" font-family="Segoe UI,Arial,sans-serif" font-size="11" fill="#605E5C">${escapeHtml(truncateString(card.fallbackPath, 48))}</text>`);
    } else {
      contentLines.push(`
          <text x="${card.x + 16}" y="${currentY + 2}" font-family="Segoe UI,Arial,sans-serif" font-size="11" font-style="italic" fill="#888888">${escapeHtml(t().archNoQueries)}</text>`);
    }

    return `
      <g>
        <rect x="${card.x}" y="${card.y}" width="${card.width}" height="${card.height}" rx="18" fill="#ffffff" stroke="#E1DFDD" stroke-width="1.5"/>
        <rect x="${card.x}" y="${card.y}" width="${card.width}" height="${HEADER_H}" rx="18" fill="#ffffff"/>
        <rect x="${card.x + 14}" y="${card.y + 10}" width="36" height="36" rx="10" fill="${card.color}"/>
        ${card.iconDataUrl ? `<image href="${escapeHtml(card.iconDataUrl)}" x="${card.x + 16}" y="${card.y + 12}" width="32" height="32" preserveAspectRatio="xMidYMid slice"/>` : `<text x="${card.x + 32}" y="${card.y + 32}" text-anchor="middle" font-family="Segoe UI,Arial,sans-serif" font-size="13" font-weight="800" fill="#ffffff">${escapeHtml(card.icon)}</text>`}
        <text x="${card.x + 60}" y="${card.y + 30}" font-family="Segoe UI,Arial,sans-serif" font-size="13" font-weight="700" fill="#17212b">${escapeHtml(truncateString(card.sourceName, 24))}</text>
        ${contentLines.join("")}
      </g>`;
  }).join("");

  const pathsSvg = cardGroups.map((card) => {
    const x1 = card.x + card.width;
    const y1 = card.y + card.height / 2;
    const x2 = pbiX;
    const y2 = pbiY + pbiHeight / 2;
    const cp = (x2 - x1) * 0.45;
    return `
      <path d="M ${x1} ${y1} C ${x1 + cp} ${y1}, ${x2 - cp} ${y2}, ${x2} ${y2}"
        fill="none" stroke="${card.color}" stroke-width="2.5" opacity="0.75" marker-end="url(#arch-arrow)"/>`;
  }).join("");

  return {
    width: svgWidth,
    height: svgHeight,
    svg: `
      <svg xmlns="http://www.w3.org/2000/svg" width="${svgWidth}" height="${svgHeight}" viewBox="0 0 ${svgWidth} ${svgHeight}">
        <defs>
          <marker id="arch-arrow" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" fill="#1B2A38" opacity="0.7"/>
          </marker>
        </defs>
        <rect width="100%" height="100%" fill="#F3F2F1" />
        ${cardsSvg}
        ${pathsSvg}
        <g transform="translate(${pbiX}, ${pbiY})">
          <rect x="0" y="0" width="${PBI_W}" height="${pbiHeight}" rx="18" fill="#1B2A38" />
          ${powerBiIconData ? `<image href="${escapeHtml(powerBiIconData)}" x="${(PBI_W - 40) / 2}" y="14" width="40" height="40" preserveAspectRatio="xMidYMid slice"/>` : `<text x="${PBI_W / 2}" y="38" font-family="Segoe UI,Arial,sans-serif" font-size="15" font-weight="700" fill="#ffffff" text-anchor="middle">${escapeHtml(pbiTitle)}</text>`}
          <text x="${PBI_W / 2}" y="68" font-family="Segoe UI,Arial,sans-serif" font-size="13" fill="#ffffff" text-anchor="middle">${escapeHtml(pbiLabel)}</text>
          <text x="${PBI_W / 2}" y="90" font-family="Segoe UI,Arial,sans-serif" font-size="11" fill="#B8C7D7" text-anchor="middle">${escapeHtml(t().archSourcesCount(arch.length))}</text>
        </g>
      </svg>`,
  };
}

export function drawSvgStringToPng(svgString, width, height, filename) {
  const blob = new Blob([svgString], { type: "image/svg+xml;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const img = new Image();
  img.onload = () => {
    const canvas = document.createElement("canvas");
    const DPR = 2;
    canvas.width = width * DPR;
    canvas.height = height * DPR;
    const ctx = canvas.getContext("2d");
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    ctx.drawImage(img, 0, 0, width, height);
    downloadCanvas(canvas, filename);
    URL.revokeObjectURL(url);
  };
  img.onerror = () => URL.revokeObjectURL(url);
  img.src = url;
}

export function exportPagesImage() {
  const pages = state.pages || [];
  if (!pages.length) return;

  const T       = t();
  const DPR     = 2;
  const PAD     = 40;
  const CARD_W  = 600;
  const CARD_H  = 72;
  const CARD_GAP = 12;
  const RADIUS  = 8;
  const ORDINAL_R = 14;          // circle radius
  const ACCENT  = "#F2C94C";    // yellow left border
  const BLUE    = "#2176ae";
  const TITLE_FONT = "700 14px Inter, Segoe UI, Arial, sans-serif";
  const META_FONT  = "400 11px Inter, Segoe UI, Arial, sans-serif";

  const totalH = PAD + pages.length * (CARD_H + CARD_GAP) - CARD_GAP + PAD + 32;
  const totalW = PAD * 2 + CARD_W;

  const canvas = document.createElement("canvas");
  canvas.width  = totalW * DPR;
  canvas.height = totalH * DPR;
  const ctx = canvas.getContext("2d");
  ctx.scale(DPR, DPR);

  // Background
  ctx.fillStyle = "#EEECEA";
  ctx.fillRect(0, 0, totalW, totalH);
  ctx.fillStyle = "#C8C6C4";
  const GRID = 24;
  for (let gx = 0; gx < totalW; gx += GRID)
    for (let gy = 0; gy < totalH; gy += GRID) {
      ctx.beginPath();
      ctx.arc(gx + GRID / 2, gy + GRID / 2, 1.25, 0, Math.PI * 2);
      ctx.fill();
    }

  pages.forEach((page, i) => {
    const x = PAD;
    const y = PAD + i * (CARD_H + CARD_GAP);

    // Card shadow
    ctx.save();
    ctx.shadowColor   = "rgba(23,33,43,0.10)";
    ctx.shadowBlur    = 12;
    ctx.shadowOffsetY = 3;
    roundRect(ctx, x, y, CARD_W, CARD_H, RADIUS);
    ctx.fillStyle = "#ffffff";
    ctx.fill();
    ctx.restore();

    // Yellow left border accent
    roundRect(ctx, x, y, 4, CARD_H, [RADIUS, 0, 0, RADIUS]);
    ctx.fillStyle = ACCENT;
    ctx.fill();

    // Ordinal circle
    const cx = x + 28;
    const cy = y + CARD_H / 2;
    ctx.beginPath();
    ctx.arc(cx, cy, ORDINAL_R, 0, Math.PI * 2);
    ctx.fillStyle = BLUE;
    ctx.fill();
    ctx.fillStyle = "#ffffff";
    ctx.font = "700 11px Inter, Segoe UI, Arial, sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(String(page.ordinal + 1), cx, cy);

    // Page name
    const textX = x + 58;
    ctx.fillStyle = "#201f1e";
    ctx.font = TITLE_FONT;
    ctx.textAlign = "left";
    ctx.textBaseline = "alphabetic";
    ctx.fillText(truncateText(ctx, page.name, CARD_W - 70), textX, y + CARD_H / 2 - 4);

    // Meta badges
    const visLabel    = T.pagesVisualsLabel(page.visualCount);
    const canvasLabel = T.pagesCanvasLabel(page.width, page.height);
    ctx.font = META_FONT;
    ctx.fillStyle = "#605e5c";
    ctx.textBaseline = "alphabetic";

    // vis badge
    const visBadgeW = ctx.measureText(visLabel).width + 14;
    roundRect(ctx, textX, y + CARD_H / 2 + 8, visBadgeW, 18, 4);
    ctx.fillStyle = "#edebe9";
    ctx.fill();
    ctx.fillStyle = "#605e5c";
    ctx.textAlign = "left";
    ctx.textBaseline = "middle";
    ctx.fillText(visLabel, textX + 7, y + CARD_H / 2 + 17);

    // canvas badge
    const cvX = textX + visBadgeW + 6;
    const cvBadgeW = ctx.measureText(canvasLabel).width + 14;
    roundRect(ctx, cvX, y + CARD_H / 2 + 8, cvBadgeW, 18, 4);
    ctx.fillStyle = "#e8f0fb";
    ctx.fill();
    ctx.fillStyle = BLUE;
    ctx.fillText(canvasLabel, cvX + 7, y + CARD_H / 2 + 17);
  });

  // Footer
  const title     = els.title.textContent || "BI Flow Mapper";
  const timestamp = t().exportTimestamp();
  ctx.fillStyle   = "rgba(93,107,120,0.7)";
  ctx.font        = "400 11px Inter, Segoe UI, Arial, sans-serif";
  ctx.textAlign   = "right";
  ctx.textBaseline = "alphabetic";
  ctx.fillText(`${title}  ·  ${timestamp}`, totalW - PAD, totalH - 12);

  downloadCanvas(canvas, exportFilename());
}

export function exportFilename() {
  const title = els.title.textContent || "BI Flow Mapper";
  return (title.replace(/[^a-z0-9]/gi, "_").toLowerCase() || "lineage") + ".png";
}

export function downloadCanvas(canvas, filename) {
  canvas.toBlob((blob) => {
    if (!blob) return;

    // pywebview blocks link.click() downloads — use the Python bridge instead.
    if (window.pywebview && window.pywebview.api && window.pywebview.api.save_file) {
      const reader = new FileReader();
      reader.onloadend = () => {
        // reader.result = "data:image/png;base64,<b64>"  — strip the prefix
        const b64 = reader.result.split(",")[1];
        window.pywebview.api.save_file(b64, filename, "image/png")
          .then((result) => {
            if (result && !result.ok && result.reason !== "cancelled") {
              console.error("[BIFlowMapper] save_file error:", result.reason);
            }
          })
          .catch((err) => console.error("[BIFlowMapper] save_file exception:", err));
      };
      reader.readAsDataURL(blob);
      return;
    }

    // Fallback: normal browser download
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
  }, "image/png");
}

export function fetchImageAsDataUrl(src) {
  return fetch(src)
    .then((response) => {
      if (!response.ok) throw new Error("Failed to fetch image");
      return response.blob();
    })
    .then((blob) => new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onloadend = () => resolve(reader.result);
      reader.onerror = reject;
      reader.readAsDataURL(blob);
    }));
}

export function loadImageElement(src) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = reject;
    img.src = src;
  });
}

export function truncateString(text, maxChars) {
  const value = String(text || "");
  return value.length > maxChars ? value.slice(0, maxChars - 1) + "…" : value;
}

// Helpers do Canvas

export function roundRect(ctx, x, y, w, h, r) {
  const radii = Array.isArray(r) ? r : [r, r, r, r];
  ctx.beginPath();
  ctx.moveTo(x + radii[0], y);
  ctx.lineTo(x + w - radii[1], y);
  ctx.quadraticCurveTo(x + w, y, x + w, y + radii[1]);
  ctx.lineTo(x + w, y + h - radii[2]);
  ctx.quadraticCurveTo(x + w, y + h, x + w - radii[2], y + h);
  ctx.lineTo(x + radii[3], y + h);
  ctx.quadraticCurveTo(x, y + h, x, y + h - radii[3]);
  ctx.lineTo(x, y + radii[0]);
  ctx.quadraticCurveTo(x, y, x + radii[0], y);
  ctx.closePath();
}

export function drawCanvasEdge(ctx, from, to, pad, stroke, sw) {
  const x1 = from.x + from.w + pad;
  const y1 = from.y + from.h / 2 + pad;
  const x2 = to.x + pad;
  const y2 = to.y + to.h / 2 + pad;
  const mid = x1 + Math.max(40, (x2 - x1) / 2);

  ctx.save();
  ctx.strokeStyle = stroke;
  ctx.lineWidth = sw;
  ctx.beginPath();
  ctx.moveTo(x1, y1);
  ctx.bezierCurveTo(mid, y1, mid, y2, x2, y2);
  ctx.stroke();
  drawArrow(ctx, mid, y2, x2, y2, stroke, sw);
  ctx.restore();
}

// Extrai pontos de "M x1 y1 C cpx1 cpy1, cpx2 cpy2, x2 y2" — não usada em
// nenhum ponto ativo do app hoje (herdada de app.js, onde já estava sem
// nenhum call site); mantida por paridade de comportamento na modularização.
function parseBezierPoints(d) {
  const m = d.match(/M\s*([\d.]+)\s+([\d.]+)\s+C\s*([\d.]+)\s+([\d.]+),\s*([\d.]+)\s+([\d.]+),\s*([\d.]+)\s+([\d.]+)/);
  if (!m) return null;
  return {
    x1: +m[1], y1: +m[2],
    cpx1: +m[3], cpy1: +m[4],
    cpx2: +m[5], cpy2: +m[6],
    x2:  +m[7], y2:  +m[8],
  };
}

export function drawArrow(ctx, fromX, fromY, toX, toY, color, sw) {
  const angle  = Math.atan2(toY - fromY, toX - fromX);
  const size   = 8 + sw;
  ctx.save();
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.translate(toX, toY);
  ctx.rotate(angle);
  ctx.moveTo(0, 0);
  ctx.lineTo(-size, -size * 0.45);
  ctx.lineTo(-size,  size * 0.45);
  ctx.closePath();
  ctx.fill();
  ctx.restore();
}

export function truncateText(ctx, text, maxWidth) {
  if (ctx.measureText(text).width <= maxWidth) return text;
  let out = text;
  while (out.length > 1 && ctx.measureText(out + "…").width > maxWidth) {
    out = out.slice(0, -1);
  }
  return out + "…";
}
