"""Testes de integracao fim-a-fim contra o servidor real (G5/G6).

Sobe ThreadingHTTPServer + Handler de verdade (fixture live_server, em
conftest.py) numa porta efemera e bate com `requests` real -- sem mockar
Handler. O objetivo e pegar erro de roteamento/serializacao real que um
teste unitario da logica pura (test_cross_origin.py, test_static_allowlist.py)
nao pegaria.
"""
from __future__ import annotations

import requests

from backend import MAX_UPLOAD_BYTES

from _http_helpers import raw_http_post, status_and_json_of


def test_health_endpoint_returns_ok(live_server):
    response = requests.get(f"{live_server}/api/health", timeout=5)
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True


def test_get_root_serves_index(live_server):
    response = requests.get(f"{live_server}/", timeout=5)
    assert response.status_code == 200
    assert "text/html" in response.headers.get("Content-Type", "")


def test_get_backend_py_is_blocked(live_server):
    # backend.py fica na mesma pasta servida como "directory" do
    # SimpleHTTPRequestHandler (ROOT) -- sem a allowlist do G6, isso serviria
    # o proprio codigo-fonte do servidor.
    response = requests.get(f"{live_server}/backend.py", timeout=5)
    assert response.status_code == 404


def test_get_connector_catalog_py_is_blocked(live_server):
    response = requests.get(f"{live_server}/connector_catalog.py", timeout=5)
    assert response.status_code == 404


def test_get_requirements_txt_is_blocked(live_server):
    response = requests.get(f"{live_server}/requirements.txt", timeout=5)
    assert response.status_code == 404


def test_get_path_traversal_out_of_allowlist_is_blocked(live_server):
    response = requests.get(f"{live_server}/image/../backend.py", timeout=5)
    assert response.status_code == 404


def test_post_analyze_cross_origin_is_blocked(live_server):
    response = requests.post(
        f"{live_server}/api/analyze",
        data=b"fake-body-not-a-real-pbix",
        headers={
            "Origin": "https://evil.example.com",
            "Content-Type": "application/octet-stream",
        },
        timeout=5,
    )
    assert response.status_code == 403
    assert response.json()["error"] == "Origem nao permitida."


def test_post_export_docx_cross_origin_is_blocked(live_server):
    response = requests.post(
        f"{live_server}/api/export-docx",
        data=b"fake-body-not-a-real-pbix",
        headers={"Origin": "https://evil.example.com"},
        timeout=5,
    )
    assert response.status_code == 403
    assert response.json()["error"] == "Origem nao permitida."


def test_post_analyze_same_origin_is_not_blocked_by_origin_check(live_server):
    # Origin batendo com o host do proprio servidor deve passar da checagem
    # de origem (o teste nao vai ate a analise real do pbix -- corpo
    # invalido gera 500 dentro do try/except de analyze_pbix, o que ja prova
    # que passou pela guarda de origem sem ser barrado com 403).
    response = requests.post(
        f"{live_server}/api/analyze",
        data=b"not-a-real-pbix-file",
        headers={"Origin": live_server},
        timeout=5,
    )
    assert response.status_code != 403


def test_post_analyze_oversized_content_length_returns_413_without_reading_body(live_server):
    # Nao manda 500MB de verdade: manda um corpo minusculo mas declara um
    # Content-Length maior que MAX_UPLOAD_BYTES. O servidor precisa rejeitar
    # ANTES de tentar ler o corpo inteiro -- se a checagem estivesse depois
    # do self.rfile.read(length), esta chamada ficaria pendurada ate o
    # timeout em vez de responder rapido com 413.
    #
    # `requests` nao serve aqui: ele recalcula Content-Length a partir do
    # corpo real sempre que ha corpo, entao um header explicito "mentiroso"
    # e sobrescrito antes de sair pela rede. Por isso falamos HTTP cru no
    # socket (_http_helpers.raw_http_post) para garantir que o Content-Length
    # que o servidor recebe e exatamente o que o teste declarou.
    oversized_declared_length = MAX_UPLOAD_BYTES + 1
    raw = raw_http_post(
        live_server,
        "/api/analyze",
        headers={
            "Content-Length": str(oversized_declared_length),
            "Content-Type": "application/octet-stream",
        },
        body=b"tiny-body-much-smaller-than-the-declared-length",
    )
    status, body = status_and_json_of(raw)
    expected_message = f"Arquivo excede o limite de {MAX_UPLOAD_BYTES // (1024 * 1024)} MB."
    assert status == 413
    assert body["error"] == expected_message


def test_post_export_docx_oversized_content_length_returns_413(live_server):
    oversized_declared_length = MAX_UPLOAD_BYTES + 1
    raw = raw_http_post(
        live_server,
        "/api/export-docx",
        headers={"Content-Length": str(oversized_declared_length)},
        body=b"tiny-body",
    )
    status, body = status_and_json_of(raw)
    assert status == 413


def test_post_analyze_invalid_content_length_returns_400(live_server):
    raw = raw_http_post(
        live_server,
        "/api/analyze",
        headers={"Content-Length": "not-a-number"},
        body=b"tiny-body",
    )
    status, body = status_and_json_of(raw)
    assert status == 400
    assert body["error"] == "Content-Length invalido."


def test_post_unknown_path_returns_404(live_server):
    response = requests.post(f"{live_server}/api/does-not-exist", data=b"x", timeout=5)
    assert response.status_code == 404
