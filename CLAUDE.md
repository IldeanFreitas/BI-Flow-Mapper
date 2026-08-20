# BI Flow Mapper

Explorador visual de linhagem de dados para Power BI — 100% local (sem backend cloud, sem conta, sem telemetria). Backend Python modular (`backend.py` orquestrador + `bi_server.py`/`pbix_analysis.py`/`doc_export.py`/`render_graphics.py`/`connector_matching.py`/`graph_utils.py`/`logging_setup.py`, servidor HTTP local + `pbixray`), frontend em módulos ES sem framework (`src/`, entry point `src/main.js`), desktop via `pywebview` (`main_app.py`), empacotado standalone com PyInstaller (`BI_Flow_Mapper.spec`).

## Squad dedicada

Este projeto tem agentes e skills próprios (prefixo `biflowmapper-*`, globais em `~/.claude/`). Use `biflowmapper-architect` para orquestrar trabalho que cruza backend + frontend + testes; veja `~/.claude/agents/biflowmapper-*.md` para os especialistas individuais (backend, frontend, packaging, testes, segurança, docs) e `~/.claude/skills/biflowmapper-*` para convenções específicas (`backend-modules` = mapa dos 8 módulos Python e o idioma de import adiado, `pbix-extraction`, `i18n`, `a11y-checklist`, `packaging-release`, `testing`).

## Backlog

`BACKLOG.md` na raiz é a fonte de verdade do que falta implementar, priorizado em 3 fases (do discovery de 2026-08-19). Mantenha os checkboxes atualizados conforme os itens fecham.

## Ambiente de dev

- Python **3.12** (não 3.14 — `pbixray`→`xpress9` não tem wheel pra 3.14). Venv em `.venv/`.
- `./.venv/Scripts/python.exe backend.py` (modo browser) ou `main_app.py` (modo desktop).
- Build do `.exe`: `./.venv/Scripts/python.exe -m PyInstaller BI_Flow_Mapper.spec --noconfirm` → `dist/`.
- Testes: `./.venv/Scripts/python.exe -m pytest tests/backend -v` (pytest) e `npx vitest run` (Vitest/jsdom, módulos ES em `src/`).
