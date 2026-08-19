// ─── Zoom (G11) ──────────────────────────────────────────────────────────────
// state.scale guarda o fator de zoom atual, aplicado via `transform: scale()`
// em #graphViewport (wrapper que envolve #edgeLayer + #graphCanvas). O pan
// continua sendo o scroll nativo do `.graph-frame` (overflow: auto) — o
// wrapper escalado é filho dele, então scroll e zoom convivem sem conflito.
import { els } from "./dom-refs.js";
import { state } from "./graph-model.js";

export const ZOOM_MIN = 0.3;
export const ZOOM_MAX = 2;
export const ZOOM_STEP = 0.15;

export function clampZoom(scale) {
  return Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, scale));
}

export function applyZoom(scale) {
  state.scale = clampZoom(scale);
  if (els.graphViewport) {
    els.graphViewport.style.transform = `scale(${state.scale})`;
  }
  if (els.zoomLevel) {
    els.zoomLevel.textContent = `${Math.round(state.scale * 100)}%`;
  }
}

export function zoomIn() {
  applyZoom(state.scale + ZOOM_STEP);
}

export function zoomOut() {
  applyZoom(state.scale - ZOOM_STEP);
}

// Escala necessária para caber `graphWidth` dentro de `frameWidth`. Função
// pura, sem DOM, para ser testável isoladamente (ver skill biflowmapper-testing,
// "regra de ouro"). Retorna 1 se alguma medida for inválida/zero (ex.: jsdom,
// que não calcula layout real e reporta clientWidth 0).
export function computeFitScale(graphWidth, frameWidth) {
  if (!graphWidth || !frameWidth) return 1;
  return clampZoom(frameWidth / graphWidth);
}

// hooks.applyZoom é o único ponto de indireção deste módulo: fitGraph() chama
// a função através deste objeto mutável em vez do identificador `applyZoom`
// direto, para que testes possam substituir a implementação (ex.: envolver
// numa spy com vi.fn(hooks.applyZoom)) sem depender de nenhum comportamento
// específico de bundler — mutar uma propriedade de um objeto exportado é
// válido em ESM puro, ao contrário de reatribuir um binding importado
// (import { applyZoom } ...; applyZoom = x lança TypeError).
export const hooks = { applyZoom };

// Botão "ajustar à tela": calcula a escala para caber a largura total do
// grafo (state.graph.width, calculada em layoutGraph() como
// `order.length*250+120`) na largura visível do .graph-frame, aplica via
// applyZoom() e volta a rolagem para o canto superior esquerdo.
export function fitGraph() {
  const frame = els.panelMapa || document.querySelector(".graph-frame");
  if (!frame) return;
  const graphWidth = (state.graph && state.graph.width) || 960;
  hooks.applyZoom(computeFitScale(graphWidth, frame.clientWidth));
  frame.scrollTo({ left: 0, top: 0, behavior: "smooth" });
}

// Wireup dos botões de zoom + Ctrl/Cmd+scroll do mouse — chamado por
// main.js.bindEvents().
export function bindZoomEvents() {
  els.zoomInButton.addEventListener("click", zoomIn);
  els.zoomOutButton.addEventListener("click", zoomOut);
  els.zoomFitButton.addEventListener("click", fitGraph);

  els.panelMapa.addEventListener("wheel", (event) => {
    if (!(event.ctrlKey || event.metaKey)) return; // sem Ctrl/Cmd: scroll normal (pan) intacto
    event.preventDefault();
    if (event.deltaY < 0) zoomIn(); else zoomOut();
  }, { passive: false });
}
