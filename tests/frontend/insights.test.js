import { afterEach, describe, expect, it, vi } from "vitest";
import { loadApp } from "./setup.js";

function analysisGraph(overrides = {}) {
  return {
    source: "pbixray",
    nodes: [{ id: "model:sales", type: "model", label: "Sales", meta: {} }],
    edges: [],
    relationships: [],
    pages: [],
    warnings: [],
    diagnostics: {
      totalSizeBytes: 3 * 1024 * 1024,
      tables: [{ name: "Sales", columnCount: 4, sizeBytes: 2 * 1024 * 1024 }],
      columns: [],
    },
    unusedObjects: [{ id: "measure:old", name: "Old measure", type: "measure", table: "Sales" }],
    securityRoles: [{ name: "Regional", rowFilters: [{ table: "Sales" }], objectPermissions: [] }],
    ...overrides,
  };
}

function makeTmdlFile() {
  const file = new File(["table 'Sales'"], "Sales.tmdl", { type: "text/plain" });
  Object.defineProperty(file, "webkitRelativePath", { value: "Model.pbip/Model.SemanticModel/definition/tables/Sales.tmdl" });
  return file;
}

afterEach(() => vi.unstubAllGlobals());

describe("G24 — Insights", () => {
  it("exibe diagnóstico, objetos não usados e RLS/OLS para PBIX", async () => {
    const app = await loadApp();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve(analysisGraph()) }));

    await app.loadPbix(new File(["pbix"], "sales.pbix"));
    document.getElementById("tabInsights").click();

    const content = document.getElementById("insightsContent");
    expect(content.classList.contains("hidden")).toBe(false);
    expect(content.textContent).toContain("3.0 MB");
    expect(content.textContent).toContain("Sales");
    expect(content.textContent).toContain("Old measure");
    expect(content.textContent).toContain("Regional");
  });

  it("trata diagnósticos e objetos não usados como indisponíveis para TMDL", async () => {
    const app = await loadApp();
    const tmdlGraph = analysisGraph({
      source: "tmdl",
      diagnostics: { totalSizeBytes: 0, tables: [], columns: [] },
      unusedObjects: [],
      securityRoles: [{ name: "ReadOnly", rowFilters: [], objectPermissions: [{ table: "Sales" }] }],
    });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve(tmdlGraph) }));

    await app.loadPbipFolder([makeTmdlFile()]);
    document.getElementById("tabInsights").click();

    const content = document.getElementById("insightsContent");
    expect(content.textContent).toContain("Unavailable");
    expect(content.textContent).toContain("ReadOnly");
    expect(content.textContent).not.toContain("No unused measures or calculated columns were found.");
  });

  it("retraduz a aba ativa e preserva o estado de indisponibilidade", async () => {
    const app = await loadApp();
    app.state.insights = { source: "tmdl", diagnostics: null, unusedObjects: [], securityRoles: [] };
    document.getElementById("tabInsights").click();
    app.setLocale("pt-BR");

    expect(document.getElementById("tabInsights").textContent).toBe("Insights");
    expect(document.getElementById("insightsContent").textContent).toContain("Indisponível");
  });
});
