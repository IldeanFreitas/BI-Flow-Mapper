// G29 — Métricas locais, desativadas por padrão e sem chamadas de rede.
// Ative conscientemente no DevTools com:
// localStorage.setItem("bifm.localMetrics.enabled", "true")
const ENABLED_KEY = "bifm.localMetrics.enabled";
const SAMPLES_KEY = "bifm.localMetrics.samples";
const MAX_SAMPLES = 200;

export function localMetricsEnabled() {
  try {
    return localStorage.getItem(ENABLED_KEY) === "true";
  } catch {
    return false;
  }
}

export function recordLocalMetric(kind, durationMs, graph = {}) {
  if (!localMetricsEnabled()) return;
  const sample = {
    kind,
    durationMs: Number(durationMs.toFixed(3)),
    nodeCount: (graph.nodes || []).length,
    edgeCount: (graph.edges || []).length,
  };
  try {
    const samples = JSON.parse(localStorage.getItem(SAMPLES_KEY) || "[]");
    samples.push(sample);
    localStorage.setItem(SAMPLES_KEY, JSON.stringify(samples.slice(-MAX_SAMPLES)));
  } catch {
    // Instrumentação nunca pode impedir o uso do mapa (quota/storage privado).
  }
}

export function readLocalMetrics() {
  try {
    return JSON.parse(localStorage.getItem(SAMPLES_KEY) || "[]");
  } catch {
    return [];
  }
}
