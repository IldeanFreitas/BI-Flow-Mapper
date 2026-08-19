// G11 — zoom/zoom-to-fit real no grafo.
//
// ZOOM_MIN (0.3) / ZOOM_MAX (2) / ZOOM_STEP (0.15) são exportados por
// src/zoom.js mas não reexportados por src/main.js (a superfície de teste
// exportada é só o que os testes precisam); os valores literais são
// repetidos aqui e comentados sempre que usados, como antes.
//
// computeFitScale/clampZoom/applyZoom/zoomIn/zoomOut/fitGraph são
// reexportados por src/main.js — ver lista no fim do arquivo.
import { describe, expect, it, vi } from "vitest";
import { loadApp } from "./setup.js";

describe("G11 — computeFitScale() isolada (função pura, sem DOM)", () => {
  it("retorna 1 quando graphWidth é 0 ou inválido", async () => {
    const app = await loadApp();
    expect(app.computeFitScale(0, 1000)).toBe(1);
    expect(app.computeFitScale(NaN, 1000)).toBe(1);
    expect(app.computeFitScale(undefined, 1000)).toBe(1);
  });

  it("retorna 1 quando frameWidth é 0 ou inválido (caso real do jsdom, que não calcula layout)", async () => {
    const app = await loadApp();
    expect(app.computeFitScale(1000, 0)).toBe(1);
    expect(app.computeFitScale(1000, NaN)).toBe(1);
    expect(app.computeFitScale(1000, undefined)).toBe(1);
  });

  it("não lança exceção para nenhuma combinação de entradas inválidas", async () => {
    const app = await loadApp();
    expect(() => app.computeFitScale(0, 0)).not.toThrow();
    expect(() => app.computeFitScale(undefined, undefined)).not.toThrow();
    expect(() => app.computeFitScale(-100, -50)).not.toThrow();
  });

  it("grafo maior que o frame: reduz a escala proporcionalmente para caber", async () => {
    const app = await loadApp();
    expect(app.computeFitScale(2000, 1000)).toBe(0.5);
    expect(app.computeFitScale(1370, 685)).toBe(0.5);
  });

  it("grafo do mesmo tamanho do frame: escala 1 (sem alteração)", async () => {
    const app = await loadApp();
    expect(app.computeFitScale(960, 960)).toBe(1);
  });

  it("grafo menor que o frame escala livremente pra cima, enquanto o fator ficar dentro do range [0.3, 2]", async () => {
    const app = await loadApp();
    // frameWidth/graphWidth = 1.5x, dentro do range de zoom permitido
    expect(app.computeFitScale(1000, 1500)).toBe(1.5);
  });

  it("grafo muito menor que o frame: fator bruto (10x) é limitado por ZOOM_MAX (2), não amplia sem limite", async () => {
    const app = await loadApp();
    expect(app.computeFitScale(100, 1000)).toBe(2);
  });
});

describe("G11 — clampZoom() isolada", () => {
  it("limita valores abaixo de ZOOM_MIN (0.3) para 0.3", async () => {
    const app = await loadApp();
    expect(app.clampZoom(0.1)).toBe(0.3);
    expect(app.clampZoom(0)).toBe(0.3);
    expect(app.clampZoom(-5)).toBe(0.3);
  });

  it("limita valores acima de ZOOM_MAX (2) para 2", async () => {
    const app = await loadApp();
    expect(app.clampZoom(5)).toBe(2);
    expect(app.clampZoom(2.01)).toBe(2);
  });

  it("mantém valores já dentro do range intactos", async () => {
    const app = await loadApp();
    expect(app.clampZoom(1)).toBe(1);
    expect(app.clampZoom(0.3)).toBe(0.3);
    expect(app.clampZoom(2)).toBe(2);
  });
});

describe("G11 — applyZoom()/zoomIn()/zoomOut() via clique nos botões reais", () => {
  it("o grafo demo carrega em 100% (setGraph -> applyZoom(1))", async () => {
    await loadApp();
    expect(document.getElementById("graphViewport").style.transform).toBe("scale(1)");
    expect(document.getElementById("zoomLevel").textContent).toBe("100%");
  });

  it("clicar em #zoomInButton aumenta a escala em ZOOM_STEP (0.15) e reflete em #graphViewport + #zoomLevel", async () => {
    await loadApp();
    const viewport = document.getElementById("graphViewport");
    const zoomLevel = document.getElementById("zoomLevel");

    document.getElementById("zoomInButton").dispatchEvent(new Event("click", { bubbles: true }));

    expect(viewport.style.transform).toBe("scale(1.15)");
    expect(zoomLevel.textContent).toBe("115%");
  });

  it("clicar em #zoomOutButton diminui a escala em ZOOM_STEP (0.15)", async () => {
    await loadApp();
    const viewport = document.getElementById("graphViewport");
    const zoomLevel = document.getElementById("zoomLevel");

    document.getElementById("zoomOutButton").dispatchEvent(new Event("click", { bubbles: true }));

    expect(viewport.style.transform).toBe("scale(0.85)");
    expect(zoomLevel.textContent).toBe("85%");
  });

  it("zoom não ultrapassa ZOOM_MAX (2) mesmo clicando + repetidamente", async () => {
    await loadApp();
    const viewport = document.getElementById("graphViewport");
    const zoomLevel = document.getElementById("zoomLevel");
    const zoomInButton = document.getElementById("zoomInButton");

    for (let i = 0; i < 20; i += 1) {
      zoomInButton.dispatchEvent(new Event("click", { bubbles: true }));
    }

    expect(viewport.style.transform).toBe("scale(2)");
    expect(zoomLevel.textContent).toBe("200%");
  });

  it("zoom não ultrapassa ZOOM_MIN (0.3) mesmo clicando - repetidamente", async () => {
    await loadApp();
    const viewport = document.getElementById("graphViewport");
    const zoomLevel = document.getElementById("zoomLevel");
    const zoomOutButton = document.getElementById("zoomOutButton");

    for (let i = 0; i < 20; i += 1) {
      zoomOutButton.dispatchEvent(new Event("click", { bubbles: true }));
    }

    expect(viewport.style.transform).toBe("scale(0.3)");
    expect(zoomLevel.textContent).toBe("30%");
  });

  it("applyZoom(scale) chamado diretamente também respeita o clamp e atualiza o DOM", async () => {
    const app = await loadApp();
    const viewport = document.getElementById("graphViewport");
    const zoomLevel = document.getElementById("zoomLevel");

    app.applyZoom(0.6);
    expect(viewport.style.transform).toBe("scale(0.6)");
    expect(zoomLevel.textContent).toBe("60%");

    app.applyZoom(50); // muito acima do máximo
    expect(viewport.style.transform).toBe("scale(2)");
    expect(zoomLevel.textContent).toBe("200%");
  });
});

describe("G11 — fitGraph() calcula a escala via computeFitScale() e aplica com applyZoom()", () => {
  it("chama applyZoom com exatamente a escala retornada por computeFitScale(graphWidth, panelMapa.clientWidth)", async () => {
    const app = await loadApp();
    const panelMapa = document.getElementById("panelMapa");
    const viewport = document.getElementById("graphViewport");
    const zoomLevel = document.getElementById("zoomLevel");

    // graph.width já está refletido no DOM real via #graphCanvas.style.minWidth
    // (setado em renderGraph() a partir de state.graph.width) — evita
    // hardcodar a fórmula de layoutGraph() no teste.
    const graphWidth = parseInt(document.getElementById("graphCanvas").style.minWidth, 10);
    expect(graphWidth).toBeGreaterThan(0);

    // jsdom não calcula layout real: clientWidth é sempre 0 por padrão.
    // Define explicitamente para simular um viewport visível e menor que o grafo.
    Object.defineProperty(panelMapa, "clientWidth", { value: Math.round(graphWidth / 2), configurable: true });
    // jsdom não implementa Element.prototype.scrollTo (fica undefined, nem
    // sequer um stub) — fitGraph() chama frame.scrollTo({...}) no fim; sem
    // isso o teste quebraria por uma lacuna do ambiente, não por bug do app.
    panelMapa.scrollTo = vi.fn();

    const expectedScale = app.computeFitScale(graphWidth, panelMapa.clientWidth);

    // fitGraph() chama internamente hooks.applyZoom(...) (src/zoom.js) em vez
    // do identificador `applyZoom` direto — substituir a propriedade do
    // hooks intercepta a chamada (mesma técnica de search.test.js).
    const applyZoomSpy = vi.fn(app.zoomHooks.applyZoom);
    app.zoomHooks.applyZoom = applyZoomSpy;

    app.fitGraph();

    expect(applyZoomSpy).toHaveBeenCalledTimes(1);
    expect(applyZoomSpy).toHaveBeenCalledWith(expectedScale);
    expect(viewport.style.transform).toBe(`scale(${expectedScale})`);
    expect(zoomLevel.textContent).toBe(`${Math.round(expectedScale * 100)}%`);
  });

  it("com clientWidth 0 (layout jsdom padrão, sem mock), cai no fallback de computeFitScale (escala 1) sem lançar exceção", async () => {
    const app = await loadApp();
    const panelMapa = document.getElementById("panelMapa");
    const viewport = document.getElementById("graphViewport");
    // ver comentário no teste anterior: jsdom não implementa scrollTo em elementos.
    panelMapa.scrollTo = vi.fn();

    expect(panelMapa.clientWidth).toBe(0);
    expect(() => app.fitGraph()).not.toThrow();
    expect(viewport.style.transform).toBe("scale(1)");
  });
});

describe("G11 — Ctrl/Cmd + scroll do mouse (wheel) em #panelMapa controla o zoom", () => {
  function makeWheelEvent({ deltaY = 0, ctrlKey = false, metaKey = false } = {}) {
    const event = new Event("wheel", { bubbles: true, cancelable: true });
    Object.defineProperty(event, "deltaY", { value: deltaY });
    Object.defineProperty(event, "ctrlKey", { value: ctrlKey });
    Object.defineProperty(event, "metaKey", { value: metaKey });
    return event;
  }

  it("wheel com ctrlKey=true e deltaY negativo chama preventDefault e aumenta o zoom (zoomIn)", async () => {
    await loadApp();
    const panelMapa = document.getElementById("panelMapa");
    const zoomLevel = document.getElementById("zoomLevel");

    const event = makeWheelEvent({ deltaY: -100, ctrlKey: true });
    const preventDefaultSpy = vi.spyOn(event, "preventDefault");

    panelMapa.dispatchEvent(event);

    expect(preventDefaultSpy).toHaveBeenCalled();
    expect(zoomLevel.textContent).toBe("115%");
  });

  it("wheel com metaKey=true (Cmd no mac) e deltaY positivo chama preventDefault e diminui o zoom (zoomOut)", async () => {
    await loadApp();
    const panelMapa = document.getElementById("panelMapa");
    const zoomLevel = document.getElementById("zoomLevel");

    const event = makeWheelEvent({ deltaY: 100, metaKey: true });
    const preventDefaultSpy = vi.spyOn(event, "preventDefault");

    panelMapa.dispatchEvent(event);

    expect(preventDefaultSpy).toHaveBeenCalled();
    expect(zoomLevel.textContent).toBe("85%");
  });

  it("wheel SEM ctrlKey/metaKey não chama preventDefault nem altera o zoom (scroll normal preservado)", async () => {
    await loadApp();
    const panelMapa = document.getElementById("panelMapa");
    const zoomLevel = document.getElementById("zoomLevel");

    const event = makeWheelEvent({ deltaY: -100 });
    const preventDefaultSpy = vi.spyOn(event, "preventDefault");

    panelMapa.dispatchEvent(event);

    expect(preventDefaultSpy).not.toHaveBeenCalled();
    expect(zoomLevel.textContent).toBe("100%");
  });
});
