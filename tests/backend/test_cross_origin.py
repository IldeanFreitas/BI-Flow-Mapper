"""Testes unitarios de Handler.is_cross_origin_request (G5).

Handler herda de socketserver.BaseRequestHandler, cujo __init__ tenta lidar
com uma conexao de socket real assim que e construido (setup/handle/finish
na hora) -- entao instanciar via Handler(...) normalmente exige um socket de
verdade. Para testar so a logica pura do metodo, construimos a instancia via
__new__ (pulando __init__/handle) e populamos manualmente so os atributos
que is_cross_origin_request le: self.path, self.headers e self.server. Isso
NAO e mock do metodo sob teste -- e o mesmo objeto Handler real, com o
metodo real sendo chamado; so evitamos abrir um socket para um teste que nao
precisa de um.
"""
from __future__ import annotations

from email.message import Message
from types import SimpleNamespace

import pytest

from backend import Handler

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 4173


def make_handler(headers: dict[str, str] | None = None, host_header: str | None = None):
    handler = Handler.__new__(Handler)
    handler.path = "/api/analyze"
    handler.server = SimpleNamespace(server_address=(SERVER_HOST, SERVER_PORT))

    message = Message()
    for key, value in (headers or {}).items():
        message[key] = value
    if host_header is not None:
        message["Host"] = host_header
    handler.headers = message
    return handler


class TestNoHeaders:
    def test_no_origin_referer_or_sec_fetch_site_is_allowed(self):
        handler = make_handler(headers={})
        assert handler.is_cross_origin_request() is False


class TestOrigin:
    def test_origin_matching_server_ip_and_port_is_allowed(self):
        handler = make_handler(headers={"Origin": f"http://{SERVER_HOST}:{SERVER_PORT}"})
        assert handler.is_cross_origin_request() is False

    def test_origin_matching_localhost_alias_is_allowed(self):
        # is_cross_origin_request trata "localhost:<porta>" como equivalente
        # a "127.0.0.1:<porta>" mesmo que o servidor tenha feito bind so no IP.
        handler = make_handler(headers={"Origin": f"http://localhost:{SERVER_PORT}"})
        assert handler.is_cross_origin_request() is False

    def test_origin_different_host_is_blocked(self):
        handler = make_handler(headers={"Origin": "https://evil.example.com"})
        assert handler.is_cross_origin_request() is True

    def test_origin_same_host_different_port_is_blocked(self):
        handler = make_handler(headers={"Origin": f"http://{SERVER_HOST}:9999"})
        assert handler.is_cross_origin_request() is True


class TestReferer:
    def test_referer_matching_server_is_allowed(self):
        handler = make_handler(headers={"Referer": f"http://{SERVER_HOST}:{SERVER_PORT}/index.html"})
        assert handler.is_cross_origin_request() is False

    def test_referer_different_host_is_blocked(self):
        handler = make_handler(headers={"Referer": "https://evil.example.com/steal-data"})
        assert handler.is_cross_origin_request() is True


class TestSecFetchSite:
    def test_same_origin_is_allowed(self):
        handler = make_handler(headers={"Sec-Fetch-Site": "same-origin"})
        assert handler.is_cross_origin_request() is False

    def test_none_is_allowed(self):
        # "none" == navegacao iniciada diretamente pelo usuario (digitou a
        # URL, abriu favorito), nao por outra pagina.
        handler = make_handler(headers={"Sec-Fetch-Site": "none"})
        assert handler.is_cross_origin_request() is False

    def test_cross_site_is_blocked(self):
        handler = make_handler(headers={"Sec-Fetch-Site": "cross-site"})
        assert handler.is_cross_origin_request() is True

    def test_same_site_is_blocked(self):
        # "same-site" (subdominio/porta diferente da mesma organizacao) nao
        # esta na allowlist do metodo -- so "same-origin"/"none" passam.
        handler = make_handler(headers={"Sec-Fetch-Site": "same-site"})
        assert handler.is_cross_origin_request() is True

    def test_cross_site_header_blocks_even_with_matching_origin(self):
        # Sec-Fetch-Site cross-site deve bloquear mesmo que, por algum
        # motivo, o Origin declarado bata com o host do servidor.
        handler = make_handler(
            headers={
                "Sec-Fetch-Site": "cross-site",
                "Origin": f"http://{SERVER_HOST}:{SERVER_PORT}",
            }
        )
        assert handler.is_cross_origin_request() is True


class TestHostHeader:
    def test_dns_rebinding_origin_matching_forwarded_host_is_still_blocked(self):
        """Regressao: o header Host da propria requisicao NUNCA deve entrar
        no conjunto de origens esperadas. Um atacante controla o dominio que
        o navegador resolve via DNS rebinding para 127.0.0.1 -- do ponto de
        vista do navegador, Origin e Host sempre "batem" um com o outro
        (ambos sao o dominio do atacante), entao usar Host como referencia
        de confianca anula a checagem de Origin inteira. Achado real do
        security-reviewer na Fase 1 do backlog -- ver BACKLOG.md/G5.
        """
        handler = make_handler(
            headers={"Origin": "http://evil.example:4173"},
            host_header="evil.example:4173",
        )
        assert handler.is_cross_origin_request() is True
