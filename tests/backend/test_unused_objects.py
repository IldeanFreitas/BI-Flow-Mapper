"""Testes unitarios de build_unused_objects() (G15 -- Best Practice Analyzer
basico).

Grafos sinteticos de nodes/edges no MESMO shape que analyze_pbix monta
(id/type/label/meta + edge {id, from, to, label}) -- sem precisar de um
.pbix real, ja que a funcao sob teste so faz BFS reverso a partir dos nos
"visual" usando USAGE_EDGE_LABELS. Import direto de backend, sem servidor.
"""
from __future__ import annotations

from backend import build_unused_objects, edge


def visual(name):
    return {"id": f"visual:{name}", "type": "visual", "label": name, "icon": "VIS", "meta": {}}


def measure(name, table="Sales"):
    return {"id": f"measure:{table}:{name}", "type": "measure", "label": name, "icon": "DAX", "meta": {"table": table}}


def calc_column(name, table="Sales"):
    return {"id": f"calc_column:{table}:{name}", "type": "calc_column", "label": name, "icon": "COL", "meta": {"table": table}}


def unused_ids(nodes, edges):
    return {item["id"] for item in build_unused_objects(nodes, edges)}


class TestDirectUsage:
    def test_measure_used_directly_by_visual_is_not_unused(self):
        v1, m_a = visual("Card1"), measure("TotalSales")
        nodes = [v1, m_a]
        edges = [edge(m_a["id"], v1["id"], "used in visual")]

        result = unused_ids(nodes, edges)
        assert m_a["id"] not in result

    def test_measure_with_no_edges_at_all_is_unused(self):
        m_orphan = measure("NeverUsed")
        nodes = [m_orphan]
        result = build_unused_objects(nodes, edges=[])
        assert len(result) == 1
        assert result[0]["id"] == m_orphan["id"]
        assert result[0]["type"] == "measure"
        assert result[0]["table"] == "Sales"


class TestTransitiveUsage:
    def test_measure_used_only_transitively_via_another_measure_is_not_unused(self):
        # measureB alimenta measureA (via dependencia DAX), e so measureA
        # alimenta o visual diretamente -- measureB deve ser considerada
        # USADA (alcancavel para tras a partir do visual), mesmo sem aresta
        # direta para o visual.
        v1 = visual("Chart1")
        m_a = measure("Margin")
        m_b = measure("Cost")
        nodes = [v1, m_a, m_b]
        edges = [
            edge(m_a["id"], v1["id"], "used in visual"),
            edge(m_b["id"], m_a["id"], "measure dependency"),
        ]

        result = unused_ids(nodes, edges)
        assert m_a["id"] not in result
        assert m_b["id"] not in result

    def test_measure_feeding_only_an_unused_measure_is_still_unused(self):
        # measureB alimenta measureA, mas measureA em si NAO alimenta nenhum
        # visual -- nem A nem B devem ser alcancaveis a partir de um visual,
        # entao ambas aparecem como nao usadas.
        v1 = visual("Chart1")
        m_used = measure("UsedOne")
        m_a = measure("Margin")
        m_b = measure("Cost")
        nodes = [v1, m_used, m_a, m_b]
        edges = [
            edge(m_used["id"], v1["id"], "used in visual"),
            edge(m_b["id"], m_a["id"], "measure dependency"),
        ]

        result = unused_ids(nodes, edges)
        assert m_a["id"] in result
        assert m_b["id"] in result
        assert m_used["id"] not in result


class TestCalcColumns:
    def test_orphan_calc_column_is_unused(self):
        v1 = visual("Table1")
        m_used = measure("Revenue")
        col_orphan = calc_column("UnreferencedFlag")
        nodes = [v1, m_used, col_orphan]
        edges = [edge(m_used["id"], v1["id"], "used in visual")]

        result = unused_ids(nodes, edges)
        assert col_orphan["id"] in result
        assert m_used["id"] not in result

    def test_calc_column_referenced_in_calc_column_expression_is_not_unused(self):
        # "referenced in calc column" e uma das USAGE_EDGE_LABELS: uma
        # medida que alimenta o calculo de uma coluna calculada, que por sua
        # vez alimenta um visual, deve propagar "usado" para tras.
        v1 = visual("Matrix1")
        col_used = calc_column("RunningTotal")
        m_feeder = measure("BaseAmount")
        nodes = [v1, col_used, m_feeder]
        edges = [
            edge(col_used["id"], v1["id"], "used in visual"),
            edge(m_feeder["id"], col_used["id"], "referenced in calc column"),
        ]

        result = unused_ids(nodes, edges)
        assert col_used["id"] not in result
        assert m_feeder["id"] not in result


class TestStructuralEdgesDoNotCountAsUsage:
    def test_defines_measure_edge_alone_does_not_count_as_usage(self):
        # "defines measure" (tabela -> medida) e uma aresta ESTRUTURAL, nao
        # de consumo -- uma medida que so tem essa aresta (nenhum visual a
        # usa) deve continuar aparecendo como nao usada.
        m_a = measure("Orphan")
        nodes = [m_a, {"id": "model:sales", "type": "model", "label": "Sales", "icon": "TBL", "meta": {}}]
        edges = [edge("model:sales", m_a["id"], "defines measure")]

        result = unused_ids(nodes, edges)
        assert m_a["id"] in result


class TestKnownFalsePositiveLimitation:
    def test_measure_referencing_calc_column_via_dax_without_explicit_edge_is_a_known_false_positive(self):
        """Documenta a limitacao conhecida descrita no docstring de
        build_unused_objects: build_measure_dependency_edges so detecta
        referencias medida->medida (procura "[OutraMedida]" na expressao),
        NAO medida->coluna calculada. Uma coluna calculada que so e
        consumida dentro da expressao DAX de uma medida usada (sem que o
        edge-builder atual gere a aresta correspondente) fica INALCANCAVEL
        no BFS reverso e aparece aqui como falso positivo "nao usada".

        Este teste fixa o comportamento ATUAL (nao o desejado) como
        regressao: se o grafo de dependencias for corrigido no futuro para
        detectar essa referencia, este teste deve ser atualizado junto
        (deixaria de ser falso positivo)."""
        v1 = visual("KpiCard")
        m_used = measure("ProfitMargin")
        col_referenced_only_in_dax = calc_column("CostPerUnit")
        # Nenhuma aresta "referenced in calc column" conecta col_referenced_only_in_dax
        # a m_used -- simula o cenario em que a expressao DAX de m_used
        # contem "[CostPerUnit]" mas o edge-builder nao capturou isso porque
        # so procura dependencias medida->medida, nao medida->coluna.
        nodes = [v1, m_used, col_referenced_only_in_dax]
        edges = [edge(m_used["id"], v1["id"], "used in visual")]

        result = unused_ids(nodes, edges)
        assert m_used["id"] not in result
        # Falso positivo documentado: a coluna calculada É de fato usada
        # (logicamente, via DAX), mas aparece como nao usada porque falta a
        # aresta correspondente no grafo hoje.
        assert col_referenced_only_in_dax["id"] in result
