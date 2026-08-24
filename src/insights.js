// ─── Painel de Insights técnicos (G24) ─────────────────────────────────────
// Consome apenas o contrato já emitido por /api/analyze e /api/analyze-tmdl.
// Não recalcula diagnósticos nem infere objetos não usados no navegador: a
// fonte de verdade continua sendo a análise local do backend.
import { escapeHtml } from "./dom-utils.js";
import { els } from "./dom-refs.js";
import { state } from "./graph-model.js";
import { t } from "./i18n.js";

function formatBytes(value) {
  const bytes = Number(value) || 0;
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB", "TB"];
  const unit = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length);
  return `${(bytes / (1024 ** unit)).toFixed(bytes >= 1024 ** 3 ? 2 : 1)} ${units[unit - 1]}`;
}

function unavailableCard(title, message) {
  return `<section class="insight-card insight-card--unavailable">
    <h3>${escapeHtml(title)}</h3>
    <p>${escapeHtml(message)}</p>
  </section>`;
}

function metric(label, value) {
  return `<div class="insight-metric"><dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}</dd></div>`;
}

function renderDiagnosticCard(diagnostics, T) {
  const tables = diagnostics.tables || [];
  if (!tables.length) {
    return unavailableCard(T.insightsStorage, T.insightsStorageEmpty);
  }

  const rows = tables.slice(0, 8).map((table) => `<tr>
    <td>${escapeHtml(table.name)}</td>
    <td>${escapeHtml(String(table.columnCount || 0))}</td>
    <td>${escapeHtml(formatBytes(table.sizeBytes))}</td>
  </tr>`).join("");
  return `<section class="insight-card">
    <h3>${escapeHtml(T.insightsStorage)}</h3>
    <table class="insight-table">
      <thead><tr><th>${escapeHtml(T.insightsTable)}</th><th>${escapeHtml(T.insightsColumns)}</th><th>${escapeHtml(T.insightsSize)}</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
  </section>`;
}

function renderUnusedCard(objects, T) {
  if (!objects.length) {
    return `<section class="insight-card"><h3>${escapeHtml(T.insightsUnused)}</h3><p>${escapeHtml(T.insightsUnusedNone)}</p></section>`;
  }
  const rows = objects.slice(0, 12).map((item) => `<li>
    <strong>${escapeHtml(item.name)}</strong><span>${escapeHtml(item.table || T.insightsNoTable)} · ${escapeHtml(item.type === "calc_column" ? T.insightsCalcColumn : T.insightsMeasure)}</span>
  </li>`).join("");
  return `<section class="insight-card">
    <h3>${escapeHtml(T.insightsUnused)}</h3>
    <p>${escapeHtml(T.insightsUnusedHint)}</p>
    <ul class="insight-list">${rows}</ul>
  </section>`;
}

function renderSecurityCard(roles, T) {
  if (!roles.length) {
    return `<section class="insight-card"><h3>${escapeHtml(T.insightsSecurity)}</h3><p>${escapeHtml(T.insightsSecurityNone)}</p></section>`;
  }
  const rows = roles.map((role) => {
    const filters = role.rowFilters || [];
    const permissions = role.objectPermissions || [];
    const scope = `${filters.length} ${T.insightsRowFilters} · ${permissions.length} ${T.insightsObjectPermissions}`;
    return `<li><strong>${escapeHtml(role.name)}</strong><span>${escapeHtml(scope)}</span></li>`;
  }).join("");
  return `<section class="insight-card">
    <h3>${escapeHtml(T.insightsSecurity)}</h3>
    <ul class="insight-list">${rows}</ul>
  </section>`;
}

export function renderInsights() {
  const T = t();
  const insights = state.insights;
  if (!insights) {
    els.insightsEmpty.classList.remove("hidden");
    els.insightsContent.classList.add("hidden");
    return;
  }

  els.insightsEmpty.classList.add("hidden");
  els.insightsContent.classList.remove("hidden");

  const isTmdl = insights.source === "tmdl";
  const diagnostics = insights.diagnostics || { totalSizeBytes: 0, tables: [], columns: [] };
  const unusedObjects = insights.unusedObjects || [];
  const securityRoles = insights.securityRoles || [];
  const summary = `<dl class="insight-metrics">
    ${metric(T.insightsModelSize, isTmdl ? T.insightsUnavailable : formatBytes(diagnostics.totalSizeBytes))}
    ${metric(T.insightsProfiledTables, isTmdl ? T.insightsUnavailable : String((diagnostics.tables || []).length))}
    ${metric(T.insightsSecurityRoles, String(securityRoles.length))}
    ${metric(T.insightsUnusedCount, isTmdl ? T.insightsUnavailable : String(unusedObjects.length))}
  </dl>`;

  const storage = isTmdl
    ? unavailableCard(T.insightsStorage, T.insightsStorageUnavailable)
    : renderDiagnosticCard(diagnostics, T);
  const unused = isTmdl
    ? unavailableCard(T.insightsUnused, T.insightsUnusedUnavailable)
    : renderUnusedCard(unusedObjects, T);

  els.insightsContent.innerHTML = `${summary}<div class="insight-grid">${storage}${unused}${renderSecurityCard(securityRoles, T)}</div>`;
}
