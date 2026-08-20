"""Testes de integracao fim-a-fim de POST /api/analyze-tmdl (G17) contra o
servidor real (mesmo padrao de test_server_integration.py: `live_server` +
`requests`, sem mockar `Handler`).

Upload multipart real com N partes chamadas "tmdl_files" (uma por arquivo
`.tmdl`) -- `requests` aceita isso passando uma LISTA de tuplas
`(campo, (filename, conteudo, content_type))` com o mesmo nome de campo
repetido, exatamente o formato que `Handler.read_tmdl_uploads()` espera.
"""
from __future__ import annotations

import requests

from backend import MAX_UPLOAD_BYTES

from _http_helpers import raw_http_post, status_and_json_of
from _tmdl_fixtures import (
    REGION_TABLE_TMDL,
    SALES_TABLE_TMDL,
    UNRECOGNIZABLE_TMDL,
    full_semantic_model_files,
)


def _multipart_files(pairs):
    """Converte [(caminho_relativo, conteudo), ...] no formato de `files=`
    do requests, todos sob o mesmo nome de campo "tmdl_files"."""
    return [
        ("tmdl_files", (relative_path, content, "text/plain"))
        for relative_path, content in pairs
    ]


class TestSuccessfulTmdlUpload:
    def test_two_files_returns_200_with_expected_graph_shape(self, live_server):
        response = requests.post(
            f"{live_server}/api/analyze-tmdl",
            files=_multipart_files(full_semantic_model_files()),
            headers={"Origin": live_server},
            timeout=15,
        )
        assert response.status_code == 200, response.text
        body = response.json()

        assert body["source"] == "tmdl"
        assert body["fileName"] == "SalesModel"
        labels = {node["label"] for node in body["nodes"]}
        assert {"Sales", "Region", "Total Sales", "Total Sales YTD", "MarginPct"} <= labels
        assert len(body["relationships"]) == 1
        assert len(body["securityRoles"]) == 1

    def test_model_name_is_derived_from_first_segment_of_uploaded_paths(self, live_server):
        response = requests.post(
            f"{live_server}/api/analyze-tmdl",
            files=_multipart_files([("MeuOutroModelo.SemanticModel/definition/tables/Sales.tmdl", SALES_TABLE_TMDL)]),
            headers={"Origin": live_server},
            timeout=15,
        )
        assert response.status_code == 200, response.text
        assert response.json()["fileName"] == "MeuOutroModelo"


class TestCrossOriginBlocked:
    def test_cross_origin_request_is_blocked_with_403(self, live_server):
        response = requests.post(
            f"{live_server}/api/analyze-tmdl",
            files=_multipart_files(full_semantic_model_files()),
            headers={"Origin": "https://evil.example.com"},
            timeout=15,
        )
        assert response.status_code == 403
        assert response.json()["error"] == "Origem nao permitida."

    def test_same_origin_is_not_blocked_by_origin_check(self, live_server):
        response = requests.post(
            f"{live_server}/api/analyze-tmdl",
            files=_multipart_files(full_semantic_model_files()),
            headers={"Origin": live_server},
            timeout=15,
        )
        assert response.status_code != 403


class TestOversizedContentLength:
    def test_declared_content_length_above_limit_returns_413(self, live_server):
        # Mesma tecnica de test_server_integration.py: `requests` recalcula
        # Content-Length a partir do corpo real, entao para simular um
        # cliente que MENTE sobre o tamanho e preciso falar HTTP cru no
        # socket (`_http_helpers.raw_http_post`).
        oversized_declared_length = MAX_UPLOAD_BYTES + 1
        raw = raw_http_post(
            live_server,
            "/api/analyze-tmdl",
            headers={
                "Content-Length": str(oversized_declared_length),
                "Content-Type": "multipart/form-data; boundary=BOUND",
            },
            body=b"tiny-body-much-smaller-than-the-declared-length",
        )
        status, body = status_and_json_of(raw)
        expected_message = f"Arquivo excede o limite de {MAX_UPLOAD_BYTES // (1024 * 1024)} MB."
        assert status == 413
        assert body["error"] == expected_message


class TestNoTmdlFileInUpload:
    def test_upload_without_any_tmdl_file_returns_400_with_specific_message(self, live_server):
        # Campo "tmdl_files" presente, mas a extensao nao e ".tmdl" (ex.: um
        # .json de layout do .Report/ que veio junto por engano) --
        # read_tmdl_uploads() filtra silenciosamente, do_POST devolve 400
        # ANTES mesmo de chamar analyze_tmdl_files().
        response = requests.post(
            f"{live_server}/api/analyze-tmdl",
            files=[("tmdl_files", ("layout.json", "{}", "application/json"))],
            headers={"Origin": live_server},
            timeout=15,
        )
        assert response.status_code == 400
        assert "Nenhum arquivo .tmdl encontrado" in response.json()["error"]

    def test_empty_multipart_body_returns_400(self, live_server):
        response = requests.post(
            f"{live_server}/api/analyze-tmdl",
            files=[("other_field", ("ignored.txt", "x", "text/plain"))],
            headers={"Origin": live_server},
            timeout=15,
        )
        assert response.status_code == 400
        assert "Nenhum arquivo .tmdl encontrado" in response.json()["error"]


class TestInvalidTmdlContentReturns400NotServerError:
    def test_unrecognizable_tmdl_content_returns_400_via_tmdl_analysis_error(self, live_server):
        response = requests.post(
            f"{live_server}/api/analyze-tmdl",
            files=_multipart_files([("Modelo.SemanticModel/definition/garbage.tmdl", UNRECOGNIZABLE_TMDL)]),
            headers={"Origin": live_server},
            timeout=15,
        )
        # TmdlAnalysisError -> 400 com mensagem clara (bi_server.py:
        # handle_analyze_tmdl), nunca o 500 generico usado para falhas
        # inesperadas.
        assert response.status_code == 400
        assert "reconhecer" in response.json()["error"]

    def test_second_file_in_upload_does_not_rescue_first_files_recognizable_content(self, live_server):
        # Confirma que arquivos MISTOS (um reconhecivel + um so-ruido) ainda
        # produzem 200 normalmente -- so o caso TOTALMENTE vazio de
        # conteudo reconhecivel deve virar 400 (TmdlAnalysisError so
        # dispara quando NADA foi reconhecido em NENHUM arquivo).
        response = requests.post(
            f"{live_server}/api/analyze-tmdl",
            files=_multipart_files([
                ("Modelo.SemanticModel/definition/tables/Region.tmdl", REGION_TABLE_TMDL),
                ("Modelo.SemanticModel/definition/garbage.tmdl", UNRECOGNIZABLE_TMDL),
            ]),
            headers={"Origin": live_server},
            timeout=15,
        )
        assert response.status_code == 200, response.text
        assert any(node["label"] == "Region" for node in response.json()["nodes"])
