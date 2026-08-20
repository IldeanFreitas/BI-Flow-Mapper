"""Regressao G22: `scripts/generate_connector_catalog.py::validate_catalog()`
roda limpo (sem "ERROR:") contra o `connector_catalog.py` real do repo.

`scripts/` fica fora do rootdir de `pythonpath = .` (pytest.ini so cobre a
raiz do repo) -- inserimos o caminho no sys.path aqui, mesmo padrao
defensivo de conftest.py para a raiz do projeto.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from generate_connector_catalog import validate_catalog  # noqa: E402  (import apos ajuste de sys.path)


def test_validate_catalog_reports_no_errors_against_real_catalog():
    problems = validate_catalog()

    errors = [line for line in problems if line.startswith("ERROR:")]
    assert errors == [], f"connector_catalog.py com problemas de integridade: {errors}"


def test_validate_catalog_known_warn_about_unreachable_preferred_patterns_is_documented():
    # Achado real, documentado na secao 5 do docstring do script (nao e bug
    # de shape, e gap de dado conhecido e triado separadamente) -- este
    # teste so trava que o WARN continua sendo reportado como WARN (nao
    # silenciosamente removido, nem promovido a ERROR sem decisao
    # deliberada).
    problems = validate_catalog()
    warns = [line for line in problems if line.startswith("WARN:")]
    assert any("PREFERRED_PATTERN_CONNECTORS" in line for line in warns)


def test_validate_catalog_detects_shape_violation_in_synthetic_bad_entry():
    # Prova que a funcao de fato PEGA um problema real (nao so "sempre
    # devolve lista vazia por acidente") -- catalogo sintetico com entrada
    # sem patterns/keywords e outra faltando chave obrigatoria.
    bad_catalog = [
        {
            "name": "Sem Deteccao",
            "icon": "SDX",
            "image": "",
            "iconUrl": "",
            "doc": "",
            "patterns": [],
            "keywords": [],
        },
        {
            "name": "Faltando Chave",
            "icon": "FLT",
            "image": "",
            "iconUrl": "",
            "patterns": ["Faltando.Chave"],
            # "doc"/"keywords" ausentes de proposito
        },
    ]
    problems = validate_catalog(bad_catalog)
    errors = [line for line in problems if line.startswith("ERROR:")]

    assert any("sem patterns e sem keywords" in line for line in errors)
    assert any("faltam chaves" in line for line in errors)
