"""Métricas locais e opt-in para diagnosticar o BI Flow Mapper.

Nenhuma amostra é enviada, gravada em disco ou contém nome de arquivo, expressão
ou dados do modelo. A retenção é apenas em memória, limitada e reiniciada junto
com o processo. Para habilitar, inicie com `BIFM_LOCAL_METRICS=1`.
"""
from __future__ import annotations

import os
import threading
from statistics import median


MAX_SAMPLES = 200


def is_enabled_from_environment() -> bool:
    return os.environ.get("BIFM_LOCAL_METRICS", "").strip().lower() in {"1", "true", "yes", "on"}


def lineage_coverage(graph: dict) -> dict | None:
    """Resume a confiança das ligações que chegam a visuais, sem conteúdo."""
    nodes = {node.get("id"): node for node in graph.get("nodes", [])}
    visual_edges = [
        edge for edge in graph.get("edges", [])
        if nodes.get(edge.get("to"), {}).get("type") == "visual"
    ]
    if not visual_edges:
        return None
    structural = sum(edge.get("linkType") == "structural" for edge in visual_edges)
    heuristic = sum(edge.get("linkType") == "heuristic" for edge in visual_edges)
    return {
        "visualLinkCount": len(visual_edges),
        "structuralLinkCount": structural,
        "heuristicLinkCount": heuristic,
        "structuralPercent": round(structural * 100 / len(visual_edges), 2),
    }


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = round((len(ordered) - 1) * fraction)
    return round(ordered[index], 3)


class LocalMetrics:
    """Coletor thread-safe, deliberadamente pequeno e sem persistência."""

    def __init__(self, enabled: bool = False, max_samples: int = MAX_SAMPLES):
        self.enabled = enabled
        self.max_samples = max_samples
        self._samples: list[dict] = []
        self._lock = threading.Lock()

    def record_analysis(self, kind: str, duration_ms: float, graph: dict | None = None, outcome: str = "success") -> None:
        if not self.enabled:
            return
        graph = graph or {}
        sample = {
            "kind": kind,
            "outcome": outcome,
            "durationMs": round(duration_ms, 3),
            "nodeCount": len(graph.get("nodes", [])),
            "edgeCount": len(graph.get("edges", [])),
            "lineageCoverage": lineage_coverage(graph) if outcome == "success" else None,
        }
        with self._lock:
            self._samples.append(sample)
            del self._samples[:-self.max_samples]

    def snapshot(self) -> dict:
        with self._lock:
            samples = list(self._samples)
        durations = [sample["durationMs"] for sample in samples]
        return {
            "enabled": self.enabled,
            "retention": "memory-only",
            "sampleCount": len(samples),
            "summary": {
                "medianMs": round(median(durations), 3) if durations else None,
                "p95Ms": percentile(durations, 0.95),
                "failureCount": sum(sample["outcome"] != "success" for sample in samples),
            },
            "samples": samples,
        }


LOCAL_METRICS = LocalMetrics(enabled=is_enabled_from_environment())
