import { describe, expect, it } from "vitest";
import { buildGraphIndex, downstream, upstream } from "../../src/graph-model.js";

describe("índice de grafo", () => {
  it("reutiliza adjacências para alcançar uma cadeia de mil nós sem alterar o resultado", () => {
    const nodes = Array.from({ length: 1000 }, (_, index) => ({ id: `node-${index}` }));
    const edges = nodes.slice(1).map((node, index) => ({ from: `node-${index}`, to: node.id }));
    const index = buildGraphIndex({ nodes, edges });

    const descendants = downstream("node-0", edges, index);
    const ancestors = upstream("node-999", edges, index);

    expect(descendants.size).toBe(999);
    expect(ancestors.size).toBe(999);
    expect(index.nodesById.get("node-500").id).toBe("node-500");
  });
});
