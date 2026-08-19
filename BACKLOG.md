# Backlog — BI Flow Mapper

Fonte de verdade dos itens priorizados no discovery de 2026-08-19 ([relatório completo](https://claude.ai/code/artifact/18471cca-47da-42d2-aaf9-765ce9897eed)). Mantido pela squad `biflowmapper-*` (`~/.claude/agents/biflowmapper-*.md`). Cada item fecha só com teste correspondente — ver skill `biflowmapper-testing`.

Legenda: `[ ]` pendente · `[x]` feito e testado · `[~]` parcial (motivo anotado).

## Fase 1 — Quick wins (0–30 dias) — ✅ concluída em 2026-08-19
- [x] **G2** — `LICENSE` (MIT) criado, titular JoseMalan/2026 (autor do primeiro commit)
- [x] **G3** — `requirements.txt` documenta Python 3.10–3.13 e a quebra conhecida em 3.14
- [x] **G9** — Drag-and-drop real (`dragenter`/`dragover`/`dragleave`/`drop` reaproveitando `loadPbix()`)
- [x] **G16** — README reposiciona "grátis/OSS/zero-instalação/zero-admin" logo na abertura, com ressalva honesta sobre o SmartScreen (G1 ainda não resolvido)
- [x] **G8** — Pacote WCAG AA: `lang` sincronizado, `aria-live` no status e no painel de impacto, `role="listitem"` removido, `aria-pressed` no nó selecionado, `.lang-btn` ≥24px
- [x] **G5** — Origin/Sec-Fetch-Site validado + limite de upload (500MB) antes do `rfile.read` — **achado de segurança corrigido**: a versão inicial confiava no header `Host` da própria requisição, abrindo brecha de bypass via DNS rebinding; removido, ver `is_cross_origin_request` em `backend.py`
- [x] **G6** — Allowlist de arquivos estáticos — **achado de segurança corrigido**: `posixpath.normpath` não neutralizava traversal via `\`/`%5c`; bloqueado explicitamente em `is_allowed_static_path`

**Testes**: 51 testes pytest (`tests/backend/`, incluindo regressão dos 2 achados de segurança) + 20 testes Vitest/jsdom (`tests/frontend/`) — todos verdes. `biflowmapper-security-reviewer` auditou a fase inteira. `.exe` rebuildado (`dist/BI Flow Mapper.exe`, 49MB) com as mudanças.

## Fase 2 — Estruturais (30–90 dias) — ✅ concluída em 2026-08-19 (exceto G17)
- [x] **G4** — CI (`.github/workflows/tests.yml`, jobs `backend` + `frontend`) + suíte expandida
- [x] **G7** — `mask_secrets()` cobre os 8 helpers de export + agora também `securityRoles` (achado da auditoria)
- [x] **G15** — `build_unused_objects()`: BFS reverso a partir de visuais, campo `unusedObjects` em `/api/analyze`. Limitação conhecida: medida→calc_column via DAX sem aresta explícita pode dar falso positivo
- [x] **G10** — Busca textual (`nodeMatchesSearch`, debounce 180ms), campo por label + expressão M/DAX
- [x] **G11** — Zoom real (`applyZoom`/`computeFitScale`/`fitGraph`) + wheel com Ctrl/Cmd
- [x] **G13** — Logging estruturado (`bi-flow-mapper.log`, `RotatingFileHandler`)
- [x] **G20** — Novo endpoint `/api/export-html`, SVG sempre embutido como base64 (nunca inline), mesma validação de Origin/tamanho
- [x] **G19** — `pbixray` expõe `model.rls`/`model.ols` prontos — `build_structured_security()` implementado, campo `securityRoles` em `/api/analyze` (ainda sem consumidor no export/UI)
- [ ] **G17** — Investigado e **não implementado**: exigiria (a) affordance de seleção de pasta no frontend, fora do escopo desta rodada, e (b) um parser TMDL não-trivial (blocos DAX/M multi-linha por indentação) comparável em tamanho aos outros 5 itens combinados. Fica para uma rodada dedicada.

**Achados de segurança da auditoria pós-fase, corrigidos antes de fechar:**
- Mensagem de erro HTTP 500 vazava `str(exception)` crua ao cliente (path local, nome de arquivo) — agora mensagem genérica, detalhe completo só no log
- `securityRoles`/RLS não passava por `mask_secrets()` — corrigido
- **XSS armazenado pré-existente** (não introduzido nesta fase, mas achado agora): `renderDetails()` interpolava nomes de nó na lista "afeta" sem `escapeHtml()` — um `.pbix` malicioso podia executar script ao abrir o painel de impacto. Corrigido.

**Testes**: 90 pytest + 55 Vitest (145 total), incluindo regressão dos 3 achados acima. `.exe` rebuildado.

## Fase 3 — Estratégicos (90+ dias) — ✅ concluída em 2026-08-19 (G1 parcial)

**Achados de segurança da auditoria pós-fase, corrigidos antes de fechar:**
- Recursão sem limite em `_resolve_select_entity` (G14): Report/Layout malicioso com `Expression` aninhada ~1500+ níveis derrubava a extração estrutural inteira com `RecursionError`, engolido por um `except` amplo que zerava a linhagem de TODOS os visuais do relatório, não só o malicioso. Corrigido com limite explícito de profundidade (50 níveis — cobre hierarquias de data legítimas, rejeita aninhamento adversarial)
- Dump de debug de `relationships` (colunas + primeira linha, usado na seção "Diagnósticos" do export) não passava por `mask_secrets()`, diferente do resto do pipeline — corrigido

**Testes**: 133 pytest + 55 Vitest (188 total). `.exe` rebuildado e validado ao vivo.


- [x] **G14** — Linhagem visual↔campo agora navega a árvore JSON estrutural real (`prototypeQuery.Select`/`projections`) para tabela/cartão/barra/linha/pizza; regex vira fallback explícito (`refSource`/`linkType: "structural"|"heuristic"` em cada aresta) para custom visuals e layouts fora do padrão
- [~] **G1** — Assinar digitalmente o executável — dono: `biflowmapper-packaging-engineer`. Pesquisa concluída e caminho documentado em `docs/CODE_SIGNING.md`: SignPath Foundation assina OSS sem custo (projeto parece elegível — MIT, licença única) via aplicação manual em signpath.io. `codesign_identity` no `.spec` **não foi alterado** (segue `None`) — não há certificado real ainda. Próximo passo é **ação manual do dono do projeto**: submeter a aplicação em signpath.io, aguardar aprovação (dias a semanas) e, se aprovado, configurar o step de assinatura no CI (condicionado a tag de release). Alternativa paga se a aplicação gratuita não avançar: Azure Trusted Signing (~US$9,99/mês).
- [x] **G12** — `backend.py` (4017 linhas) virou orquestrador de 265 linhas + 7 módulos (`bi_server.py`, `pbix_analysis.py`, `doc_export.py`, `render_graphics.py`, `connector_matching.py`, `graph_utils.py`, `logging_setup.py`); `app.js` virou 13 módulos ES em `src/` (`index.html` carrega `<script type="module" src="src/main.js">`). Interface pública preservada (`from backend import X` continua funcionando p/ todos os testes). `app.js` deletado após validação completa (build real do `.exe` testado ao vivo, todos os 13 módulos servidos com 200)
- [x] **G18** — `build_structured_diagnostics()`: tamanho e cardinalidade por tabela/coluna via `model.statistics`/`model.size` do pbixray, campo `diagnostics` em `/api/analyze`. `rowCount` deliberadamente omitido (pbixray não expõe barato) — não fingido

## Menores / registrados, fora da priorização principal
- [ ] Corrigir 2 strings PT-BR sem acentuação no export (ver skill `biflowmapper-i18n`)
- [ ] Versionar o script de geração do `connector_catalog.py`
- [ ] Feedback de progresso (spinner) para análise de PBIX grandes

---
Depois de cada fase, `biflowmapper-security-reviewer` audita o que mudou antes de marcar a fase como fechada.
