import { beforeEach, describe, expect, it } from "vitest";
import { localMetricsEnabled, readLocalMetrics, recordLocalMetric } from "../../src/local-metrics.js";

beforeEach(() => localStorage.clear());

describe("G29 — métricas locais opt-in", () => {
  it("permanece sem amostras até a ativação explícita", () => {
    recordLocalMetric("render", 12.34, { nodes: [{ id: "sensitive-name" }], edges: [] });

    expect(localMetricsEnabled()).toBe(false);
    expect(readLocalMetrics()).toEqual([]);
  });

  it("guarda apenas duração e contagens no localStorage quando ativada", () => {
    localStorage.setItem("bifm.localMetrics.enabled", "true");
    recordLocalMetric("selection", 12.34567, { nodes: [{ id: "Revenue" }], edges: [{ from: "a", to: "b" }] });

    expect(readLocalMetrics()).toEqual([
      { kind: "selection", durationMs: 12.346, nodeCount: 1, edgeCount: 1 },
    ]);
    expect(localStorage.getItem("bifm.localMetrics.samples")).not.toContain("Revenue");
  });
});
