"""Fixtures compartilhadas dos testes de backend.py.

`backend.py` vive na raiz do projeto, fora de `tests/`, e nao e um pacote
instalado -- entao garantimos que a raiz do repo esteja em sys.path antes de
qualquer `import backend`. `pytest.ini` (pythonpath=.) ja cobre isso quando o
rootdir e detectado corretamente, mas repetimos aqui de forma defensiva para
que os testes tambem funcionem se alguem rodar so `pytest` (sem `-m`) de um
cwd diferente ou sem o ini sendo lido por algum motivo.
"""
from __future__ import annotations

import sys
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend import HOST, Handler  # noqa: E402  (import apos ajuste de sys.path)


@pytest.fixture
def live_server():
    """Sobe o `Handler` real (sem mock) num `ThreadingHTTPServer` numa porta
    efemera escolhida pelo SO (bind em porta 0), roda numa thread daemon, e
    derruba tudo no teardown.

    O valor de um teste de integracao aqui esta em bater no roteamento e na
    serializacao *reais* do handler -- mockar `Handler` perderia exatamente
    o que estamos tentando proteger (G5/G6).
    """
    server = ThreadingHTTPServer((HOST, 0), Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://{HOST}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
