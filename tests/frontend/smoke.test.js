import { describe, expect, it } from "vitest";
import { loadApp } from "./setup.js";

// Com módulos ES reais (G12), `document`/`window` são os globals injetados
// pelo ambiente jsdom do Vitest (environment: "jsdom" em vitest.config.js) —
// não precisamos mais de `dom.window.document` como no antigo hack via `vm`.
describe("smoke: loadApp", () => {
  it("carrega o app real e roda init() sem lancar excecao, renderizando o grafo demo", async () => {
    await loadApp();
    expect(document.getElementById("graphCanvas")).toBeTruthy();
    expect(document.querySelectorAll("#graphCanvas .node-card").length).toBeGreaterThan(0);
  });
});
