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
- [x] **G14** — Linhagem visual↔campo agora navega a árvore JSON estrutural real (`prototypeQuery.Select`/`projections`) para tabela/cartão/barra/linha/pizza; regex vira fallback explícito (`refSource`/`linkType: "structural"|"heuristic"` em cada aresta) para custom visuals e layouts fora do padrão
- [~] **G1** — Assinar digitalmente o executável — dono: `biflowmapper-packaging-engineer`. Pesquisa concluída e caminho documentado em `docs/CODE_SIGNING.md`: SignPath Foundation assina OSS sem custo (projeto parece elegível — MIT, licença única) via aplicação manual em signpath.io. `codesign_identity` no `.spec` **não foi alterado** (segue `None`) — não há certificado real ainda. Próximo passo é **ação manual do dono do projeto**: submeter a aplicação em signpath.io, aguardar aprovação (dias a semanas) e, se aprovado, configurar o step de assinatura no CI (condicionado a tag de release). Alternativa paga se a aplicação gratuita não avançar: Azure Trusted Signing (~US$9,99/mês).
- [x] **G12** — `backend.py` (4017 linhas) virou orquestrador de 265 linhas + 7 módulos (`bi_server.py`, `pbix_analysis.py`, `doc_export.py`, `render_graphics.py`, `connector_matching.py`, `graph_utils.py`, `logging_setup.py`); `app.js` virou 13 módulos ES em `src/` (`index.html` carrega `<script type="module" src="src/main.js">`). Interface pública preservada (`from backend import X` continua funcionando p/ todos os testes). `app.js` deletado após validação completa (build real do `.exe` testado ao vivo, todos os 13 módulos servidos com 200)
- [x] **G18** — `build_structured_diagnostics()`: tamanho e cardinalidade por tabela/coluna via `model.statistics`/`model.size` do pbixray, campo `diagnostics` em `/api/analyze`. `rowCount` deliberadamente omitido (pbixray não expõe barato) — não fingido

**Achados de segurança da auditoria pós-fase, corrigidos antes de fechar:**
- Recursão sem limite em `_resolve_select_entity` (G14): Report/Layout malicioso com `Expression` aninhada ~1500+ níveis derrubava a extração estrutural inteira com `RecursionError`, engolido por um `except` amplo que zerava a linhagem de TODOS os visuais do relatório, não só o malicioso. Corrigido com limite explícito de profundidade (50 níveis — cobre hierarquias de data legítimas, rejeita aninhamento adversarial)
- Dump de debug de `relationships` (colunas + primeira linha, usado na seção "Diagnósticos" do export) não passava por `mask_secrets()`, diferente do resto do pipeline — corrigido

**Testes**: 133 pytest + 55 Vitest (188 total). `.exe` rebuildado e validado ao vivo.

## Fase 4 — Pendências — ✅ concluída em 2026-08-20 (G1 e G22 parciais, por natureza — dependem de ação externa/manual)
- [x] **G17** — Suporte a `.pbip`/TMDL, ponta a ponta. Frontend: `#pbipFolderInput` (`<input webkitdirectory directory multiple>`) ao lado de `#uploadZone`; `filterTmdlFiles()`/`buildTmdlFormData()`/`loadPbipFolder()` em `src/upload.js` filtram `.tmdl`, montam multipart (`tmdl_files`, filename = `webkitRelativePath`) e chamam `POST /api/analyze-tmdl`, reaproveitando `applyBackendGraph()`. Backend: `tmdl_analysis.py` (módulo novo) parseia TMDL por indentação (iterativo, não recursivo — mesma lição do G14) e normaliza pro MESMO shape de registros que `records_from`/`list_from` produziriam do pbixray, reaproveitando os `build_*_nodes`/`build_structured_*` existentes de `pbix_analysis.py` sem duplicar lógica. `bi_server.py` ganhou o endpoint com a mesma validação de Origin/Content-Length dos demais. **Fora de escopo, documentado**: linhagem visual↔campo do `.Report/` (formato PBIR, outro parser inteiro) — `pages`/`unusedObjects` ficam vazios nesse fluxo em vez de fingidos.
- [x] **G21** — Corrigidas 5 strings PT-BR sem acentuação no cluster de export (`btnDocx`, `btnDocxTitle`, `docxNoPbix`, `docxGenerating`, `docxError` em `src/i18n.js`) — revisão do resto do dicionário `pt-BR` não encontrou outras strings sem acento (achado à parte, fora de escopo: `pagesVisualsLabel` pluraliza "visual" como "visualis" em vez de "visuais" — bug de gramática, não de acentuação)
- [~] **G22** — `scripts/generate_connector_catalog.py` criado: documenta o formato real do dict estático (166 entradas, 7 chaves), `validate_catalog()` funcional (roda limpo contra o catálogo real, achou `WARN` real: 11 patterns em `PREFERRED_PATTERN_CONNECTORS` sem entrada correspondente no catálogo — conectores provavelmente não detectados hoje, não corrigido nesta rodada). `MicrosoftDocs/powerquery-docs` não está mais publicamente acessível (confirmado ao vivo) — regeneração automática completa não é viável; `fetch_live_connector_index()` é melhor esforço contra a página live da Microsoft Learn, só roda com `--fetch-live-index` explícito.
- [x] **G23** — Feedback de progresso: spinner CSS (`.spinner`/`@keyframes bifm-spin`, `styles.css`) junto de `#workspaceSubtitle` (novo `#loadingSpinner`), controlado por `setLoading()` (`src/dom-refs.js`) em `try/finally` nos dois fluxos que fazem fetch demorado (`loadPbix()` e o novo `loadPbipFolder()`, `src/upload.js`) — visível do início do upload até a resposta chegar, sucesso ou erro. `aria-live="polite"` de `#workspaceSubtitle` (G8) preservado, spinner é `aria-hidden="true"` (reforço visual, não duplica o anúncio pra leitor de tela).

**Achados da auditoria pós-fase**: nenhum bloqueante. Parser TMDL testado sob carga adversarial real (indentação até ~31.600 níveis, 500k linhas, 50k arquivos multipart) — sem ReDoS, sem escrita em disco, sem custo desproporcional. `meta.expression` (M/DAX) não mascarado no JSON ao vivo de `/api/analyze`/`/api/analyze-tmdl` é paridade intencional (requisitante já precisa possuir o arquivo-fonte; masking real importa nos exports compartilháveis, que já mascaram) — não é regressão. 2 achados cosméticos corrigidos (comentário desatualizado em `tmdl_analysis.py`, checkbox G22).

**Testes**: 181 pytest + 75 Vitest (256 total). `.exe` rebuildado.

---
Depois de cada fase, `biflowmapper-security-reviewer` audita o que mudou antes de marcar a fase como fechada.

## Fase 5 — Evolução orientada por evidências (2026-08-24)

Origem: avaliação técnica, benchmark e refatoração de 2026-08-24. Prioridades
usam impacto × esforço; todo item novo deve preservar o processamento 100% local.

### Concluído nesta rodada

- [x] **G25** — Exportação HTML disponível na interface. O botão reutiliza o
  endpoint `/api/export-html`, o locale e o fluxo de download/Save As do DOCX,
  sem duplicar a implementação em `src/export.js`. Cobertura:
  `tests/frontend/export-html.test.js`.
- [x] **G26** — README alinhado ao produto: export HTML documentado, requisito
  de Python corrigido para 3.10–3.13 e roadmap passa a descrever a futura tela
  de diagnósticos, em vez de declarar como futura uma exportação já entregue.
- [x] **G30** — Travessia de grafo otimizada. `buildGraphIndex()` cria
  adjacências de entrada/saída e índice de nós; seleção, detalhes e filtro de
  linhagem os reutilizam. Benchmark sintético local de 1.000 nós: mediana de
  19,611 ms → 0,191 ms (102,7×). Cobertura:
  `tests/frontend/graph-model.test.js`.
- [x] **G31** — Correções de acessibilidade P0: tabs com setas/Home/End e
  roving tabindex; radiogroup de idioma navegável; foco preservado após
  re-render do card; canvas com semântica de grupo interativo; foco visível no
  upload. Cobertura: `tests/frontend/accessibility.test.js`.

**Validação da rodada:** 195 pytest + 90 Vitest = **285 testes aprovados**.

### P0 — Próximo ciclo (alto impacto)

- [x] **G24** — Aba **Insights** expõe `diagnostics`, `securityRoles` e
  `unusedObjects` já devolvidos pelo backend.
  - Entregue: três blocos visíveis para PBIX; TMDL exibe “indisponível” onde
    não há `.Report`/VertiPaq, nunca zero enganoso; i18n EN/PT-BR; testes de
    integração em `tests/frontend/insights.test.js`.
  - Métrica atingida: 3 superfícies de dados antes invisíveis agora acessíveis.
- [x] **G27** — Proveniência das arestas (`linkType` estrutural ou heurístico)
  exibida no mapa e no painel de detalhe.
  - Entregue: legenda textual, linha sólida verde para evidência estrutural,
    linha tracejada laranja para inferência heurística, rótulos nos detalhes e
    i18n EN/PT-BR. Cobertura: `tests/frontend/lineage-confidence.test.js`.
  - Critério atendido: toda aresta que recebe `linkType` do backend apresenta
    sua confiabilidade no mapa e no detalhe do nó conectado.

### P1 — Robustez, confiança e distribuição

- [x] **G32** — Limitar pressão de memória do upload local: leitura em blocos
  para `SpooledTemporaryFile` (8 MB em memória), teto padrão configurável de
  100 MB, validação do container ZIP e semáforo de duas análises com timeout.
  - Critérios atendidos: cobertura de spool/tamanho, ZIP inválido e razão de
    compressão, concorrência com `429` e limpeza do diretório temporário em
    `tests/backend/test_upload_safety.py`; nenhuma requisição acima do limite
    configurado é lida.
- [x] **G33** — Cabeçalhos defensivos centralizados no `end_headers()` do
  servidor: `nosniff`, CSP local, `DENY` para frame, política de referrer e
  permissões de câmera/localização/microfone bloqueadas. O traceback do
  launcher agora passa por `html.escape()`.
  - Critérios atendidos: respostas estáticas, API e 404 verificadas, além de
    regressão para traceback contendo HTML em
    `tests/backend/test_security_headers.py`.
- [x] **G34** — Removida a importação do Google Fonts; `--font-ui` usa a
  pilha nativa Segoe UI/sistema. A CSP do G33 também limita estilos, scripts,
  fontes e conexões a `'self'`.
  - Critérios atendidos: `tests/frontend/styles.test.js` garante ausência de
    URL de fonte remota e presença do token local; fallback preserva a
    tipografia e o contraste existentes.
- [~] **G1** — Assinatura Authenticode permanece dependente de ação manual do
  mantenedor (SignPath/Azure Trusted Signing). Quando houver credencial, criar
  job Windows de build, assinatura, hash/SBOM e smoke test do executável.

### P2 — Qualidade contínua e aprendizado

- [x] **G28** — CI expandido com lint fatal Python, cobertura e JUnit para
  pytest/Vitest, upload de artefatos e job separado de build Windows. O lock
  de 45 dependências para Python 3.12/Windows é fixado em
  `requirements.lock` e verificado por SHA-256 antes do empacotamento.
  - Critérios atendidos: `scripts/verify_requirements_lock.py`,
    `npm run test:cov` e PyInstaller validados localmente; workflow em
    `.github/workflows/tests.yml` publica os relatórios e o `.exe`.
- [x] **G29** — Instrumentação local e opt-in. Backend só coleta com
  `BIFM_LOCAL_METRICS=1`, em memória e limitado a 200 amostras; frontend só
  coleta após chave explícita no `localStorage`. As amostras trazem duração,
  contagens, cobertura estrutural/heurística e falhas — sem nomes, expressões,
  conexões ou envio de rede.
  - Critérios atendidos: `/api/metrics` local, mediana/p95 backend e amostras
    de render/seleção frontend; cobertura em
    `tests/backend/test_local_metrics.py` e
    `tests/frontend/local-metrics.test.js`.
  - Baseline a coletar: PBIX/PBIP representativos de 50, 250 e 1.000 nós;
    mediana/p95 de análise, render e seleção.
