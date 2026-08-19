"""Testes unitarios de Handler.is_allowed_static_path (G6).

Mesma tecnica de test_cross_origin.py: instancia via __new__ para pular o
__init__ orientado a socket de BaseRequestHandler, populando so o atributo
que o metodo le (self.path). O metodo real e chamado sem mock.
"""
from __future__ import annotations

import pytest

from backend import Handler


def make_handler(path: str):
    handler = Handler.__new__(Handler)
    handler.path = path
    return handler


class TestExactAllowlist:
    @pytest.mark.parametrize("path", ["/", "/index.html", "/styles.css"])
    def test_exact_paths_allowed(self, path):
        assert make_handler(path).is_allowed_static_path() is True


class TestPrefixAllowlist:
    @pytest.mark.parametrize(
        "path",
        [
            "/image/logo.png",
            "/image/connectors/sql-server-64.png",
            "/assets/foo.json",
            "/assets/sub/dir/bar.txt",
            "/src/main.js",
            "/src/graph-model.js",
        ],
    )
    def test_prefix_paths_allowed(self, path):
        assert make_handler(path).is_allowed_static_path() is True


class TestOutsideAllowlist:
    @pytest.mark.parametrize(
        "path",
        [
            "/backend.py",
            "/connector_catalog.py",
            "/requirements.txt",
            "/requirements-dev.txt",
            "/BACKLOG.md",
            "/BI_Flow_Mapper.spec",
            "/.git/config",
            "/bi-flow-mapper.port",
            "/imageX/logo.png",  # prefixo parecido mas nao igual a "/image/"
        ],
    )
    def test_paths_outside_allowlist_blocked(self, path):
        assert make_handler(path).is_allowed_static_path() is False


class TestPathTraversal:
    @pytest.mark.parametrize(
        "path",
        [
            "/image/../backend.py",
            "/assets/../../backend.py",
            "/image/%2e%2e/backend.py",  # ".." percent-encoded: so vira ".."
            # depois do unquote, entao precisa ser normalizado DEPOIS de
            # decodificar -- se a ordem fosse invertida, escaparia da checagem.
        ],
    )
    def test_traversal_outside_allowlist_blocked(self, path):
        assert make_handler(path).is_allowed_static_path() is False

    def test_traversal_that_resolves_back_inside_prefix_is_allowed(self):
        # Sobe um nivel e desce de volta pro mesmo prefixo permitido -- o
        # destino final normalizado ainda esta dentro de /image/, entao isso
        # e comportamento correto (nao e um escape).
        handler = make_handler("/image/sub/../logo.png")
        assert handler.is_allowed_static_path() is True

    @pytest.mark.parametrize(
        "path",
        [
            "/image/..\\backend.py",
            "/image/..\\..\\backend.py",
            "\\backend.py",
        ],
    )
    def test_backslash_traversal_blocked(self, path):
        """Regressao: posixpath.normpath so entende '/' como separador --
        uma barra invertida crua sobrevive intacta a normalizacao e podia
        escapar do allowlist antes desta checagem explicita. Achado real do
        security-reviewer na Fase 1 do backlog -- ver BACKLOG.md/G6."""
        assert make_handler(path).is_allowed_static_path() is False

    def test_percent_encoded_backslash_traversal_blocked(self):
        handler = make_handler("/image/..%5c..%5cbackend.py")
        assert handler.is_allowed_static_path() is False
