import { describe, expect, it } from "vitest";
import { loadApp } from "./setup.js";

function confidenceGraph() {
  return {
    nodes: [
      { id: "measure:revenue", type: "measure", label: "Revenue", meta: {} },
      { id: "visual:card", type: "visual", label: "Revenue card", meta: {} },
      { id: "visual:custom", type: "visual", label: "Custom visual", meta: {} },
    ],
    edges: [
      { from: "measure:revenue", to: "visual:card", label: "used in visual", linkType: "structural" },
      { from: "measure:revenue", to: "visual:custom", label: "used in visual", linkType: "heuristic" },
    ],
  };
}

describe("G27 — confiança da linhagem visual", () => {
  it("distingue no mapa a aresta estrutural da heurística", async () => {
    const app = await loadApp();
    app.setGraph(confidenceGraph(), "Confidence", "");

    const structural = document.querySelector('path[data-link-type="structural"]');
    const heuristic = document.querySelector('path[data-link-type="heuristic"]');
    expect(structural.getAttribute("stroke")).toBe("#107C10");
    expect(structural.hasAttribute("stroke-dasharray")).toBe(false);
    expect(heuristic.getAttribute("stroke")).toBe("#D83B01");
    expect(heuristic.getAttribute("stroke-dasharray")).toBe("7 5");
    expect(document.getElementById("lineageConfidenceLegend").textContent).toContain("structural");
  });

  it("explica a confiança das arestas conectadas no painel de detalhes", async () => {
    const app = await loadApp();
    app.setGraph(confidenceGraph(), "Confidence", "");
    app.selectNode("measure:revenue");

    const details = document.getElementById("nodeDetails");
    expect(details.textContent).toContain("Structural evidence");
    expect(details.textContent).toContain("Heuristic inference");
    expect(details.textContent).toContain("Revenue card");
    expect(details.textContent).toContain("Custom visual");
  });

  it("traduz a legenda de confiança", async () => {
    const app = await loadApp();
    app.setLocale("pt-BR");
    expect(document.getElementById("lineageConfidenceLegend").textContent).toContain("heurística");
  });
});
