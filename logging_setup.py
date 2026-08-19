"""G13: logging estruturado e persistente (bi-flow-mapper.log), extraido de
backend.py na modularizacao G12.

Modulo self-contained de proposito: bi_server.py precisa do `logger` daqui
(do_GET/do_POST), e pbix_analysis.py/doc_export.py tambem. Para evitar um
import circular com bi_server.py (que por sua vez precisaria de `logger`
antes de terminar de calcular seu proprio RUNTIME_DIR), este modulo resolve
seu PROPRIO RUNTIME_DIR de forma independente -- a deteccao via `sys.frozen`
e deliberadamente duplicada aqui e em bi_server.py (ambas derivam o MESMO
valor pela MESMA checagem, entao nunca podem divergir na pratica; nao e
"estado" compartilhado no sentido perigoso do termo, so um calculo puro
repetido). Ver BACKLOG.md G12.
"""
from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

if getattr(sys, "frozen", False):
    _RUNTIME_DIR = Path(sys.executable).parent
else:
    _RUNTIME_DIR = Path(__file__).resolve().parent

LOG_FILE = _RUNTIME_DIR / "bi-flow-mapper.log"


def configure_logging() -> logging.Logger:
    log = logging.getLogger("bi_flow_mapper")
    log.setLevel(logging.INFO)
    if not log.handlers:
        try:
            handler: logging.Handler = RotatingFileHandler(
                LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
            )
        except OSError:
            # Diretorio somente-leitura ou sem permissao de escrita: nao
            # derruba o app por causa de logging, so desativa a persistencia.
            handler = logging.NullHandler()
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))
        log.addHandler(handler)
        log.propagate = False
    return log


logger = configure_logging()
