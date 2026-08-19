// G8 — checklist de acessibilidade (skill `biflowmapper-a11y-checklist`):
// aria-pressed no card selecionado, papel de lista no container, aria-live
// nos paineis que mudam de conteudo dinamicamente sem foco do usuario.
import { describe, expect, it } from "vitest";
import { loadApp } from "./setup.js";

describe("G8 — aria-pressed no card selecionado", () => {
  it("apos selectNode(id), so o card correspondente tem aria-pressed=true", async () => {
    const app = await loadApp();
    const graphCanvas = document.getElementById("graphCanvas");

    const cardsBefore = Array.from(graphCanvas.querySelectorAll(".node-card"));
    expect(cardsBefore.length).toBeGreaterThan(1); // o demo tem varios nos

    // Nenhum node selecionado ainda: todos os cards comecam com aria-pressed=false
    cardsBefore.forEach((card) => {
      expect(card.getAttribute("aria-pressed")).toBe("false");
    });

    const targetId = cardsBefore[0].dataset.nodeId;
    const otherIds = cardsBefore.slice(1).map((card) => card.dataset.nodeId);
    expect(targetId).toBeTruthy();

    app.selectNode(targetId);

    // renderGraph() reconstroi #graphCanvas do zero a cada chamada de
    // selectNode(); reconsulta os cards depois da re-renderizacao.
    const cardsAfter = Array.from(graphCanvas.querySelectorAll(".node-card"));
    const selectedCard = cardsAfter.find((card) => card.dataset.nodeId === targetId);
    expect(selectedCard.getAttribute("aria-pressed")).toBe("true");

    const pressedCards = cardsAfter.filter((card) => card.getAttribute("aria-pressed") === "true");
    expect(pressedCards).toHaveLength(1);
    expect(pressedCards[0].dataset.nodeId).toBe(targetId);

    // Confere explicitamente que nenhum dos outros ids ficou pressed=true
    otherIds.forEach((id) => {
      const card = cardsAfter.find((c) => c.dataset.nodeId === id);
      expect(card.getAttribute("aria-pressed")).toBe("false");
    });
  });

  it("chamar selectNode(id) de novo no mesmo id desmarca (toggle) e nenhum card fica pressed=true", async () => {
    const app = await loadApp();
    const graphCanvas = document.getElementById("graphCanvas");
    const targetId = graphCanvas.querySelector(".node-card").dataset.nodeId;

    app.selectNode(targetId);
    app.selectNode(targetId); // toggle -> deseleciona

    const cards = Array.from(graphCanvas.querySelectorAll(".node-card"));
    const pressedCards = cards.filter((card) => card.getAttribute("aria-pressed") === "true");
    expect(pressedCards).toHaveLength(0);
  });
});

describe("G8 — papel de lista: role=list no container, sem role=listitem nos cards", () => {
  it("#graphCanvas mantem role=list", async () => {
    await loadApp();
    const graphCanvas = document.getElementById("graphCanvas");
    expect(graphCanvas.getAttribute("role")).toBe("list");
  });

  it("nenhum .node-card renderizado tem role=listitem", async () => {
    await loadApp();
    const cards = document.querySelectorAll("#graphCanvas .node-card");
    expect(cards.length).toBeGreaterThan(0);
    cards.forEach((card) => {
      expect(card.hasAttribute("role")).toBe(false);
    });
  });

  it("continua sem role=listitem depois de re-renderizar via selectNode()", async () => {
    const app = await loadApp();
    const graphCanvas = document.getElementById("graphCanvas");
    const targetId = graphCanvas.querySelector(".node-card").dataset.nodeId;

    app.selectNode(targetId);

    const cards = document.querySelectorAll("#graphCanvas .node-card");
    cards.forEach((card) => {
      expect(card.hasAttribute("role")).toBe(false);
    });
    expect(graphCanvas.getAttribute("role")).toBe("list");
  });
});

describe("seguranca — renderDetails escapa labels de nos afetados", () => {
  it("nome de no malicioso na lista de impactados aparece escapado, nunca cru", async () => {
    // Regressao: achado real do security-reviewer na Fase 2 (XSS
    // armazenado pre-existente) -- ver BACKLOG.md. `labelForId()` retorna
    // node.label cru (vindo do .pbix do usuario); renderDetails() montava
    // `affected.map(labelForId).join(", ")` sem escapeHtml().
    const app = await loadApp();
    const maliciousLabel = '<img src=x onerror="window.__pwned=true">';
    const graph = {
      nodes: [
        { id: "src1", type: "source", label: "Fonte", meta: {} },
        { id: "evil1", type: "query", label: maliciousLabel, meta: {} },
      ],
      edges: [{ from: "src1", to: "evil1", label: "" }],
    };

    app.setGraph(graph, "teste", "");
    app.selectNode("src1");

    const details = document.getElementById("nodeDetails");
    expect(details.innerHTML).not.toContain("<img");
    expect(details.innerHTML).toContain("&lt;img");
    expect(window.__pwned).toBeUndefined();
  });
});

describe("G8 — aria-live nos paineis dinamicos", () => {
  it("#workspaceSubtitle tem aria-live=polite", async () => {
    await loadApp();
    const subtitle = document.getElementById("workspaceSubtitle");
    expect(subtitle.getAttribute("aria-live")).toBe("polite");
  });

  it("#nodeDetails tem aria-live=polite", async () => {
    await loadApp();
    const details = document.getElementById("nodeDetails");
    expect(details.getAttribute("aria-live")).toBe("polite");
  });
});
