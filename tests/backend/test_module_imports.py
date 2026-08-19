"""Regressao G12: cada modulo novo precisa importar limpo como PRIMEIRO
import de um processo Python novo, isoladamente -- sem depender de nenhum
outro modulo do projeto ja ter sido importado antes no mesmo processo.

Por que isso importa: o arquivo monolitico anterior (backend.py com ~4000
linhas) nunca teve essa classe de risco -- so existia um modulo. A
modularizacao (G12) introduziu import circular real entre bi_server.py e
doc_export.py (ver docstrings de ambos: doc_export precisa de `ROOT`, que
vem de bi_server; bi_server precisa de build_documentation_docx/html, que
vem de doc_export). O backend-engineer relatou ter encontrado e corrigido 2
bugs reais de import circular durante o refactor -- este teste tranca essa
classe de regressao especifica.

Um `import module_x; import module_y` dentro do MESMO processo de teste nao
pegaria esse tipo de bug: uma vez que um modulo entra em `sys.modules` (ainda
que parcialmente inicializado), imports subsequentes dele so vinculam o nome
em vez de reexecutar o corpo do modulo -- o que mascara exatamente a ordem
de carregamento que queremos garantir. Por isso cada caso aqui roda um
`subprocess.run([sys.executable, "-c", f"import {module}"])` isolado: um
processo novo, com `sys.modules` vazio, para cada modulo.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

# Todo modulo novo criado pela modularizacao G12, na ordem alfabetica (a
# ordem de execucao do subprocess.run NAO segue a ordem de import interna de
# backend.py -- e essa e exatamente a garantia que este teste quer: cada um
# precisa se bastar sozinho como PRIMEIRO import, em qualquer ordem).
MODULES = [
    "logging_setup",
    "graph_utils",
    "connector_matching",
    "render_graphics",
    "pbix_analysis",
    "doc_export",
    "bi_server",
    "backend",
]


@pytest.mark.parametrize("module_name", MODULES)
def test_module_imports_standalone_as_first_import(module_name):
    """`import {module_name}` como UNICO import do processo precisa ter
    exit code 0 e stderr vazio (sem ImportError/traceback de ciclo)."""
    result = subprocess.run(
        [sys.executable, "-c", f"import {module_name}"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, (
        f"import {module_name!r} isolado falhou "
        f"(returncode={result.returncode}):\n{result.stderr}"
    )
    assert result.stderr == "", (
        f"import {module_name!r} isolado produziu stderr inesperado:\n{result.stderr}"
    )
