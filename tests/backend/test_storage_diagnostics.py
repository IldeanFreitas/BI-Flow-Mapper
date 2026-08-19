"""Testes de G18 -- diagnostico tecnico de armazenamento (tamanho/cardinalidade
por tabela/coluna, agregado a partir de `model.statistics`/`model.size` do
pbixray).

`build_structured_diagnostics`/`scalar_from` sao funcoes puras -- import
direto de backend, com `stats_records` sinteticos no mesmo shape de linha que
pbixray devolve (TableName/ColumnName/Cardinality/Dictionary/HashIndex/
DataSize). O ultimo teste da classe `TestEndToEndAnalyzePbix` exercita o
pipeline completo via /api/analyze com o servidor real (live_server) e o
PBIXRay fake (_pbix_fixtures), incluindo o atributo escalar `size`.
"""
from __future__ import annotations

import requests

import backend
from backend import build_structured_diagnostics, scalar_from

from _pbix_fixtures import make_empty_pbix_bytes, make_fake_pbixray_class, patch_pbixray


# ---------------------------------------------------------------------------
# (1) agregacao por tabela, ordenacao desc, totalSizeBytes == model_size
# ---------------------------------------------------------------------------
class TestBuildStructuredDiagnosticsAggregation:
    def test_totals_and_ordering_across_tables_and_columns(self):
        stats_records = [
            {"TableName": "Sales", "ColumnName": "Amount", "Cardinality": 500, "Dictionary": 1000, "HashIndex": 200, "DataSize": 300},
            {"TableName": "Sales", "ColumnName": "OrderDate", "Cardinality": 365, "Dictionary": 100, "HashIndex": 50, "DataSize": 50},
            {"TableName": "Region", "ColumnName": "Name", "Cardinality": 10, "Dictionary": 40, "HashIndex": 10, "DataSize": 10},
        ]
        diagnostics = build_structured_diagnostics(stats_records, model_size=999999)

        # totalSizeBytes vem de model_size (passado explicitamente), NAO da
        # soma dos registros de stats -- os dois numeros sao independentes
        # por design (model.size inclui overhead que nao aparece por coluna).
        assert diagnostics["totalSizeBytes"] == 999999

        assert diagnostics["tables"] == [
            {"name": "Sales", "columnCount": 2, "sizeBytes": 1700},
            {"name": "Region", "columnCount": 1, "sizeBytes": 60},
        ]

        assert diagnostics["columns"] == [
            {"table": "Sales", "name": "Amount", "cardinality": 500, "sizeBytes": 1500, "dictionarySizeBytes": 1000, "dataSizeBytes": 300},
            {"table": "Sales", "name": "OrderDate", "cardinality": 365, "sizeBytes": 200, "dictionarySizeBytes": 100, "dataSizeBytes": 50},
            {"table": "Region", "name": "Name", "cardinality": 10, "sizeBytes": 60, "dictionarySizeBytes": 40, "dataSizeBytes": 10},
        ]

    def test_tables_list_is_sorted_desc_even_when_input_order_is_ascending(self):
        stats_records = [
            {"TableName": "Small", "ColumnName": "A", "Cardinality": 1, "Dictionary": 5, "HashIndex": 0, "DataSize": 0},
            {"TableName": "Big", "ColumnName": "B", "Cardinality": 1, "Dictionary": 5000, "HashIndex": 0, "DataSize": 0},
            {"TableName": "Medium", "ColumnName": "C", "Cardinality": 1, "Dictionary": 500, "HashIndex": 0, "DataSize": 0},
        ]
        diagnostics = build_structured_diagnostics(stats_records, model_size=0)
        assert [t["name"] for t in diagnostics["tables"]] == ["Big", "Medium", "Small"]
        assert [c["table"] for c in diagnostics["columns"]] == ["Big", "Medium", "Small"]

    def test_missing_numeric_fields_default_to_zero_without_raising(self):
        stats_records = [{"TableName": "Sales", "ColumnName": "Amount"}]
        diagnostics = build_structured_diagnostics(stats_records, model_size=0)
        assert diagnostics["columns"] == [
            {"table": "Sales", "name": "Amount", "cardinality": 0, "sizeBytes": 0, "dictionarySizeBytes": 0, "dataSizeBytes": 0}
        ]

    def test_non_numeric_model_size_defaults_to_zero(self):
        diagnostics = build_structured_diagnostics([], model_size="not-a-number")
        assert diagnostics["totalSizeBytes"] == 0

    def test_empty_stats_records_returns_empty_tables_and_columns(self):
        diagnostics = build_structured_diagnostics([], model_size=12345)
        assert diagnostics == {"totalSizeBytes": 12345, "tables": [], "columns": []}


# ---------------------------------------------------------------------------
# (2) linhas sem TableName/ColumnName sao ignoradas sem erro
# ---------------------------------------------------------------------------
class TestRowsMissingIdentifiersAreSkipped:
    def test_row_without_table_name_is_skipped(self):
        stats_records = [
            {"ColumnName": "Orphan", "Cardinality": 5, "Dictionary": 10, "HashIndex": 0, "DataSize": 0},
            {"TableName": "Sales", "ColumnName": "Amount", "Cardinality": 1, "Dictionary": 1, "HashIndex": 1, "DataSize": 1},
        ]
        diagnostics = build_structured_diagnostics(stats_records, model_size=0)
        assert len(diagnostics["columns"]) == 1
        assert diagnostics["columns"][0]["name"] == "Amount"

    def test_row_without_column_name_is_skipped(self):
        stats_records = [
            {"TableName": "Sales", "Cardinality": 5, "Dictionary": 10, "HashIndex": 0, "DataSize": 0},
        ]
        diagnostics = build_structured_diagnostics(stats_records, model_size=0)
        assert diagnostics["columns"] == []
        assert diagnostics["tables"] == []

    def test_row_with_empty_string_identifiers_is_skipped(self):
        stats_records = [
            {"TableName": "", "ColumnName": "Amount", "Cardinality": 5, "Dictionary": 10, "HashIndex": 0, "DataSize": 0},
            {"TableName": "Sales", "ColumnName": "", "Cardinality": 5, "Dictionary": 10, "HashIndex": 0, "DataSize": 0},
        ]
        diagnostics = build_structured_diagnostics(stats_records, model_size=0)
        assert diagnostics["columns"] == []
        assert diagnostics["tables"] == []

    def test_mix_of_valid_and_invalid_rows_does_not_raise_and_keeps_only_valid(self):
        stats_records = [
            {"ColumnName": "NoTable"},
            {"TableName": "NoColumn"},
            {},
            {"TableName": "Sales", "ColumnName": "Amount", "Cardinality": 5, "Dictionary": 10, "HashIndex": 0, "DataSize": 0},
        ]
        diagnostics = build_structured_diagnostics(stats_records, model_size=0)
        assert len(diagnostics["columns"]) == 1
        assert len(diagnostics["tables"]) == 1


# ---------------------------------------------------------------------------
# (3) scalar_from com atributo ausente devolve None sem lancar
# ---------------------------------------------------------------------------
class TestScalarFrom:
    def test_missing_attribute_on_fake_pbixray_returns_none_without_raising(self):
        fake_class = make_fake_pbixray_class(records={})  # sem "size" em scalars nem em records
        model = fake_class("fake-path.pbix")
        diagnostics: list[str] = []

        result = scalar_from(model, "size", diagnostics)

        assert result is None
        assert any("size" in entry for entry in diagnostics)

    def test_present_scalar_attribute_is_returned_as_is(self):
        fake_class = make_fake_pbixray_class(records={}, scalars={"size": 123456})
        model = fake_class("fake-path.pbix")
        diagnostics: list[str] = []

        result = scalar_from(model, "size", diagnostics)

        assert result == 123456
        assert diagnostics == []

    def test_attribute_that_raises_on_access_is_caught_and_returns_none(self):
        class ExplodingModel:
            @property
            def size(self):
                raise RuntimeError("boom")

        diagnostics: list[str] = []
        result = scalar_from(ExplodingModel(), "size", diagnostics)

        assert result is None
        assert any("boom" in entry for entry in diagnostics)


# ---------------------------------------------------------------------------
# (4) tabela de sistema aparece no diagnostico (nao e filtrada)
# ---------------------------------------------------------------------------
class TestSystemTablesAreNotFiltered:
    def test_local_date_table_appears_in_diagnostics(self):
        stats_records = [
            {"TableName": "Sales", "ColumnName": "Amount", "Cardinality": 100, "Dictionary": 100, "HashIndex": 0, "DataSize": 0},
            {"TableName": "LocalDateTable_abcd1234", "ColumnName": "Date", "Cardinality": 3650, "Dictionary": 5000, "HashIndex": 100, "DataSize": 400},
        ]
        diagnostics = build_structured_diagnostics(stats_records, model_size=0)

        table_names = {t["name"] for t in diagnostics["tables"]}
        assert "LocalDateTable_abcd1234" in table_names

        system_table = next(t for t in diagnostics["tables"] if t["name"] == "LocalDateTable_abcd1234")
        assert system_table["sizeBytes"] == 5500
        assert system_table["columnCount"] == 1

        column_tables = {c["table"] for c in diagnostics["columns"]}
        assert "LocalDateTable_abcd1234" in column_tables


# ---------------------------------------------------------------------------
# Fim-a-fim: /api/analyze devolve "diagnostics" no shape esperado, com o
# pipeline real (analyze_pbix -> records_from/scalar_from -> build_structured_diagnostics).
# ---------------------------------------------------------------------------
class TestEndToEndAnalyzePbix:
    def test_analyze_endpoint_returns_diagnostics_field_built_from_fake_model(self, live_server, monkeypatch):
        records = {
            "statistics": [
                {"TableName": "Sales", "ColumnName": "Amount", "Cardinality": 500, "Dictionary": 1000, "HashIndex": 200, "DataSize": 300},
                {"TableName": "Region", "ColumnName": "Name", "Cardinality": 10, "Dictionary": 40, "HashIndex": 10, "DataSize": 10},
            ],
        }
        patch_pbixray(monkeypatch, backend, records, scalars={"size": 42000})

        response = requests.post(
            f"{live_server}/api/analyze",
            data=make_empty_pbix_bytes(),
            headers={"Origin": live_server, "Content-Type": "application/octet-stream"},
            timeout=15,
        )
        assert response.status_code == 200, response.text
        body = response.json()

        assert "diagnostics" in body
        assert body["diagnostics"]["totalSizeBytes"] == 42000
        assert body["diagnostics"]["tables"][0]["name"] == "Sales"
        assert body["diagnostics"]["tables"][0]["sizeBytes"] == 1500
        assert "rowCount" not in body["diagnostics"]["tables"][0]

    def test_analyze_endpoint_without_size_attribute_still_returns_diagnostics_with_zero_total(self, live_server, monkeypatch):
        # Versao mais antiga do pbixray (ou modelo sem essa propriedade) --
        # scalar_from() devolve None graciosamente, e build_structured_diagnostics
        # trata isso como 0 em vez de propagar o None/lancar.
        records = {
            "statistics": [
                {"TableName": "Sales", "ColumnName": "Amount", "Cardinality": 500, "Dictionary": 1000, "HashIndex": 200, "DataSize": 300},
            ],
        }
        patch_pbixray(monkeypatch, backend, records)  # sem scalars={"size": ...}

        response = requests.post(
            f"{live_server}/api/analyze",
            data=make_empty_pbix_bytes(),
            headers={"Origin": live_server, "Content-Type": "application/octet-stream"},
            timeout=15,
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["diagnostics"]["totalSizeBytes"] == 0
        assert len(body["diagnostics"]["tables"]) == 1
