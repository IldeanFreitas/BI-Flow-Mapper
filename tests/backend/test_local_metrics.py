"""G29: métricas locais só existem após opt-in e nunca guardam conteúdo."""
from __future__ import annotations

import requests

import bi_server
from backend import LocalMetrics, lineage_coverage
from _pbix_fixtures import make_empty_pbix_bytes


GRAPH_WITH_CONFIDENCE = {
    "nodes": [
        {"id": "measure:revenue", "type": "measure"},
        {"id": "visual:card", "type": "visual"},
    ],
    "edges": [{"from": "measure:revenue", "to": "visual:card", "linkType": "structural"}],
}


def test_disabled_metrics_keep_no_samples():
    metrics = LocalMetrics(enabled=False)
    metrics.record_analysis("pbix", 12.3, GRAPH_WITH_CONFIDENCE)

    assert metrics.snapshot()["sampleCount"] == 0


def test_enabled_metrics_aggregate_duration_failure_and_lineage_without_labels():
    metrics = LocalMetrics(enabled=True)
    metrics.record_analysis("pbix", 10, GRAPH_WITH_CONFIDENCE)
    metrics.record_analysis("pbix", 30, outcome="failure")
    snapshot = metrics.snapshot()

    assert snapshot["retention"] == "memory-only"
    assert snapshot["summary"] == {"medianMs": 20.0, "p95Ms": 30, "failureCount": 1}
    assert snapshot["samples"][0]["lineageCoverage"]["structuralPercent"] == 100.0
    assert "fileName" not in str(snapshot)
    assert "Revenue" not in str(snapshot)


def test_lineage_coverage_is_unavailable_without_visual_links():
    assert lineage_coverage({"nodes": [], "edges": []}) is None


def test_local_metrics_endpoint_exposes_only_enabled_in_memory_summary(live_server, monkeypatch):
    metrics = LocalMetrics(enabled=True)
    monkeypatch.setattr(bi_server, "LOCAL_METRICS", metrics)
    monkeypatch.setattr(bi_server, "analyze_pbix", lambda _path: GRAPH_WITH_CONFIDENCE)

    analyzed = requests.post(
        f"{live_server}/api/analyze",
        data=make_empty_pbix_bytes(),
        headers={"Origin": live_server},
        timeout=5,
    )
    summary = requests.get(f"{live_server}/api/metrics", timeout=5)

    assert analyzed.status_code == 200
    assert summary.status_code == 200
    assert summary.json()["sampleCount"] == 1
    assert summary.json()["samples"][0]["nodeCount"] == 2
