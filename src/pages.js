// ─── Painel de Páginas (aba "Pages") ────────────────────────────────────────
// Dona de #pagesEmpty/#pagesContent.
import { escapeHtml } from "./dom-utils.js";
import { els } from "./dom-refs.js";
import { state } from "./graph-model.js";
import { t } from "./i18n.js";

export function renderPages() {
  const T     = t();
  const pages = state.pages || [];

  if (!pages.length) {
    els.pagesEmpty.classList.remove("hidden");
    els.pagesContent.classList.add("hidden");
    return;
  }

  els.pagesEmpty.classList.add("hidden");
  els.pagesContent.classList.remove("hidden");

  const ICON_MAP = {
    1: "📊", 2: "📈", 3: "🎯", 4: "💱", 5: "📋", 6: "🔍", 7: "📉", 8: "🗂️",
  };

  els.pagesContent.innerHTML = pages.map((page, i) => {
    const icon        = ICON_MAP[(i % Object.keys(ICON_MAP).length) + 1] || "📄";
    const visLabel    = T.pagesVisualsLabel(page.visualCount);
    const canvasLabel = T.pagesCanvasLabel(page.width, page.height);
    return `
      <div class="page-card">
        <div class="page-card-ordinal">${page.ordinal + 1}</div>
        <div class="page-card-icon" aria-hidden="true">${icon}</div>
        <div class="page-card-body">
          <div class="page-card-name">${escapeHtml(page.name)}</div>
          <div class="page-card-meta">
            <span class="page-badge">${escapeHtml(visLabel)}</span>
            <span class="page-badge page-badge--canvas">${escapeHtml(canvasLabel)}</span>
          </div>
        </div>
      </div>`;
  }).join("");
}
