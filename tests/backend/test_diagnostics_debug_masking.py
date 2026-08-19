"""Regressao: achado real do security-reviewer na auditoria da Fase 3.

`analyze_pbix()` grava um dump de debug de `model.relationships` (colunas +
primeira linha) na lista `diagnostics`, que vira o campo `warnings` da
resposta de `/api/analyze` (endpoint sem autenticacao, por design) e tambem
entra na secao "Diagnosticos" do export DOCX/HTML via
`build_readable_warnings()`. Esse dump nao passava por `mask_secrets()`,
diferente de todo o resto do pipeline (M/DAX, connection strings, RLS) --
inconsistencia corrigida em `pbix_analysis.py` (ver BACKLOG.md/G7).

O conteudo real de `relationships` e so metadado de schema (nomes de
tabela/coluna, cardinalidade), nao segredo tipo connection string -- mas o
teste verifica o mecanismo de mascaramento em si, nao uma alegacao de que
esse DataFrame especifico normalmente contem segredos.
"""
from __future__ import annotations

import io
import zipfile

import pytest

from backend import analyze_pbix

from _pbix_fixtures import patch_pbixray


class FakeRelationshipsFrame:
    """DataFrame-like minimo: so o que `records_from`/o bloco de debug usam
    (`to_dict(orient="records")`, `.columns`, `len()`, `.iloc[i].to_dict()`)."""

    def __init__(self, rows):
        self._rows = rows

    def to_dict(self, orient="records"):
        assert orient == "records"
        return list(self._rows)

    @property
    def columns(self):
        return list(self._rows[0].keys()) if self._rows else []

    def __len__(self):
        return len(self._rows)

    @property
    def iloc(self):
        rows = self._rows

        class _Row:
            def __init__(self, data):
                self._data = data

            def to_dict(self):
                return self._data

        class _Iloc:
            def __getitem__(self, idx):
                return _Row(rows[idx])

        return _Iloc()


def make_minimal_pbix_path(tmp_path):
    zip_path = tmp_path / "fake.pbix"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("placeholder.txt", "not a real pbix, only for zip-open in extract_visuals_from_layout")
    return zip_path


class TestRelationshipsDebugDumpIsMasked:
    def test_secret_like_value_in_relationships_first_row_is_masked_in_warnings(self, monkeypatch, tmp_path):
        rows = [
            {
                "FromTableName": "Sales",
                "FromColumnName": "CustomerID",
                "ToTableName": "Customer",
                "ToColumnName": "ID",
                "Cardinality": "Many",
                # valor sintetico que bate no catch-all de token longo do
                # mask_secrets -- simula um caso real onde um campo
                # inesperado do DataFrame do pbixray carregasse algo sensivel.
                "Note": "apikeyABCDEFGHIJ1234567890XYZ",
            }
        ]
        patch_pbixray(monkeypatch, __import__("backend"), records={"relationships": FakeRelationshipsFrame(rows)})

        graph = analyze_pbix(make_minimal_pbix_path(tmp_path))
        warnings_text = " ".join(graph.get("warnings", []))

        assert "ABCDEFGHIJ1234567890XYZ" not in warnings_text
        assert "***MASKED***" in warnings_text
        # o resto do conteudo legivel (nomes de tabela/coluna) continua presente
        assert "Sales" in warnings_text
        assert "Customer" in warnings_text

    def test_relationships_columns_line_is_masked_too(self, monkeypatch, tmp_path):
        rows = [{"FromTableName": "T1", "LongToken": "X" * 25}]
        patch_pbixray(monkeypatch, __import__("backend"), records={"relationships": FakeRelationshipsFrame(rows)})

        graph = analyze_pbix(make_minimal_pbix_path(tmp_path))
        warnings_text = " ".join(graph.get("warnings", []))

        assert "X" * 25 not in warnings_text
