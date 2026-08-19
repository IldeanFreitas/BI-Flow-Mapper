// G10 — busca textual por nome/DAX/M no grafo.
//
// nodeMatchesSearch(node, term) é função pura (graph-model.js, reaproveita
// normalize(), já usada em slug() e nos testes de locale) — comparada
// isoladamente aqui, sem DOM. handleSearchInput(rawValue) (graph-render.js)
// debounça o re-render em SEARCH_DEBOUNCE_MS (180ms, const de módulo, não
// exportada — o literal 180 é repetido aqui, documentado).
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { loadApp } from "./setup.js";

const TOTAL_DEMO_NODES = 18; // 3 sources + 3 queries + 4 tables + 3 measures + 2 calc columns + 3 visuals

describe("G10 — nodeMatchesSearch() isolada (função pura)", () => {
  it("termo vazio sempre bate, mesmo sem node.meta", async () => {
    const app = await loadApp();
    expect(app.nodeMatchesSearch({ label: "Sales" }, "")).toBe(true);
  });

  it("termo só com espaços em branco também bate tudo (trim -> vazio)", async () => {
    const app = await loadApp();
    expect(app.nodeMatchesSearch({ label: "Sales" }, "   ")).toBe(true);
  });

  it("compara case-insensitive contra o label", async () => {
    const app = await loadApp();
    const node = { label: "Sales Query" };
    expect(app.nodeMatchesSearch(node, "SALES")).toBe(true);
    expect(app.nodeMatchesSearch(node, "sales")).toBe(true);
    expect(app.nodeMatchesSearch(node, "SaLeS QuErY")).toBe(true);
  });

  it("ignora acentuação (normalize NFD) nos dois sentidos", async () => {
    const app = await loadApp();
    // termo sem acento bate label acentuado
    expect(app.nodeMatchesSearch({ label: "Preço Único" }, "preco")).toBe(true);
    expect(app.nodeMatchesSearch({ label: "Preço Único" }, "unico")).toBe(true);
    // termo acentuado bate label sem acento
    expect(app.nodeMatchesSearch({ label: "Preco Unico" }, "único")).toBe(true);
  });

  it("bate por node.meta.expression (M/DAX) mesmo quando o label não contém o termo", async () => {
    const app = await loadApp();
    const node = {
      label: "Sales Query",
      meta: { expression: 'Sql.Database("contoso.database.windows.net", "SalesDB")' }
    };
    expect(app.nodeMatchesSearch(node, "contoso")).toBe(true);
    expect(app.nodeMatchesSearch(node, "SalesDB")).toBe(true);
  });

  it("não bate quando o termo não existe nem no label nem na expressão", async () => {
    const app = await loadApp();
    const node = { label: "Sales Query", meta: { expression: "Sql.Database(...)" } };
    expect(app.nodeMatchesSearch(node, "sharepoint")).toBe(false);
  });

  it("não lança exceção para nó sem meta (meta undefined) — só considera o label", async () => {
    const app = await loadApp();
    const node = { label: "Revenue" };
    expect(() => app.nodeMatchesSearch(node, "revenue")).not.toThrow();
    expect(app.nodeMatchesSearch(node, "revenue")).toBe(true);
    expect(app.nodeMatchesSearch(node, "nao-existe")).toBe(false);
  });

  it("não lança exceção para node.label undefined — ainda considera meta.expression", async () => {
    const app = await loadApp();
    const node = { meta: { expression: "abc" } };
    expect(() => app.nodeMatchesSearch(node, "abc")).not.toThrow();
    expect(app.nodeMatchesSearch(node, "abc")).toBe(true);
  });
});

describe("G10 — digitar em #nodeSearchInput filtra os nós renderizados (debounce 180ms)", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("filtra por label: só cards cujo texto combina com o termo permanecem em #graphCanvas", async () => {
    await loadApp();
    const input = document.getElementById("nodeSearchInput");

    expect(document.querySelectorAll("#graphCanvas .node-card")).toHaveLength(TOTAL_DEMO_NODES);

    input.value = "Revenue";
    input.dispatchEvent(new Event("input", { bubbles: true }));

    // debounce ainda não completou: nada deveria ter mudado
    expect(document.querySelectorAll("#graphCanvas .node-card")).toHaveLength(TOTAL_DEMO_NODES);

    vi.advanceTimersByTime(180);

    const cardsAfter = Array.from(document.querySelectorAll("#graphCanvas .node-card"));
    expect(cardsAfter).toHaveLength(1);
    expect(cardsAfter[0].dataset.nodeId).toBe("measure:revenue");
  });

  it("filtra por expressão M/DAX, não apenas pelo label (termo só existe no meta.expression)", async () => {
    await loadApp();
    const input = document.getElementById("nodeSearchInput");

    // "fiscal" só aparece em demoQuery1Expr ("... with fiscal calendar merge"),
    // associado à Sales Query — não aparece em nenhum label do grafo demo.
    input.value = "fiscal";
    input.dispatchEvent(new Event("input", { bubbles: true }));
    vi.advanceTimersByTime(180);

    const cards = Array.from(document.querySelectorAll("#graphCanvas .node-card"));
    expect(cards).toHaveLength(1);
    expect(cards[0].dataset.nodeId).toBe("query:sales-query");
  });

  it("não re-renderiza a cada tecla digitada — só uma vez, depois do debounce completo desde a última tecla", async () => {
    const app = await loadApp();
    const input = document.getElementById("nodeSearchInput");

    // hooks.renderGraph (graph-render.js) é o ponto de indireção que o
    // callback do debounce chama internamente — substituir a propriedade do
    // objeto intercepta a chamada sem depender de reatribuir um identificador
    // global (que não existe mais com módulos ES).
    const renderGraphSpy = vi.fn(app.searchHooks.renderGraph);
    app.searchHooks.renderGraph = renderGraphSpy;

    // 3 teclas digitadas, cada uma a 100ms da anterior — nunca deixa os
    // 180ms completos passarem entre elas, então o timer é sempre reiniciado.
    ["r", "re", "rev"].forEach((value) => {
      input.value = value;
      input.dispatchEvent(new Event("input", { bubbles: true }));
      vi.advanceTimersByTime(100);
    });

    expect(renderGraphSpy).not.toHaveBeenCalled();

    vi.advanceTimersByTime(180);

    expect(renderGraphSpy).toHaveBeenCalledTimes(1);
    const cards = Array.from(document.querySelectorAll("#graphCanvas .node-card"));
    expect(cards.length).toBeGreaterThan(0);
    cards.forEach((card) => {
      expect(card.textContent.toLowerCase()).toContain("rev");
    });
  });

  it("limpar a busca (string vazia) restaura todos os nós depois do debounce", async () => {
    await loadApp();
    const input = document.getElementById("nodeSearchInput");

    input.value = "revenue";
    input.dispatchEvent(new Event("input", { bubbles: true }));
    vi.advanceTimersByTime(180);
    expect(document.querySelectorAll("#graphCanvas .node-card")).toHaveLength(1);

    input.value = "";
    input.dispatchEvent(new Event("input", { bubbles: true }));
    vi.advanceTimersByTime(180);
    expect(document.querySelectorAll("#graphCanvas .node-card")).toHaveLength(TOTAL_DEMO_NODES);
  });

  it("busca sem nenhum resultado esvazia #graphCanvas e mostra o empty state", async () => {
    await loadApp();
    const input = document.getElementById("nodeSearchInput");
    const emptyState = document.getElementById("emptyState");

    input.value = "termo-que-nao-existe-em-nenhum-node-ou-expressao";
    input.dispatchEvent(new Event("input", { bubbles: true }));
    vi.advanceTimersByTime(180);

    expect(document.querySelectorAll("#graphCanvas .node-card")).toHaveLength(0);
    expect(emptyState.classList.contains("hidden")).toBe(false);
  });
});
