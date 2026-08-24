// G17 — seleção de pasta .pbip/.SemanticModel via <input webkitdirectory> em
// #pbipFolderInput: filtra os arquivos .tmdl, envia pro backend
// (/api/analyze-tmdl) e reaproveita o mesmo caminho de renderização
// (applyBackendGraph) usado pelo fluxo .pbix.
// G23 — #loadingSpinner (setLoading()) cobre, em try/finally, todo o tempo
// entre o início do fetch e a resposta, tanto no fluxo .pbix quanto no fluxo
// .pbip/TMDL (sucesso e erro).
import { afterEach, describe, expect, it, vi } from "vitest";
import { loadApp } from "./setup.js";
import { filterTmdlFiles, buildTmdlFormData } from "../../src/upload.js";

// Helper: cria um File real (jsdom/Node), com webkitRelativePath sobrescrito
// via defineProperty — não dá pra passar webkitRelativePath no construtor de
// File (é somente-leitura em navegadores reais, setado pelo próprio picker de
// pasta), mas defineProperty funciona igual à técnica já usada em
// drag-and-drop.test.js para simular propriedades de File.
function makeTmdlFile(relativePath) {
  const name = relativePath.split("/").pop();
  const file = new File(["conteudo tmdl"], name, { type: "text/plain" });
  Object.defineProperty(file, "webkitRelativePath", { value: relativePath, configurable: true });
  return file;
}

function makeSyntheticGraph() {
  return {
    nodes: [
      { id: "model:sales", type: "model", label: "Sales", meta: {} },
      { id: "measure:revenue", type: "measure", label: "Revenue", meta: {} },
    ],
    edges: [{ from: "model:sales", to: "measure:revenue", label: "" }],
    relationships: [],
    pages: [],
    warnings: [],
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("G17 — filterTmdlFiles() (pura)", () => {
  it("mantém só arquivos .tmdl, ignorando outras extensões (.json, .pbip, .Report)", () => {
    const fileList = [
      { name: "Sales.tmdl", webkitRelativePath: "Model.pbip/Model.SemanticModel/definition/tables/Sales.tmdl" },
      { name: "model.tmdl", webkitRelativePath: "Model.pbip/Model.SemanticModel/definition/model.tmdl" },
      { name: "report.json", webkitRelativePath: "Model.pbip/Model.Report/report.json" },
      { name: "Model.pbip", webkitRelativePath: "Model.pbip" },
    ];

    const result = filterTmdlFiles(fileList);

    expect(result).toHaveLength(2);
    expect(result.map((f) => f.name)).toEqual(["Sales.tmdl", "model.tmdl"]);
  });

  it("é case-insensitive na extensão (.TMDL também passa)", () => {
    const fileList = [
      { name: "Sales.TMDL", webkitRelativePath: "Model.pbip/Model.SemanticModel/definition/tables/Sales.TMDL" },
      { name: "readme.TXT", webkitRelativePath: "readme.TXT" },
    ];

    const result = filterTmdlFiles(fileList);

    expect(result).toHaveLength(1);
    expect(result[0].name).toBe("Sales.TMDL");
  });

  it("usa webkitRelativePath (não name) para decidir a extensão quando ambos existem", () => {
    // name engana (.txt), mas webkitRelativePath é quem manda de verdade
    // (mesmo campo usado depois por buildTmdlFormData/derivePbipTitle).
    const fileList = [
      { name: "Sales.txt", webkitRelativePath: "Model.pbip/Model.SemanticModel/definition/tables/Sales.tmdl" },
      { name: "Sales.tmdl", webkitRelativePath: "Model.pbip/Model.SemanticModel/definition/tables/Sales.txt" },
    ];

    const result = filterTmdlFiles(fileList);

    expect(result).toHaveLength(1);
    expect(result[0].name).toBe("Sales.txt");
  });

  it("cai para name quando webkitRelativePath está ausente", () => {
    const fileList = [{ name: "Sales.tmdl" }, { name: "notes.md" }];

    const result = filterTmdlFiles(fileList);

    expect(result).toHaveLength(1);
    expect(result[0].name).toBe("Sales.tmdl");
  });

  it("devolve array vazio para entrada vazia/undefined, sem lançar", () => {
    expect(filterTmdlFiles([])).toEqual([]);
    expect(filterTmdlFiles(undefined)).toEqual([]);
  });
});

describe("G17 — buildTmdlFormData() (pura)", () => {
  it("monta um FormData com uma entrada tmdl_files por arquivo, usando webkitRelativePath como filename", () => {
    const files = [
      makeTmdlFile("Model.pbip/Model.SemanticModel/definition/tables/Sales.tmdl"),
      makeTmdlFile("Model.pbip/Model.SemanticModel/definition/tables/Date.tmdl"),
    ];

    const formData = buildTmdlFormData(files);
    const entries = formData.getAll("tmdl_files");

    expect(entries).toHaveLength(2);
    expect(entries[0].name).toBe("Model.pbip/Model.SemanticModel/definition/tables/Sales.tmdl");
    expect(entries[1].name).toBe("Model.pbip/Model.SemanticModel/definition/tables/Date.tmdl");
  });

  it("cai para file.name como filename quando webkitRelativePath está ausente", () => {
    const file = new File(["x"], "solto.tmdl");
    const formData = buildTmdlFormData([file]);
    const entries = formData.getAll("tmdl_files");

    expect(entries).toHaveLength(1);
    expect(entries[0].name).toBe("solto.tmdl");
  });

  it("array vazio produz FormData sem nenhuma entrada tmdl_files", () => {
    const formData = buildTmdlFormData([]);
    expect(formData.getAll("tmdl_files")).toHaveLength(0);
  });
});

describe("G17 — loadPbipFolder(): zero arquivos .tmdl encontrados", () => {
  it("não chama fetch e mostra t().tmdlNoFilesFound no subtítulo", async () => {
    const app = await loadApp();
    const fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);

    const fileList = [
      { name: "report.json", webkitRelativePath: "Model.pbip/Model.Report/report.json" },
      { name: "Model.pbip", webkitRelativePath: "Model.pbip" },
    ];

    await app.loadPbipFolder(fileList);

    expect(fetchSpy).not.toHaveBeenCalled();
    const subtitle = document.getElementById("workspaceSubtitle");
    expect(subtitle.textContent).toBe(app.t().tmdlNoFilesFound);
  });
});

describe("G17 — loadPbipFolder(): sucesso do backend renderiza o grafo", () => {
  it("chama /api/analyze-tmdl e renderiza o grafo retornado (applyBackendGraph)", async () => {
    const app = await loadApp();
    const graph = makeSyntheticGraph();

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(graph),
      })
    );

    const files = [makeTmdlFile("MeuModelo.pbip/MeuModelo.SemanticModel/definition/tables/Sales.tmdl")];

    await app.loadPbipFolder(files);

    expect(fetch).toHaveBeenCalledTimes(1);
    expect(fetch).toHaveBeenCalledWith("/api/analyze-tmdl", expect.objectContaining({ method: "POST" }));

    // mesmo caminho de renderização que o fluxo .pbix: node cards no DOM,
    // título derivado do primeiro segmento do path relativo.
    const graphCanvas = document.getElementById("graphCanvas");
    expect(graphCanvas.querySelectorAll(".node-card").length).toBe(2);
    expect(document.getElementById("workspaceTitle").textContent).toBe("MeuModelo.pbip");

    // rememberPbix() é chamado por applyBackendGraph() nos dois fluxos —
    // habilita o botão de voltar ao último grafo carregado.
    expect(document.getElementById("pbixButton").disabled).toBe(false);
  });
});

describe("G17 — #pbipFolderInput (change) aciona hooks.loadPbipFolder", () => {
  it("dispara hooks.loadPbipFolder(fileList) com o FileList selecionado", async () => {
    const app = await loadApp();
    const input = document.getElementById("pbipFolderInput");

    const loadPbipFolderSpy = vi.fn().mockResolvedValue(undefined);
    app.uploadHooks.loadPbipFolder = loadPbipFolderSpy;

    const files = [makeTmdlFile("Model.pbip/Model.SemanticModel/definition/tables/Sales.tmdl")];
    Object.defineProperty(input, "files", { value: files, configurable: true });

    input.dispatchEvent(new Event("change", { bubbles: true }));

    expect(loadPbipFolderSpy).toHaveBeenCalledTimes(1);
    expect(loadPbipFolderSpy).toHaveBeenCalledWith(files);
  });

  it("não dispara hooks.loadPbipFolder quando o FileList está vazio", async () => {
    const app = await loadApp();
    const input = document.getElementById("pbipFolderInput");

    const loadPbipFolderSpy = vi.fn().mockResolvedValue(undefined);
    app.uploadHooks.loadPbipFolder = loadPbipFolderSpy;

    Object.defineProperty(input, "files", { value: [], configurable: true });
    input.dispatchEvent(new Event("change", { bubbles: true }));

    expect(loadPbipFolderSpy).not.toHaveBeenCalled();
  });
});

describe("G17 — regressão: loadPbipFolder() bem-sucedido não deixa reexportar documentos de um .pbix anterior", () => {
  it("zera state.lastPbixFile e mantém os exports de documento desabilitados após sucesso", async () => {
    const app = await loadApp();

    // simula um .pbix já carregado antes (fluxo normal deixaria isso habilitado)
    app.state.lastPbixFile = new File(["x"], "anterior.pbix");
    document.getElementById("exportDocxButton").disabled = false;
    document.getElementById("exportHtmlButton").disabled = false;

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(makeSyntheticGraph()),
      })
    );

    const files = [makeTmdlFile("Model.pbip/Model.SemanticModel/definition/tables/Sales.tmdl")];
    await app.loadPbipFolder(files);

    expect(app.state.lastPbixFile).toBeNull();
    expect(document.getElementById("exportDocxButton").disabled).toBe(true);
    expect(document.getElementById("exportHtmlButton").disabled).toBe(true);
  });
});

describe("G23 — setLoading()/#loadingSpinner", () => {
  it("setLoading(true) remove hidden, setLoading(false) devolve hidden", async () => {
    const app = await loadApp();
    const spinner = document.getElementById("loadingSpinner");
    expect(spinner.hidden).toBe(true); // estado inicial (index.html)

    app.setLoading(true);
    expect(spinner.hidden).toBe(false);

    app.setLoading(false);
    expect(spinner.hidden).toBe(true);
  });

  it("loadPbipFolder(): spinner liga no início e desliga no finally após SUCESSO", async () => {
    const app = await loadApp();
    const spinner = document.getElementById("loadingSpinner");

    let spinnerDuringFetch = null;
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(() => {
        spinnerDuringFetch = spinner.hidden;
        return Promise.resolve({ ok: true, json: () => Promise.resolve(makeSyntheticGraph()) });
      })
    );

    const files = [makeTmdlFile("Model.pbip/Model.SemanticModel/definition/tables/Sales.tmdl")];
    await app.loadPbipFolder(files);

    expect(spinnerDuringFetch).toBe(false); // ligado durante o fetch
    expect(spinner.hidden).toBe(true); // desligado no finally
  });

  it("loadPbipFolder(): spinner desliga no finally mesmo quando o fetch REJEITA", async () => {
    const app = await loadApp();
    const spinner = document.getElementById("loadingSpinner");

    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network down")));

    const files = [makeTmdlFile("Model.pbip/Model.SemanticModel/definition/tables/Sales.tmdl")];
    await app.loadPbipFolder(files);

    expect(spinner.hidden).toBe(true);
    const subtitle = document.getElementById("workspaceSubtitle");
    expect(subtitle.textContent).toBe(app.t().loadingErrorTmdl);
  });

  it("loadPbix(): spinner desliga no finally após SUCESSO do backend", async () => {
    const app = await loadApp();
    const spinner = document.getElementById("loadingSpinner");

    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve(makeSyntheticGraph()) })
    );

    const file = new File(["conteudo"], "relatorio.pbix");
    await app.loadPbix(file);

    expect(spinner.hidden).toBe(true);
  });

  it("loadPbix(): spinner desliga no finally mesmo quando o fetch do backend REJEITA (cai no fallback do navegador)", async () => {
    const app = await loadApp();
    const spinner = document.getElementById("loadingSpinner");

    // analyzeWithBackend() engole o erro de fetch internamente e retorna
    // null; loadPbix() cai no parser de zip do navegador, que também falha
    // (o File não é um zip real) — o finally precisa desligar o spinner de
    // qualquer forma, nos dois estágios encadeados.
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network down")));

    const file = new File(["nao e um zip valido"], "relatorio.pbix");
    await app.loadPbix(file);

    expect(spinner.hidden).toBe(true);
    const subtitle = document.getElementById("workspaceSubtitle");
    expect(subtitle.textContent).toBe(app.t().loadingError);
  });
});

describe("G17 — applyI18n() traduz #pbipFolderLabel entre en-US/pt-BR", () => {
  it("pt-BR mostra 'ou selecione uma pasta .pbip'", async () => {
    const app = await loadApp();
    app.setLocale("pt-BR");
    expect(document.getElementById("pbipFolderLabel").textContent).toBe("ou selecione uma pasta .pbip");
  });

  it("en-US mostra 'or select a .pbip folder'", async () => {
    const app = await loadApp();
    app.setLocale("pt-BR");
    app.setLocale("en-US");
    expect(document.getElementById("pbipFolderLabel").textContent).toBe("or select a .pbip folder");
  });
});
