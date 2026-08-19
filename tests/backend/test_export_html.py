"""Testes fim-a-fim de /api/export-html (G20).

Mesmo padrao de test_server_integration.py: servidor real (fixture
live_server, ThreadingHTTPServer + Handler sem mock) numa porta efemera,
batido com `requests`/socket cru. O parser binario do pbixray
(`PBIXRay(str(path))`) e substituido por uma classe fake
(`_pbix_fixtures.patch_pbixray`) que expoe os mesmos atributos "amigaveis"
que `records_from`/`list_from` leem -- suficiente para exercitar o pipeline
de geracao de HTML (`build_documentation_html` e os `build_*_rows` que ele
reaproveita do DOCX) sem depender de um .pbix binario real.
"""
from __future__ import annotations

import requests

import backend
from backend import MAX_UPLOAD_BYTES

from _http_helpers import raw_http_post, status_and_json_of
from _pbix_fixtures import make_empty_pbix_bytes, patch_pbixray

MALICIOUS_TABLE_NAME = 'Sales & "Special" <script>alert(1)</script>'


def _records_with_malicious_table():
    return {
        "tmschema_tables": [
            {"Name": MALICIOUS_TABLE_NAME, "IsHidden": False},
            {"Name": "Region", "IsHidden": False},
        ],
        "schema": [
            {"TableName": MALICIOUS_TABLE_NAME, "ColumnName": "Amount", "DataType": "Int64"},
            {"TableName": "Region", "ColumnName": "RegionID", "DataType": "Int64"},
        ],
        "relationships": [
            {
                "FromTableName": MALICIOUS_TABLE_NAME,
                "FromColumnName": "RegionID",
                "ToTableName": "Region",
                "ToColumnName": "RegionID",
                "Cardinality": "2",
                "IsActive": True,
                "CrossFilteringBehavior": "1",
            }
        ],
        # Sql.Database(...) dispara a deteccao de conector "SQL Server" em
        # detect_connector_nodes -- garante que `sources` fica nao-vazio,
        # o que faz build_architecture_svg tambem gerar um SVG (alem do ERD
        # via `relationships` acima), para exercitar os DOIS pontos de
        # embutimento de SVG no HTML gerado.
        "power_query": [
            {
                "TableName": MALICIOUS_TABLE_NAME,
                "Expression": 'let Source = Sql.Database("myserver.database.windows.net", "SalesDB") in Source',
            }
        ],
    }


class TestSecurityBattery:
    """Mesma bateria de seguranca ja coberta para /api/export-docx em
    test_server_integration.py -- /api/export-html passa pelo MESMO bloco
    de validacao de Origin/Content-Length em do_POST, entao a regressao aqui
    e igualmente critica."""

    def test_cross_origin_is_blocked(self, live_server):
        response = requests.post(
            f"{live_server}/api/export-html",
            data=b"fake-body-not-a-real-pbix",
            headers={"Origin": "https://evil.example.com"},
            timeout=5,
        )
        assert response.status_code == 403
        assert response.json()["error"] == "Origem nao permitida."

    def test_oversized_content_length_is_blocked(self, live_server):
        oversized_declared_length = MAX_UPLOAD_BYTES + 1
        raw = raw_http_post(
            live_server,
            "/api/export-html",
            headers={"Content-Length": str(oversized_declared_length)},
            body=b"tiny-body",
        )
        status, body = status_and_json_of(raw)
        assert status == 413

    def test_unauthenticated_same_origin_request_is_not_blocked_by_origin_check(self, live_server, monkeypatch):
        # Nao chega ate build_documentation_html de verdade aqui -- so prova
        # que passou da guarda de Origin (corpo invalido faria 500 dentro do
        # try/except, o que ja e suficiente para provar que nao foi 403).
        response = requests.post(
            f"{live_server}/api/export-html",
            data=b"not-a-real-pbix-file",
            headers={"Origin": live_server},
            timeout=5,
        )
        assert response.status_code != 403


class TestSuccessfulExport:
    def test_response_headers_and_escaped_content(self, live_server, monkeypatch):
        patch_pbixray(monkeypatch, backend, _records_with_malicious_table())

        response = requests.post(
            f"{live_server}/api/export-html",
            data=make_empty_pbix_bytes(),
            headers={"Origin": live_server, "Content-Type": "application/octet-stream"},
            timeout=10,
        )
        assert response.status_code == 200, response.text

        assert "text/html" in response.headers["Content-Type"]
        content_disposition = response.headers["Content-Disposition"]
        assert content_disposition.startswith("attachment;")
        assert ".html" in content_disposition

        body = response.text
        assert "<!DOCTYPE html>" in body

        # SVG (ERD/arquitetura) so pode aparecer embutido como imagem
        # base64 -- nunca inline no DOM. Protecao contra XML/HTML injection
        # via nome de tabela malicioso (G20): um <svg> inline com o nome de
        # tabela cru dentro executaria/quebraria o parsing; como data-URI
        # base64 dentro de <img>, o navegador so renderiza como imagem.
        assert "<svg" not in body
        assert body.count("data:image/svg+xml;base64,") >= 1

        # Nome de tabela malicioso aparece ESCAPADO em toda parte, nunca cru.
        assert "<script>alert(1)</script>" not in body
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in body
        assert "Sales &amp;" in body
        assert "&quot;Special&quot;" in body

    def test_connection_string_secret_is_masked_in_generated_html(self, live_server, monkeypatch):
        # Reaproveita a mesma protecao G7 -- build_source_rows/build_query_rows
        # chamam mask_secrets antes de escrever qualquer connection string/
        # expressao M no HTML, igual ja fazem para o DOCX.
        records = {
            "tmschema_datasources": [
                {"Name": "SalesDb", "Kind": "Sql", "ConnectionString": "Data Source=srv;Pwd=TopSecret123;"}
            ],
        }
        patch_pbixray(monkeypatch, backend, records)

        response = requests.post(
            f"{live_server}/api/export-html",
            data=make_empty_pbix_bytes(),
            headers={"Origin": live_server},
            timeout=10,
        )
        assert response.status_code == 200, response.text
        body = response.text
        assert "TopSecret123" not in body
        assert "***MASKED***" in body
