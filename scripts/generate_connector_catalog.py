#!/usr/bin/env python3
"""G22 (BACKLOG.md): documenta e versiona o processo de geracao/validacao de
`connector_catalog.py`, que hoje se autodeclara "Generated from
MicrosoftDocs/powerquery-docs connectors index. Do not edit by hand." sem
nenhum script de geracao no repo.

────────────────────────────────────────────────────────────────────────────
1) O QUE `connector_catalog.py` E HOJE (fonte de dados atual)
────────────────────────────────────────────────────────────────────────────
Um dict Python ESTATICO (`POWER_QUERY_CONNECTORS`, ~166 entradas em
2026-08-20), sem nenhuma etapa de build -- o arquivo em si E o dado, versionado
como codigo-fonte comum. Cada entrada e um dict com EXATAMENTE estas 7 chaves
(confirmado inspecionando as 166 entradas reais -- ver `validate_catalog()`
abaixo, que trava essa forma):

    {
        "name":    str,        # nome de exibicao (ex.: "SQL Server", "Excel")
        "icon":    str,        # abreviacao curta pro badge compacto na UI
                                # (ex.: "SQL", "ACC") -- curada a mao, nao
                                # extraivel de nenhuma pagina de doc
        "image":   str,        # nome de arquivo do icone 64x64 sob
                                # assets/connectors/ (pode ser "" -- 1 das
                                # 166 entradas nao tem, ex.: "SharePoint")
        "iconUrl": str,        # "" ou f"assets/connectors/{image}" -- usado
                                # direto pelo frontend (src/*.js) como <img src>
        "doc":     str,        # "" ou "<slug>.md" -- nome do arquivo de doc
                                # do conector no repo powerquery-docs original
        "patterns": list[str], # nomes de funcao M que indicam este conector
                                # sem ambiguidade (ex.: "Sql.Database") --
                                # casados via `connector_matching.has_connector_call`
        "keywords": list[str], # palavras/frases de fallback pra casar contra
                                # texto livre (M/connection string) quando
                                # nenhum pattern bate -- `datasource_matches`
    }

`connector_matching.py` consome isso via `detect_connector_nodes()`: pattern
match tem prioridade sobre keyword match, e `PREFERRED_PATTERN_CONNECTORS`
resolve ambiguidade quando o MESMO pattern aparece em mais de um conector
(ex.: "PostgreSQL.Database" aparece em 3 entradas -- "PostgreSQL" e a
escolhida). Qualquer regeneracao futura do dict PRECISA preservar essa forma
exata, ou `connector_matching.py`/`pbix_analysis.py` param de funcionar sem
nenhum erro obvio (deteccao de conector so fica silenciosamente pior).

────────────────────────────────────────────────────────────────────────────
2) SOBRE RECRIAR O SCRAPER ORIGINAL -- investigado, nao reconstruivel
────────────────────────────────────────────────────────────────────────────
O comentario no topo do arquivo aponta para o repo GitHub
`MicrosoftDocs/powerquery-docs`. Investigacao feita em 2026-08-20 (com acesso
de rede real neste ambiente):

  - `https://github.com/MicrosoftDocs/powerquery-docs` -> HTTP 404 (via
    `api.github.com/repos/...` E via `github.com` direto no navegador).
  - A pagina viva `https://learn.microsoft.com/en-us/power-query/connectors/`
    (essa SIM publica e acessivel) ainda linka pra
    `github.com/MicrosoftDocs/powerquery-docs/blob/main/.../connectors/index.md`
    como seu "Edit this document" -- ou seja, o repo EXISTIU e alimentou essa
    pagina, mas nao esta mais publicamente acessivel hoje (mais provavel:
    Microsoft privatizou/consolidou esse repo durante uma reorganizacao dos
    repos de docs -- varios `MicrosoftDocs/*-docs` passaram por isso em
    2023-2025). Um fork antigo (`I-Alpha/powerquery-docs`) existe mas so tem
    13 paginas de conector com convencao de nome de arquivo DIFERENTE
    (`SQLServer.md` PascalCase, nao `sql-server.md` como em `doc` aqui) --
    claramente uma copia velha/parcial, nao a fonte usada para gerar este
    catalogo.

  Conclusao honesta: **nao da para reconstruir o scraper ORIGINAL** (o
  repo-fonte exato nao existe mais publicamente). O que ESTE script faz em
  vez disso, dividido em duas partes com garantias bem diferentes:

  (a) `validate_catalog()` -- FUNCIONA DE VERDADE, sem depender de rede,
      contra o `connector_catalog.py` real do repo. E o que deve rodar em
      CI/antes de qualquer edicao manual do catalogo. Ver secao 3.

  (b) `fetch_live_connector_index()` -- esqueleto de regeneracao a partir de
      uma fonte VIVA equivalente: a propria tabela de compatibilidade em
      `learn.microsoft.com/en-us/power-query/connectors/` (publica, HTML
      renderizado no servidor -- confirmado acessivel nesta investigacao).
      Funciona (testado ao vivo, ver secao 4), mas so extrai NOME +
      SLUG-DE-DOC + ARQUIVO-DE-ICONE de cada conector listado na tabela --
      "icon" (abreviacao) e "keywords" nao estao nessa pagina (bastante
      provavel que tenham sido curados a mao ou derivados por outra
      ferramenta na geracao original), e "patterns" (nomes de funcao M)
      exigiriam abrir a pagina de doc de CADA conector individualmente e
      procurar por chamadas de funcao nos exemplos -- fora do escopo de um
      esqueleto. Regeneracao completa automatizada continua NAO viável sem
      mais trabalho manual/heuristico; o valor real deste script hoje e (a).

────────────────────────────────────────────────────────────────────────────
3) VALIDACAO -- rode antes de qualquer edicao manual do catalogo
────────────────────────────────────────────────────────────────────────────
    python scripts/generate_connector_catalog.py --validate   (default)

Verificacoes reais, todas passando contra o `connector_catalog.py` atual
(rodado em 2026-08-20 -- ver relato do backend-engineer):
  - lista de dicts, cada um com EXATAMENTE as 7 chaves do shape da secao 1;
  - tipos corretos (name/icon/image/iconUrl/doc: str: patterns/keywords: list[str]);
  - "name" nao-vazio e unico (alerta tambem em colisao case-insensitive,
    already resolved hoje: nenhuma);
  - "icon" nao-vazio (usado direto como texto do badge -- vazio quebraria a UI);
  - todo conector tem pelo menos 1 pattern OU 1 keyword (sem isso,
    `detect_connector_nodes` nunca o encontraria -- entrada morta);
  - "iconUrl" == f"assets/connectors/{image}" quando "image" existe, "" caso
    contrario (consistencia interna);
  - quando "image" existe, o arquivo REALMENTE existe em `assets/connectors/`
    no disco (checagem de integridade real contra o filesystem, nao so o dict);
  - "doc" termina em ".md" quando nao-vazio;
  - patterns duplicados entre conectores diferentes (existem hoje: 4 casos,
    ex. "Csv.Document" em "Text/CSV" e "CSV") sao TODOS cobertos por
    `connector_matching.PREFERRED_PATTERN_CONNECTORS` (senao a deteccao fica
    ambigua/nao-deterministica);
  - [achado novo desta investigacao, reportado como alerta -- nao e um erro
    de validacao de shape, e uma inconsistencia de dado real] chaves de
    `PREFERRED_PATTERN_CONNECTORS` cujo pattern NAO aparece em NENHUM
    conector do catalogo -- ver secao 5.

────────────────────────────────────────────────────────────────────────────
4) REGENERACAO (esqueleto, best-effort, depende de rede)
────────────────────────────────────────────────────────────────────────────
    python scripts/generate_connector_catalog.py --fetch-live-index

Faz scraping da tabela de compatibilidade viva e imprime quantas entradas
achou + uma comparacao (por nome exato) contra o catalogo atual. Overlap por
nome exato e esperado ser BAIXO mesmo com o scraper funcionando -- nosso
catalogo canonicaliza varias variantes de produto num unico nome (ver
`connector_matching.CANONICAL_CONNECTOR_NAMES`, ex.: "SharePoint Folder" +
"SharePoint Online List" -> "SharePoint" no catalogo), enquanto a tabela viva
lista cada variante separadamente. O parser (regex sobre HTML, nao um parser
de arvore de verdade) e FRAGIL POR DESIGN contra mudanca de marcacao da
pagina -- Microsoft pode mudar isso sem aviso; se `--fetch-live-index` parar
de achar entradas, comece checando a marcacao HTML atual da pagina antes de
assumir bug no script. Isso nunca escreve em `connector_catalog.py` --
qualquer merge de entrada nova exige revisao humana (mapear name -> icon
curado, decidir patterns/keywords), por isso o script so IMPRIME um relatorio.

────────────────────────────────────────────────────────────────────────────
5) Achado desta investigacao (fora do escopo de G22 consertar aqui)
────────────────────────────────────────────────────────────────────────────
`connector_matching.PREFERRED_PATTERN_CONNECTORS` referencia 11 patterns que
NAO existem em NENHUM `patterns` de NENHUM conector do catalogo atual (ex.:
"Salesforce.Objects", "Salesforce.Reports", "Snowflake.Databases",
"OData.Feed", "DB2.Database", "OleDb.DataSource"/"OleDb.Query",
"SapBusinessWarehouse.Cubes", "Sybase.Database", "Informix.Database"). Como
`detect_connector_nodes()` so consulta `PREFERRED_PATTERN_CONNECTORS` DENTRO
do loop `for pattern in connector.get("patterns", [])`, uma entrada cujo
pattern nao esta em NENHUM conector nunca e sequer consultada -- essas 11
linhas de `PREFERRED_PATTERN_CONNECTORS` sao efetivamente codigo morto, e
(mais importante) Salesforce/Snowflake/SAP BW/DB2/OleDb/Sybase/Informix/OData
provavelmente NAO sao detectados hoje como conector em um .pbix real que os
use (nenhum conector com esse nome existe no catalogo pra keyword-match
tambem cair de volta). Reportado aqui para triagem separada -- consertar isso
exigiria ADICIONAR entradas novas em `connector_catalog.py` (dado real, nao
so codigo), o que este script deliberadamente nao faz sozinho.
"""
from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REQUIRED_KEYS = {"name", "icon", "image", "iconUrl", "doc", "patterns", "keywords"}
STR_KEYS = ("name", "icon", "image", "iconUrl", "doc")
LIST_KEYS = ("patterns", "keywords")

LIVE_INDEX_URL = "https://learn.microsoft.com/en-us/power-query/connectors/"


def load_current_catalog():
    """Importa o `connector_catalog.py` real do repo (nao uma copia) -- a
    validacao so tem valor se checar o arquivo que de fato vai pro build."""
    sys.path.insert(0, str(REPO_ROOT))
    from connector_catalog import POWER_QUERY_CONNECTORS  # noqa: PLC0415

    return POWER_QUERY_CONNECTORS


def validate_catalog(connectors=None) -> list[str]:
    """Roda todas as checagens de integridade descritas na secao 3 do
    docstring do modulo. Devolve uma lista de strings "ERROR: ..." (falha de
    shape/consistencia real) e "WARN: ..." (achado que nao quebra o
    pipeline, mas vale investigar) -- lista vazia == catalogo 100% saudavel.
    Nao lanca excecao para problemas de DADO (so para bug de uso, ex. tipo
    errado no parametro) -- quem chama decide o que fazer com os achados.
    """
    if connectors is None:
        connectors = load_current_catalog()

    problems: list[str] = []

    if not isinstance(connectors, list):
        return [f"ERROR: POWER_QUERY_CONNECTORS deveria ser list, achou {type(connectors).__name__}"]

    names_exact: dict[str, int] = {}
    names_ci: dict[str, list[str]] = {}
    all_patterns_by_owner: dict[str, list[str]] = {}

    for index, entry in enumerate(connectors):
        label = f"[{index}]"
        if not isinstance(entry, dict):
            problems.append(f"ERROR: {label} nao e um dict ({type(entry).__name__})")
            continue
        label = f"[{index}] {entry.get('name', '<sem name>')!r}"

        keys = set(entry.keys())
        if keys != REQUIRED_KEYS:
            missing = REQUIRED_KEYS - keys
            extra = keys - REQUIRED_KEYS
            if missing:
                problems.append(f"ERROR: {label} faltam chaves: {sorted(missing)}")
            if extra:
                problems.append(f"WARN: {label} chaves extras nao documentadas: {sorted(extra)}")

        for key in STR_KEYS:
            if key in entry and not isinstance(entry[key], str):
                problems.append(f"ERROR: {label} campo {key!r} deveria ser str, achou {type(entry[key]).__name__}")
        for key in LIST_KEYS:
            if key in entry:
                value = entry[key]
                if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                    problems.append(f"ERROR: {label} campo {key!r} deveria ser list[str]")

        name = entry.get("name", "")
        if not isinstance(name, str) or not name.strip():
            problems.append(f"ERROR: {label} 'name' vazio ou invalido")
        else:
            names_exact[name] = names_exact.get(name, 0) + 1
            names_ci.setdefault(name.lower(), []).append(name)

        icon = entry.get("icon")
        if not isinstance(icon, str) or not icon.strip():
            problems.append(f"ERROR: {label} 'icon' vazio ou invalido (quebra o badge na UI)")

        patterns = entry.get("patterns") or []
        keywords = entry.get("keywords") or []
        if not patterns and not keywords:
            problems.append(f"ERROR: {label} sem patterns e sem keywords -- nunca sera detectado")

        image = entry.get("image", "") or ""
        icon_url = entry.get("iconUrl", "") or ""
        expected_icon_url = f"assets/connectors/{image}" if image else ""
        if icon_url != expected_icon_url:
            problems.append(
                f"ERROR: {label} iconUrl {icon_url!r} inconsistente com image {image!r} "
                f"(esperado {expected_icon_url!r})"
            )
        if image:
            asset_path = REPO_ROOT / "assets" / "connectors" / image
            if not asset_path.exists():
                problems.append(f"ERROR: {label} image {image!r} nao existe em assets/connectors/")

        doc = entry.get("doc", "") or ""
        if doc and not doc.endswith(".md"):
            problems.append(f"WARN: {label} doc {doc!r} nao termina em .md (convencao esperada)")

        if isinstance(patterns, list):
            for pattern in patterns:
                all_patterns_by_owner.setdefault(pattern, []).append(name)

    for name, count in names_exact.items():
        if count > 1:
            problems.append(f"ERROR: name {name!r} duplicado ({count}x)")
    for lowered, variants in names_ci.items():
        unique_variants = sorted(set(variants))
        if len(unique_variants) > 1:
            problems.append(f"WARN: nomes colidem ignorando maiusculas/minusculas: {unique_variants}")

    # Cross-checagem com connector_matching.py -- roda sempre (nao so quando
    # ha pattern duplicado), porque o achado da secao 5 (preferencias
    # inalcancaveis) independe de duplicidade.
    try:
        sys.path.insert(0, str(REPO_ROOT))
        from connector_matching import PREFERRED_PATTERN_CONNECTORS  # noqa: PLC0415
    except Exception as error:  # pragma: no cover - so falha se connector_matching.py quebrar
        problems.append(f"ERROR: nao foi possivel importar connector_matching.py para checar PREFERRED_PATTERN_CONNECTORS: {error}")
        PREFERRED_PATTERN_CONNECTORS = None

    if PREFERRED_PATTERN_CONNECTORS is not None:
        dupe_patterns = {p: owners for p, owners in all_patterns_by_owner.items() if len(owners) > 1}
        for pattern, owners in dupe_patterns.items():
            preferred = PREFERRED_PATTERN_CONNECTORS.get(pattern)
            if preferred is None:
                problems.append(
                    f"ERROR: pattern {pattern!r} aparece em varios conectores {owners} "
                    "sem entrada em connector_matching.PREFERRED_PATTERN_CONNECTORS -- deteccao ambigua"
                )
            elif preferred not in owners:
                problems.append(
                    f"ERROR: PREFERRED_PATTERN_CONNECTORS[{pattern!r}] aponta para {preferred!r}, "
                    f"que nao esta entre os donos reais do pattern {owners}"
                )

        # Achado da secao 5: preferencias que nunca sao alcancadas porque o
        # pattern-chave nao pertence a NENHUM conector do catalogo.
        all_registered_patterns = set(all_patterns_by_owner)
        unreachable = sorted(p for p in PREFERRED_PATTERN_CONNECTORS if p not in all_registered_patterns)
        if unreachable:
            problems.append(
                "WARN: PREFERRED_PATTERN_CONNECTORS tem patterns sem nenhum conector correspondente "
                f"no catalogo (nunca consultados, provavel gap de dado -- ver secao 5 do docstring): {unreachable}"
            )

    return problems


# ── Regeneracao (esqueleto best-effort, ver secao 4 do docstring) ──────────

_CONNECTOR_LINK_RE = re.compile(
    r'<a href="([^"]+)" data-linktype="relative-path">'
    r'<img src="media/index/([^"]+)"[^>]*>'
    r'(?:<br>)?\s*<strong>(.*?)</strong>',
    re.DOTALL,
)


def fetch_live_connector_index(timeout: float = 15.0) -> list[dict]:
    """Faz scraping best-effort da tabela de compatibilidade viva em
    learn.microsoft.com (ver secao 4 do docstring do modulo para as
    limitacoes conhecidas). Levanta a excecao original (URLError etc.) se a
    rede nao estiver disponivel -- quem chama decide como reportar isso."""
    import urllib.request  # noqa: PLC0415 -- so usado neste caminho opcional/online

    request = urllib.request.Request(LIVE_INDEX_URL, headers={"User-Agent": "bi-flow-mapper-connector-catalog-script"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8", errors="replace")

    seen: dict[str, dict] = {}
    for slug, image, name_html in _CONNECTOR_LINK_RE.findall(body):
        name = html.unescape(re.sub(r"<br\s*/?>", " ", name_html))
        name = re.sub(r"\s+", " ", name).strip()
        if not name or len(name) > 120:
            continue
        seen.setdefault(slug, {"name": name, "docSlug": slug, "image": image})
    return list(seen.values())


def diff_against_current_catalog(live_entries: list[dict], connectors=None) -> dict:
    """Comparacao best-effort por nome EXATO -- ver secao 4 do docstring
    para por que um overlap baixo e esperado mesmo com o scraper saudavel
    (canonicalizacao de nomes no catalogo atual)."""
    if connectors is None:
        connectors = load_current_catalog()
    catalog_names = {entry["name"] for entry in connectors if isinstance(entry.get("name"), str)}
    live_names = {entry["name"] for entry in live_entries}
    return {
        "liveCount": len(live_entries),
        "catalogCount": len(connectors),
        "exactNameOverlap": sorted(catalog_names & live_names),
        "liveOnlyNames": sorted(live_names - catalog_names)[:40],
    }


def _print_report(lines: list[str], title: str) -> None:
    print(f"=== {title} ===")
    if not lines:
        print("(nenhum problema encontrado)")
        return
    for line in lines:
        print(line)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else "")
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Valida a integridade de connector_catalog.py (default se nenhuma flag for passada).",
    )
    parser.add_argument(
        "--fetch-live-index",
        action="store_true",
        help="Scraping best-effort da tabela de conectores viva (ver secao 4 do docstring). Requer rede.",
    )
    args = parser.parse_args(argv)

    if not args.validate and not args.fetch_live_index:
        args.validate = True

    exit_code = 0

    if args.validate:
        problems = validate_catalog()
        _print_report(problems, "validate_catalog()")
        if any(line.startswith("ERROR:") for line in problems):
            exit_code = 1

    if args.fetch_live_index:
        try:
            live_entries = fetch_live_connector_index()
        except Exception as error:
            print(f"=== fetch_live_connector_index() ===\nERROR: nao foi possivel buscar a pagina viva: {error}")
            exit_code = exit_code or 1
        else:
            report = diff_against_current_catalog(live_entries)
            print("=== fetch_live_connector_index() ===")
            print(f"Entradas encontradas na pagina viva: {report['liveCount']}")
            print(f"Entradas no catalogo atual: {report['catalogCount']}")
            print(f"Overlap por nome exato: {len(report['exactNameOverlap'])} -> {report['exactNameOverlap'][:20]}")
            print(f"Nomes so na pagina viva (ate 40): {report['liveOnlyNames']}")

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
