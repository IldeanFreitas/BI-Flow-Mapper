"""Testes de tmdl_analysis.py (G17 -- caminho paralelo .pbip/TMDL, sem
pbixray/sem .pbix binario).

Funcoes puras -- import direto de tmdl_analysis (ou de backend, que
reexporta tudo), sem servidor. `_tmdl_fixtures.py` traz o texto TMDL
sintetico reutilizado nos varios cenarios.
"""
from __future__ import annotations

import pytest

from backend import TmdlAnalysisError, analyze_tmdl_files, parse_tmdl_model
from tmdl_analysis import _build_tree, _preprocess_lines

from _tmdl_fixtures import (
    REGION_TABLE_TMDL,
    RELATIONSHIPS_TMDL,
    ROLE_TMDL,
    SALES_TABLE_TMDL,
    UNRECOGNIZABLE_TMDL,
    deep_nesting_tmdl,
    full_semantic_model_files,
)


# ---------------------------------------------------------------------------
# parse_tmdl_model(): normalizacao para os shapes de records_from/list_from
# ---------------------------------------------------------------------------
class TestParseTmdlModel:
    def test_tables_and_columns_are_recognized(self):
        parsed = parse_tmdl_model([("Sales.tmdl", SALES_TABLE_TMDL), ("Region.tmdl", REGION_TABLE_TMDL)])

        assert parsed["parse_errors"] == []
        assert set(parsed["tables"]) == {"Sales", "Region"}
        assert {row["Name"] for row in parsed["semantic_tables"]} == {"Sales", "Region"}
        assert all(row["IsHidden"] is False for row in parsed["semantic_tables"])

    def test_calculated_column_expression_is_extracted(self):
        parsed = parse_tmdl_model([("Sales.tmdl", SALES_TABLE_TMDL)])

        calc_columns = {row["Name"]: row for row in parsed["calc_columns"]}
        assert "MarginPct" in calc_columns
        assert calc_columns["MarginPct"]["TableName"] == "Sales"
        assert calc_columns["MarginPct"]["Expression"] == "DIVIDE([Amount] - [Cost], [Amount])"
        # colunas normais (sem "expression = ...") nao viram coluna calculada
        assert "ProductID" not in calc_columns
        assert "Amount" not in calc_columns

    def test_single_line_and_multiline_measures_are_both_extracted(self):
        parsed = parse_tmdl_model([("Sales.tmdl", SALES_TABLE_TMDL)])

        measures = {row["Name"]: row for row in parsed["measures"]}
        assert measures["Total Sales"]["Expression"] == "SUM(Sales[Amount])"
        # medida multi-linha (bloco de crase tripla): DAX preservado com
        # quebras de linha, sem a sintaxe TMDL ao redor (aspas, "measure",
        # crases).
        ytd_expression = measures["Total Sales YTD"]["Expression"]
        assert "CALCULATE(" in ytd_expression
        assert "DATESYTD('Date'[Date])" in ytd_expression
        assert "```" not in ytd_expression

    def test_partition_m_multiline_source_becomes_power_query_record(self):
        parsed = parse_tmdl_model([("Sales.tmdl", SALES_TABLE_TMDL)])

        sales_pq = next(row for row in parsed["power_query"] if row["TableName"] == "Sales")
        assert "Sql.Database(" in sales_pq["Expression"]
        assert "let" in sales_pq["Expression"]
        assert "```" not in sales_pq["Expression"]

    def test_relationships_tmdl_is_parsed_into_from_to_records(self):
        parsed = parse_tmdl_model([
            ("Sales.tmdl", SALES_TABLE_TMDL),
            ("Region.tmdl", REGION_TABLE_TMDL),
            ("relationships.tmdl", RELATIONSHIPS_TMDL),
        ])

        assert len(parsed["relationships"]) == 1
        rel = parsed["relationships"][0]
        assert rel["FromTableName"] == "Sales"
        assert rel["FromColumnName"] == "RegionID"
        assert rel["ToTableName"] == "Region"
        assert rel["ToColumnName"] == "RegionID"
        assert rel["IsActive"] is True

    def test_role_table_permission_becomes_rls_record(self):
        parsed = parse_tmdl_model([("roles.tmdl", ROLE_TMDL)])

        assert len(parsed["rls_records"]) == 1
        rls = parsed["rls_records"][0]
        assert rls["RoleName"] == "Region Manager"
        assert rls["TableName"] == "Sales"
        assert "Pwd=hunter2secret" in rls["FilterExpression"]  # cru aqui -- masking acontece em build_structured_security

    def test_malformed_single_file_is_isolated_not_fatal(self):
        # bytes que nao decodificam nem como utf-8-sig nem utf-8 "puro" caem
        # no fallback errors="replace" de _decode_tmdl -- nao deveria
        # derrubar a analise dos OUTROS arquivos do mesmo upload.
        weird_bytes = b"table Weird\xff\xfe\n    column X\n"
        parsed = parse_tmdl_model([("weird.tmdl", weird_bytes), ("Sales.tmdl", SALES_TABLE_TMDL)])

        assert "Sales" in parsed["tables"]


# ---------------------------------------------------------------------------
# analyze_tmdl_files(): mesmo shape de retorno que analyze_pbix()
# ---------------------------------------------------------------------------
class TestAnalyzeTmdlFilesShape:
    def test_return_shape_matches_analyze_pbix_keys(self):
        graph = analyze_tmdl_files(full_semantic_model_files(), model_name="SalesModel")

        assert set(graph.keys()) == {
            "nodes", "edges", "warnings", "source", "relationships",
            "pages", "unusedObjects", "securityRoles", "diagnostics",
        }
        assert graph["source"] == "tmdl"
        # G17 escopo: sem dados de .Report/(PBIR) -- pages/unusedObjects
        # ficam vazios de proposito (ver docstring do modulo), nunca None.
        assert graph["pages"] == []
        assert graph["unusedObjects"] == []
        assert graph["diagnostics"] == {"totalSizeBytes": 0, "tables": [], "columns": []}

    def test_table_measure_and_calc_column_nodes_are_present(self):
        graph = analyze_tmdl_files(full_semantic_model_files(), model_name="SalesModel")

        nodes_by_type = {}
        for node in graph["nodes"]:
            nodes_by_type.setdefault(node["type"], []).append(node["label"])

        assert set(nodes_by_type.get("model", [])) == {"Sales", "Region"}
        assert "Total Sales" in nodes_by_type.get("measure", [])
        assert "Total Sales YTD" in nodes_by_type.get("measure", [])
        assert "MarginPct" in nodes_by_type.get("calc_column", [])
        # conector SQL Server detectado a partir do M da partition
        assert any(node["type"] == "source" and "SQL Server" in node["label"] for node in graph["nodes"])

    def test_measure_dependency_edge_between_measures_is_detected(self):
        graph = analyze_tmdl_files(full_semantic_model_files(), model_name="SalesModel")

        ids_by_label = {node["label"]: node["id"] for node in graph["nodes"] if node["type"] == "measure"}
        dependency_edges = [
            e for e in graph["edges"]
            if e["from"] == ids_by_label["Total Sales"] and e["to"] == ids_by_label["Total Sales YTD"]
        ]
        assert dependency_edges, "esperava aresta 'Total Sales' -> 'Total Sales YTD' (medida referenciada via [Total Sales] na DAX multi-linha)"
        assert dependency_edges[0]["label"] == "measure dependency"

    def test_structured_relationships_match_relationships_tmdl(self):
        graph = analyze_tmdl_files(full_semantic_model_files(), model_name="SalesModel")

        assert len(graph["relationships"]) == 1
        rel = graph["relationships"][0]
        assert rel["fromTable"] == "Sales"
        assert rel["fromColumn"] == "RegionID"
        assert rel["toTable"] == "Region"
        assert rel["toColumn"] == "RegionID"
        assert rel["crossFilter"] == "Both"
        assert rel["active"] is True

    def test_security_roles_shape_matches_pbix_pipeline(self):
        graph = analyze_tmdl_files(full_semantic_model_files(), model_name="SalesModel")

        assert len(graph["securityRoles"]) == 1
        role = graph["securityRoles"][0]
        assert role["name"] == "Region Manager"
        assert role["objectPermissions"] == []  # sem OLS nesta rodada (ver docstring do modulo)
        assert len(role["rowFilters"]) == 1
        assert role["rowFilters"][0]["table"] == "Sales"

    def test_diagnostics_warnings_report_counts(self):
        graph = analyze_tmdl_files(full_semantic_model_files(), model_name="SalesModel")
        warnings_text = " ".join(graph["warnings"])

        assert "Tabelas TMDL: 2" in warnings_text
        assert "Medidas: 2" in warnings_text
        assert "Colunas calculadas: 1" in warnings_text
        assert "Relacionamentos: 1" in warnings_text
        assert "Papeis de seguranca (RLS): 1" in warnings_text


class TestMaskSecretsParityWithPbixPipeline:
    """G7: `analyze_tmdl_files` reaproveita build_structured_security() de
    pbix_analysis.py SEM MODIFICACAO -- entao a mesma garantia de masking
    (RLS mascarado, ver test_structured_security.py::TestSecretMasking) vale
    aqui automaticamente. `build_query_nodes()`/`build_measure_nodes()`
    tambem sao os MESMOS usados por analyze_pbix() -- e eles NAO mascaram
    `meta.expression` (M/DAX) no grafo JSON ao vivo hoje (mask_secrets so e
    aplicado ao exportar DOCX/HTML e ao dump de debug de `warnings`, ver
    pbix_analysis.py linha ~430 e test_mask_secrets.py). Este teste
    documenta a PARIDADE exata com o caminho pbixray -- nao uma regressao
    nova do G17."""

    def test_rls_filter_expression_secret_is_masked_same_as_pbix_pipeline(self):
        graph = analyze_tmdl_files([("roles.tmdl", ROLE_TMDL), ("Sales.tmdl", SALES_TABLE_TMDL)], model_name="M")

        expression = graph["securityRoles"][0]["rowFilters"][0]["expression"]
        assert "hunter2secret" not in expression
        assert "***MASKED***" in expression
        assert "ConnectionNote" in expression  # resto do texto legivel continua presente

    def test_m_expression_secret_in_live_graph_node_is_not_masked_parity_with_pbix(self):
        # Mesmo comportamento do caminho pbixray: o texto M cru (incluindo
        # qualquer credencial embutida) vai para `meta.expression` do no
        # "query" sem passar por mask_secrets() -- so os exports
        # DOCX/HTML mascaram. Documentado aqui para nao ser confundido com
        # regressao caso alguem note o segredo aparecendo no /api/analyze-tmdl.
        graph = analyze_tmdl_files([("Sales.tmdl", SALES_TABLE_TMDL)], model_name="M")

        query_node = next(node for node in graph["nodes"] if node["type"] == "query" and node["label"] == "Sales")
        assert "hunter2secret" in query_node["meta"]["expression"]


# ---------------------------------------------------------------------------
# TmdlAnalysisError: input vazio/nao reconhecivel
# ---------------------------------------------------------------------------
class TestTmdlAnalysisError:
    def test_empty_files_list_raises(self):
        with pytest.raises(TmdlAnalysisError):
            analyze_tmdl_files([], model_name="Vazio")

    def test_unrecognizable_content_raises(self):
        with pytest.raises(TmdlAnalysisError):
            analyze_tmdl_files([("random.tmdl", UNRECOGNIZABLE_TMDL)], model_name="Lixo")

    def test_error_message_mentions_semantic_model_folder(self):
        with pytest.raises(TmdlAnalysisError, match="SemanticModel"):
            analyze_tmdl_files([("random.tmdl", UNRECOGNIZABLE_TMDL)], model_name="Lixo")


# ---------------------------------------------------------------------------
# Resiliencia a aninhamento adversarial (mesma licao do G14) -- _build_tree()
# e ITERATIVO (pilha explicita), nunca recursivo.
# ---------------------------------------------------------------------------
class TestAdversarialNestingResilience:
    def test_build_tree_survives_thousands_of_increasing_indentation_levels(self):
        text = deep_nesting_tmdl(depth=5000)

        entries = _preprocess_lines(text)
        assert len(entries) == 5000

        tree = _build_tree(entries)  # nao deve levantar RecursionError

        assert len(tree) == 1
        assert tree[0]["text"] == "table Root"

        # desce ate a folha mais profunda ITERATIVAMENTE (o proprio teste
        # tambem nao pode ser recursivo, pela mesma razao) para confirmar
        # que a arvore inteira foi construida corretamente, nao so que a
        # chamada "nao explodiu".
        node = tree[0]
        depth_reached = 0
        while node["children"]:
            node = node["children"][0]
            depth_reached += 1
        assert depth_reached == 4999

    def test_parse_tmdl_model_does_not_crash_on_deep_nesting_and_records_no_parse_error(self):
        # Camada de integracao: prova que a resiliencia e genuina (a arvore
        # foi construida com sucesso), nao apenas "engolida" pelo
        # try/except por-arquivo de parse_tmdl_model -- um RecursionError
        # tambem seria capturado ali (e' subclasse de Exception) e viraria
        # silenciosamente um parse_errors, o que mascararia a diferenca
        # entre "realmente iterativo" e "recursivo, mas com a falha escondida".
        text = deep_nesting_tmdl(depth=5000)
        parsed = parse_tmdl_model([("deep.tmdl", text)])
        assert parsed["parse_errors"] == []

    def test_build_tree_survives_deep_nesting_well_beyond_default_recursion_limit(self):
        import sys

        # Confirmacao adicional: profundidade EXPLICITAMENTE maior que o
        # limite padrao de recursao do Python (garante que, se alguem
        # reintroduzir recursao aqui por engano, este teste falharia com
        # RecursionError em vez de passar por sorte com um numero pequeno).
        depth = sys.getrecursionlimit() + 500
        text = deep_nesting_tmdl(depth=depth)
        tree = _build_tree(_preprocess_lines(text))
        assert len(tree) == 1
