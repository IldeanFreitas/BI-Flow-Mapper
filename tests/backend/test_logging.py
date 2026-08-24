"""Testes de configure_logging()/LOG_FILE (G13).

`logger = configure_logging()` roda uma unica vez, na importacao do modulo
`backend` (mesmo processo/mesma sessao de pytest para todos os arquivos de
teste aqui) -- entao LOG_FILE ja existe e pode ja ter conteudo de outros
testes quando este arquivo roda. Em vez de exigir "arquivo vazio no
inicio", medimos o tamanho ANTES de forcar uma falha real via
`live_server` e conferimos que os bytes ADICIONADOS depois contem a
entrada esperada -- prova tanto a criacao (o arquivo existe e cresce)
quanto o conteudo (nivel ERROR + mensagem + rota) exigidos pelo item.
"""
from __future__ import annotations

import logging

import requests

from backend import LOG_FILE, logger
from _pbix_fixtures import make_empty_pbix_bytes


def test_log_file_exists_after_backend_import():
    # configure_logging() roda no import do modulo (nivel de arquivo) --
    # se RUNTIME_DIR for gravavel (caso normal em dev/CI), o RotatingFileHandler
    # ja deve ter criado o arquivo fisico neste ponto.
    assert LOG_FILE.exists(), (
        "bi-flow-mapper.log nao foi criado -- configure_logging() deve ter "
        "criado o arquivo (ou o RUNTIME_DIR de teste nao e gravavel)."
    )


def test_logger_is_a_named_non_propagating_logger_with_a_handler():
    assert logger.name == "bi_flow_mapper"
    assert logger.propagate is False
    assert len(logger.handlers) >= 1


def test_exception_in_post_endpoint_is_persisted_to_log_file(live_server, monkeypatch):
    import bi_server

    def fail_analysis(_path):
        raise RuntimeError("falha sintetica depois da validacao do PBIX")

    monkeypatch.setattr(bi_server, "analyze_pbix", fail_analysis)
    before_size = LOG_FILE.stat().st_size if LOG_FILE.exists() else 0

    # A entrada agora passa primeiro pela validacao ZIP G32. Forcamos uma
    # falha no analisador apos essa fronteira para continuar protegendo o
    # contrato de logging do 500 inesperado.
    response = requests.post(
        f"{live_server}/api/analyze",
        data=make_empty_pbix_bytes(),
        headers={"Origin": live_server},
        timeout=10,
    )
    assert response.status_code == 500

    raw_bytes_after = LOG_FILE.read_bytes()
    new_bytes = raw_bytes_after[before_size:]
    new_text = new_bytes.decode("utf-8", errors="replace")

    assert "Falha ao processar POST /api/analyze" in new_text
    assert "ERROR" in new_text
    assert "bi_flow_mapper" in new_text


def test_client_response_does_not_leak_raw_exception_message(live_server, monkeypatch):
    """Regressao: a resposta HTTP 500 deve trazer uma mensagem generica --
    o detalhe completo (que pode incluir path local/nome de arquivo do
    cliente) fica so no log server-side. Achado real do security-reviewer
    na Fase 2 -- ver BACKLOG.md/G7."""
    import bi_server

    def fail_analysis(_path):
        raise RuntimeError("detalhe interno que nao pode vazar")

    monkeypatch.setattr(bi_server, "analyze_pbix", fail_analysis)
    response = requests.post(
        f"{live_server}/api/analyze",
        data=make_empty_pbix_bytes(),
        headers={"Origin": live_server},
        timeout=10,
    )
    assert response.status_code == 500
    body = response.json()
    assert body == {"error": "Falha ao processar o arquivo. Veja bi-flow-mapper.log para detalhes."}
    # a mensagem crua da excecao real (levantada por PBIXRay) nao deve
    # aparecer na resposta ao cliente
    assert "RuntimeError" not in response.text
    assert "detalhe interno" not in response.text
