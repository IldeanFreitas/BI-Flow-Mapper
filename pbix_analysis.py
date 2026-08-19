"""G12: pipeline de extracao/normalizacao de metadados do PBIX (Power Query,
datasources, schema, medidas, colunas calculadas, paginas/visuais, linhagem
estrutural G14, objetos nao usados G15, seguranca estruturada G19,
diagnostico de armazenamento G18) + analyze_pbix(), o orquestrador do
pipeline inteiro. Extraido de backend.py na modularizacao G12.

`analyze_pbix()` precisa de PBIXRay/load_pbixray()/PBIXRAY_IMPORT_ERROR --
essas tres pecas de estado de lazy-loading FICAM em backend.py (nao foram
movidas para ca) porque `tests/backend/_pbix_fixtures.py::patch_pbixray` faz
`monkeypatch.setattr(backend, "PBIXRay", FakeClass)`: o monkeypatch so
alcanca quem resolve o nome `PBIXRay` a partir do NAMESPACE do modulo
`backend` em tempo de chamada. Por isso este modulo faz `import backend`
(nunca `from backend import PBIXRay`, que copiaria o valor `None` inicial e
jamais veria a substituicao feita por load_pbixray()/pelo teste) e usa
`backend.PBIXRay(...)`/`backend.load_pbixray()`/`backend.PBIXRAY_IMPORT_ERROR`
qualificados dentro do corpo de analyze_pbix().

`import backend` (em vez de `from backend import X`) e feito DENTRO do corpo
de analyze_pbix(), nao no topo do modulo -- isso NAO e so por seguranca
extra, e necessario: um `import backend` no topo deste arquivo faria
`import pbix_analysis` (sozinho, sem `backend` ja carregado antes -- ex.
`python -c "import pbix_analysis"`, ou qualquer script/teste futuro que
importe este modulo primeiro) disparar a carga de backend.py, que por sua
vez tenta `from pbix_analysis import analyze_pbix, ...` enquanto este
proprio modulo ainda esta parado na linha `import backend`, no meio do seu
carregamento -- `ImportError: cannot import name ... from partially
initialized module`. Adiando o `import backend` para dentro da funcao,
pbix_analysis.py termina de carregar por completo SEM tocar em `backend`
nenhuma vez no nivel de modulo; o `import backend` so acontece quando
analyze_pbix() e de fato CHAMADO, bem depois de todo mundo (backend.py
incluso) ja ter terminado de carregar, entao sempre encontra `backend` ou
totalmente pronto ou ainda nao tocado (caso em que o proprio Python cuida de
carrega-lo do zero, sem ciclo -- nada mais depende de pbix_analysis.py nesse
ponto).
"""
from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path

from connector_matching import detect_connector_nodes, source_matches_query
from graph_utils import (
    clean_records,
    edge,
    first_value,
    mask_secrets,
    record_text,
    scalar,
    slug,
    titleize,
    unique_by_id,
    unique_edges,
)
from logging_setup import logger


def records_from(model, attr, diagnostics):
    try:
        value = getattr(model, attr)
    except Exception as error:
        diagnostics.append(f"{attr}: {error}")
        # Debug: muitos atributos pbixray sao opcionais (ausentes em modelos
        # sem RLS/OLS, sem perspectivas etc.) -- ja aparece em "diagnostics"
        # (devolvido ao usuario no JSON), so persistimos o traceback aqui.
        logger.debug("records_from(%s) falhou", attr, exc_info=True)
        return []

    if value is None:
        return []
    if hasattr(value, "to_dict"):
        return clean_records(value.to_dict(orient="records"))
    if isinstance(value, list):
        return clean_records(value)
    return []


def list_from(model, attr, diagnostics):
    try:
        value = getattr(model, attr)
    except Exception as error:
        diagnostics.append(f"{attr}: {error}")
        logger.debug("list_from(%s) falhou", attr, exc_info=True)
        return []
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def scalar_from(model, attr, diagnostics):
    """G18: mesmo padrao defensivo de records_from/list_from, mas para um
    atributo escalar (ex.: `model.size`, o tamanho total do modelo em bytes
    -- nao um DataFrame/lista). Devolve None quando o atributo nao existe
    (versao mais antiga do pbixray) ou lanca ao ler."""
    try:
        value = getattr(model, attr)
    except Exception as error:
        diagnostics.append(f"{attr}: {error}")
        logger.debug("scalar_from(%s) falhou", attr, exc_info=True)
        return None
    return scalar(value)


def analyze_pbix(path: Path):
    # Import adiado (nao no topo do modulo) de proposito: quebra o ciclo
    # backend <-> pbix_analysis em qualquer ordem de import (inclusive
    # `import pbix_analysis` standalone, sem `backend` ja carregado) -- ver
    # docstring do modulo para o porque de precisar ser `backend.PBIXRay`
    # qualificado (monkeypatch dos testes) em vez de `from backend import
    # PBIXRay`.
    import backend

    if not backend.load_pbixray():
        raise RuntimeError(f"pbixray nao esta instalado ou nao carregou: {backend.PBIXRAY_IMPORT_ERROR}")

    model = backend.PBIXRay(str(path))
    diagnostics = []

    power_query = records_from(model, "power_query", diagnostics)
    datasource_records = records_from(model, "tmschema_datasources", diagnostics)
    measures = records_from(model, "dax_measures", diagnostics)
    calc_columns_raw = records_from(model, "dax_columns", diagnostics)
    relationships = records_from(model, "relationships", diagnostics)

    # Diagnóstico: exibe as colunas reais para facilitar debug. Vira
    # "warnings" na resposta de /api/analyze (endpoint sem autenticacao) e
    # entra na secao "Diagnosticos" do export -- mask_secrets() por
    # consistencia com o resto do pipeline, mesmo sendo so metadado de
    # schema (nomes de tabela/coluna), nao segredo tipo connection string.
    try:
        raw_rels = getattr(model, "relationships", None)
        if raw_rels is not None and hasattr(raw_rels, "columns"):
            diagnostics.append(mask_secrets(f"relationships columns: {list(raw_rels.columns)}"))
            if len(raw_rels) > 0:
                diagnostics.append(mask_secrets(f"relationships first row: {raw_rels.iloc[0].to_dict()}"))
    except Exception as _e:
        diagnostics.append(f"relationships debug error: {_e}")
        logger.debug("relationships debug error", exc_info=True)
    schema = records_from(model, "schema", diagnostics)
    semantic_tables = records_from(model, "tmschema_tables", diagnostics)
    tables = list_from(model, "tables", diagnostics)
    visuals = extract_visuals_from_layout(path)

    # G19: RLS (row-level security) e OLS (object-level security). pbixray
    # expoe as duas como propriedades "amigaveis" (`model.rls`/`model.ols`)
    # ja resolvidas a partir de TablePermission/ColumnPermission/Role --
    # graceful no records_from() se a versao instalada nao tiver esses
    # atributos (modelo sem seguranca definida ou lib mais antiga).
    rls_records = records_from(model, "rls", diagnostics)
    ols_records = records_from(model, "ols", diagnostics)

    # G18: diagnostico tecnico de armazenamento (tamanho/cardinalidade por
    # tabela/coluna). `model.statistics` e `model.size` sao propriedades
    # "amigaveis" que pbixray ja calcula a partir do log VertiPaq do proprio
    # .pbix -- ver build_structured_diagnostics() para o porque do shape e
    # do que NAO da pra expor (rowCount) sem reimplementar analise VertiPaq.
    stats_records = records_from(model, "statistics", diagnostics)
    model_size = scalar_from(model, "size", diagnostics)

    connector_nodes = detect_connector_nodes(power_query, datasource_records)
    query_nodes = build_query_nodes(power_query, connector_nodes)
    table_nodes = build_table_nodes(tables, schema, semantic_tables, query_nodes)
    measure_nodes = build_measure_nodes(measures)
    calc_column_nodes = build_calc_column_nodes(calc_columns_raw)
    visual_nodes = build_visual_nodes(visuals)

    nodes = unique_by_id(connector_nodes + query_nodes + table_nodes + measure_nodes + calc_column_nodes + visual_nodes)
    edges = []
    valid_node_ids = {node["id"] for node in nodes}

    for query in query_nodes:
        query_text = query_search_text(query)
        matched_sources = [
            source for source in connector_nodes
            if source_matches_query(source, query_text)
        ]
        if not matched_sources and len(connector_nodes) == 1:
            matched_sources = connector_nodes
        for source in matched_sources:
            edges.append(edge(source["id"], query["id"], "uses connector"))

    table_by_label = {node["label"].lower(): node for node in table_nodes}
    for query in query_nodes:
        table = table_by_label.get(query["label"].lower())
        if table:
            edges.append(edge(query["id"], table["id"], "loads table"))

    # Relacionamentos entre tabelas do modelo NÃO entram no grafo do Mapa.
    # Eles são exibidos exclusivamente no painel "Relacionamentos" via structured_rels.

    for measure in measure_nodes:
        table_name = measure["meta"].get("table")
        if table_name and f"model:{slug(table_name)}" in valid_node_ids:
            edges.append(edge(f"model:{slug(table_name)}", measure["id"], "defines measure"))
        edges.extend(build_measure_dependency_edges(measure, measure_nodes, table_nodes))

    for calc_col in calc_column_nodes:
        table_name = calc_col["meta"].get("table")
        if table_name and f"model:{slug(table_name)}" in valid_node_ids:
            edges.append(edge(f"model:{slug(table_name)}", calc_col["id"], "defines calc column"))
        # Calc columns can also reference measures
        edges.extend(build_calc_column_dependency_edges(calc_col, measure_nodes, table_nodes))

    edges.extend(build_visual_edges(visual_nodes, measure_nodes, table_nodes, calc_column_nodes))

    if not nodes:
        nodes.append({
            "id": "file:pbix",
            "type": "source",
            "label": path.name,
            "icon": "PBX",
            "meta": {"expression": "\n".join(diagnostics) or "PBIXRay nao retornou metadados."},
        })

    diagnostics.append(f"Power Query rows: {len(power_query)}")
    diagnostics.append(f"Data source rows: {len(datasource_records)}")
    diagnostics.append(f"Tables: {len(table_nodes)}")
    diagnostics.append(f"Semantic table rows: {len(semantic_tables)}")
    diagnostics.append(f"Measures: {len(measure_nodes)}")
    diagnostics.append(f"Calculated columns: {len(calc_column_nodes)}")
    diagnostics.append(f"Relationships: {len(relationships)}")
    diagnostics.append(f"Visuals inferred from layout: {len(visual_nodes)}")

    structured_rels = build_structured_relationships(relationships)

    pages = extract_pages_from_layout(path)

    deduped_edges = unique_edges(edges)
    unused_objects = build_unused_objects(nodes, deduped_edges)
    diagnostics.append(f"Unused objects (measures + calc columns): {len(unused_objects)}")

    security_roles = build_structured_security(rls_records, ols_records)
    diagnostics.append(f"Security roles (RLS/OLS): {len(security_roles)}")

    # G18: variavel deliberadamente nomeada diferente da lista `diagnostics`
    # acima (que e o log de avisos, devolvido em "warnings") para nao colidir
    # -- esta e a tela tecnica de armazenamento, devolvida na chave "diagnostics".
    model_diagnostics = build_structured_diagnostics(stats_records, model_size)
    diagnostics.append(f"Diagnostics: {len(model_diagnostics['tables'])} tables, {len(model_diagnostics['columns'])} columns profiled")

    return {
        "nodes": nodes,
        "edges": deduped_edges,
        "warnings": diagnostics,
        "source": "pbixray",
        "relationships": structured_rels,
        "pages": pages,
        "unusedObjects": unused_objects,
        "securityRoles": security_roles,
        "diagnostics": model_diagnostics,
    }


# G15: rotulos de aresta que representam "consumo real" no pipeline (um
# objeto alimentando outro), na direcao origem-alimenta-destino em que
# build_visual_edges/build_measure_dependency_edges/
# build_calc_column_dependency_edges ja as criam. Arestas estruturais como
# "defines measure"/"defines calc column" (tabela -> objeto que ela contem)
# ou "uses connector"/"loads table" NAO contam como uso -- so o fato de uma
# medida existir numa tabela nao significa que ela e consumida por alguem.
USAGE_EDGE_LABELS = {"used in visual", "measure dependency", "referenced in calc column"}


def build_unused_objects(nodes, edges):
    """G15 (Best Practice Analyzer basico): medidas e colunas calculadas que
    nao alimentam nenhum visual, nem diretamente nem transitivamente atraves
    de outra medida/coluna que por sua vez seja usada.

    Reaproveita o grafo de dependencias ja montado por analyze_pbix (mesmas
    arestas do Mapa, sem nenhuma extracao nova): parte dos nos "visual" e
    caminha para tras pelas arestas de USAGE_EDGE_LABELS, marcando como
    "usado" todo no que alimenta, direta ou indiretamente, algum visual.
    Tudo que sobra fora desse conjunto alcancavel e reportado como nao
    usado.

    Limitacao conhecida: os edge-builders atuais (build_measure_dependency_edges/
    build_calc_column_dependency_edges) so detectam referencias DAX
    medida->medida e medida->coluna calculada; uma medida que referencia uma
    COLUNA CALCULADA dentro da sua expressao DAX ainda nao gera aresta hoje,
    entao essa coluna pode aparecer aqui como falso positivo "nao usada".
    Corrigir isso e trabalho do proprio grafo de dependencias, fora do
    escopo desta deteccao.
    """
    visual_ids = {node["id"] for node in nodes if node.get("type") == "visual"}

    reverse_adjacency: dict[str, list[str]] = {}
    for item in edges:
        if item.get("label") in USAGE_EDGE_LABELS:
            reverse_adjacency.setdefault(item["to"], []).append(item["from"])

    used_ids: set[str] = set()
    queue = list(visual_ids)
    while queue:
        current = queue.pop()
        for source_id in reverse_adjacency.get(current, []):
            if source_id not in used_ids:
                used_ids.add(source_id)
                queue.append(source_id)

    unused = []
    for node in nodes:
        node_type = node.get("type")
        if node_type not in ("measure", "calc_column"):
            continue
        if node["id"] in used_ids:
            continue
        unused.append({
            "id": node["id"],
            "name": node.get("label", node["id"]),
            "type": node_type,
            "table": node.get("meta", {}).get("table", ""),
        })
    return unused


def build_structured_relationships(relationships):
    """
    Normaliza os registros de model.relationships do pbixray para o frontend.

    Campos documentados pela API:
      FromTableName, FromColumnName, ToTableName, ToColumnName, Cardinality, IsActive

    CrossFilteringBehavior pode aparecer como coluna extra dependendo da versão;
    lemos se existir, senão marcamos como desconhecido.
    """
    # Mapa de valores numéricos/texto de Cardinality para símbolo legível
    CARD_MAP = {
        "1": "1:M",  "onetomany": "1:M",  "one_to_many": "1:M",
        "2": "M:1",  "manytoone": "M:1",  "many_to_one": "M:1",
        "3": "1:1",  "onetoone":  "1:1",  "one_to_one":  "1:1",
        "4": "M:M",  "manytomany":"M:M",  "many_to_many":"M:M",
    }
    # CrossFilteringBehavior: 1 = OneDirection / Single, 2 = BothDirections / Both
    CF_MAP = {
        "1": "Single", "onedirection": "Single", "single": "Single",
        "2": "Both", "bothdirections": "Both", "both": "Both",
    }

    result = []
    for rel in relationships:
        from_table  = str(rel.get("FromTableName",  "") or "").strip()
        from_col    = str(rel.get("FromColumnName", "") or "").strip()
        to_table    = str(rel.get("ToTableName",    "") or "").strip()
        to_col      = str(rel.get("ToColumnName",   "") or "").strip()
        cardinality = str(rel.get("Cardinality",    "") or "").strip()
        is_active   = rel.get("IsActive", True)
        cross_raw   = str(rel.get("CrossFilteringBehavior", "") or "").strip()

        if not from_table or not to_table:
            continue

        # Normaliza cardinalidade
        card_key = cardinality.lower().replace(" ", "").replace("-", "")
        card_symbol = CARD_MAP.get(card_key, cardinality if cardinality else "–")

        # Normaliza filtro cruzado
        cf_key = cross_raw.lower().replace(" ", "").replace("-", "")
        cf_label = CF_MAP.get(cf_key, cross_raw if cross_raw else "–")

        # IsActive pode vir como bool, int ou string
        if isinstance(is_active, bool):
            active = is_active
        else:
            active = str(is_active).lower() not in ("false", "0", "no", "none", "")

        result.append({
            "fromTable":  from_table,
            "fromColumn": from_col,
            "toTable":    to_table,
            "toColumn":   to_col,
            "cardinality": card_symbol,
            "crossFilter": cf_label,
            "active":      active,
        })
    return result


def build_structured_security(rls_records, ols_records):
    """
    G19: normaliza RLS (row-level security) e OLS (object-level security)
    do modelo semantico para o frontend.

    Fonte: pbixray expoe as duas como views "amigaveis" ja resolvidas --
    `model.rls` (colunas: TableName, RoleName, RoleDescription,
    FilterExpression, State, MetadataPermission) e `model.ols` (colunas:
    RoleName, TableName, ColumnName, Scope, Permission) -- entao aqui so
    agrupamos por papel, sem reinterpretar os DMVs TMSCHEMA_ROLES/
    TMSCHEMA_TABLEPERMISSIONS/TMSCHEMA_COLUMNPERMISSIONS brutos.

    Retorna uma lista de papeis:
      {
        "name": str, "description": str,
        "rowFilters":        [{"table", "expression", "state"}],
        "objectPermissions": [{"table", "column", "scope", "permission"}],
      }
    """
    roles: dict = {}

    def get_role(name, description=""):
        key = str(name or "").strip()
        if key not in roles:
            roles[key] = {
                "name": key,
                "description": str(description or ""),
                "rowFilters": [],
                "objectPermissions": [],
            }
        elif description and not roles[key]["description"]:
            roles[key]["description"] = str(description)
        return roles[key]

    for row in rls_records:
        name = first_value(row, ["RoleName", "Name"])
        if not name:
            continue
        entry = get_role(name, first_value(row, ["RoleDescription", "Description"]))
        table = first_value(row, ["TableName", "Table"])
        expression = first_value(row, ["FilterExpression", "Expression"])
        state = first_value(row, ["State"])
        if table or expression:
            entry["rowFilters"].append({
                "table": str(table),
                # G7: expressao de filtro RLS e devolvida pelo /api/analyze
                # sem autenticacao (design do servidor); mascara segredos
                # que porventura estejam embutidos na expressao DAX, mesmo
                # tratamento ja aplicado a M/DAX no pipeline de export.
                "expression": mask_secrets(str(expression)),
                "state": str(state),
            })

    for row in ols_records:
        name = first_value(row, ["RoleName", "Name"])
        if not name:
            continue
        entry = get_role(name)
        table = first_value(row, ["TableName", "Table"])
        column = first_value(row, ["ColumnName", "Column"])
        scope = first_value(row, ["Scope"])
        permission = first_value(row, ["Permission"])
        entry["objectPermissions"].append({
            "table": str(table),
            "column": str(column) if column else "",
            "scope": str(scope),
            "permission": str(permission),
        })

    return list(roles.values())


def build_structured_diagnostics(stats_records, model_size):
    """
    G18: diagnostico tecnico de armazenamento (tamanho por tabela/coluna,
    cardinalidade) direto do VertiPaq, sem reimplementar nenhuma analise
    VertiPaq do zero.

    Fonte: pbixray ja expoe isso pronto via `model.statistics` (um DataFrame
    com uma linha por coluna fisica do modelo -- colunas TableName,
    ColumnName, Cardinality, Dictionary, HashIndex, DataSize, todas
    calculadas em `pbixray.meta.metadata.Metadata._compute_statistics` a
    partir do log de armazenamento do proprio arquivo .pbix) e `model.size`
    (tamanho total do modelo, em bytes, soma de todo o file_log). Dictionary +
    HashIndex + DataSize somados reproduzem o "Total Size" por coluna que o
    VertiPaq Analyzer mostra; aqui tambem somamos por tabela para dar uma
    visao de "quem pesa mais no modelo".

    Diferente do resto do grafo (`build_table_nodes` etc.), esta view NAO
    filtra tabelas de sistema/hierarquia de data automatica
    (`is_system_table`) de proposito -- tabelas de data auto-geradas ocultas
    sao uma causa comum e conhecida de inchaco de modelo, e e exatamente
    esse tipo de coisa que uma tela de diagnostico tecnico deveria expor.

    NAO inclui contagem de linhas por tabela ("rowCount"): pbixray nao expoe
    isso de forma barata -- a unica forma seria decodificar cada tabela
    inteira via `model.get_table()`/`iter_table()`, o que reintroduziria
    exatamente o custo de leitura completa que uma tela de diagnostico
    "leve" deveria evitar (e pode ser lento/pesado em tabelas de fato
    grandes, o cenario que esta tela existe para diagnosticar). Cardinality
    por coluna (contagem de valores DISTINTOS, nao de linhas) e o dado mais
    proximo que a lib da de graca -- deliberadamente NAO usamos o maior
    Cardinality de uma tabela como proxy de rowCount porque isso e so um
    limite inferior (uma coluna pode ter menos valores distintos que linhas),
    nao um valor exato, e reportar isso como "linhas" enganaria o usuario.

    Retorna:
      {
        "totalSizeBytes": int,
        "tables":  [{"name", "columnCount", "sizeBytes"}, ...],  # desc por sizeBytes
        "columns": [{"table", "name", "cardinality", "sizeBytes",
                     "dictionarySizeBytes", "dataSizeBytes"}, ...],  # desc por sizeBytes
      }
    """
    columns = []
    table_size_totals: dict = {}
    table_column_counts: dict = {}

    for row in stats_records:
        table_name = str(first_value(row, ["TableName"]))
        column_name = str(first_value(row, ["ColumnName"]))
        if not table_name or not column_name:
            continue

        cardinality = row.get("Cardinality") or 0
        dictionary_bytes = row.get("Dictionary") or 0
        hash_index_bytes = row.get("HashIndex") or 0
        data_bytes = row.get("DataSize") or 0
        total_bytes = int(dictionary_bytes) + int(hash_index_bytes) + int(data_bytes)

        columns.append({
            "table": table_name,
            "name": column_name,
            "cardinality": int(cardinality),
            "sizeBytes": total_bytes,
            "dictionarySizeBytes": int(dictionary_bytes),
            "dataSizeBytes": int(data_bytes),
        })
        table_size_totals[table_name] = table_size_totals.get(table_name, 0) + total_bytes
        table_column_counts[table_name] = table_column_counts.get(table_name, 0) + 1

    tables = [
        {
            "name": name,
            "columnCount": table_column_counts[name],
            "sizeBytes": table_size_totals[name],
        }
        for name in sorted(table_size_totals, key=lambda n: table_size_totals[n], reverse=True)
    ]
    columns.sort(key=lambda c: c["sizeBytes"], reverse=True)

    return {
        "totalSizeBytes": int(model_size) if isinstance(model_size, (int, float)) else 0,
        "tables": tables,
        "columns": columns,
    }


def query_search_text(query):
    meta = query.get("meta", {})
    return " ".join([
        str(query.get("label", "")),
        str(meta.get("expression", "")),
        str(meta.get("searchText", "")),
        record_text(meta.get("row", {})),
    ])


def build_query_nodes(power_query, connectors):
    nodes = []
    for index, row in enumerate(power_query):
        name = first_value(row, ["TableName", "Name", "QueryName", "table", "name"]) or f"Power Query {index + 1}"
        expression = first_value(row, ["Expression", "expression", "MExpression"]) or ""
        full_text = record_text(row)
        connection_path = extract_connection_path_from_m(str(expression))
        nodes.append({
            "id": f"query:{slug(name)}",
            "type": "query",
            "label": str(name),
            "icon": "M",
            "meta": {
                "expression": str(expression),
                "searchText": full_text,
                "row": row,
                "connectionPath": connection_path,
            },
        })

    if not nodes and connectors:
        for connector in connectors:
            nodes.append({
                "id": f"query:{slug(connector['label'])}-query",
                "type": "query",
                "label": f"{connector['label']} Query",
                "icon": "M",
                "meta": {"expression": connector["meta"].get("pattern", ""), "connectionPath": ""},
            })

    return nodes


def extract_connection_path_from_m(expression: str) -> str:
    """
    Extracts the connection arguments from the Source = ConnectorFunction(...) step.
    Returns a human-readable string like 'server.database.windows.net › SalesDB'
    or a file path / URL.
    """
    if not expression:
        return ""

    # Connector function patterns (e.g. Sql.Database("server", "db"))
    connector_call = re.search(
        r'(?:Source\s*=\s*)?([A-Za-z][A-Za-z0-9_]*\.[A-Za-z][A-Za-z0-9_]*)\s*\(([^)]{0,600})\)',
        expression
    )
    if connector_call:
        args_str = connector_call.group(2)
        args = re.findall(r'"([^"]{1,300})"', args_str)
        if args:
            return " › ".join(args)

    # SharePoint / web URL
    url_match = re.search(r'https?://[^\s"\']{4,300}', expression)
    if url_match:
        return url_match.group(0)

    # Windows file path
    path_match = re.search(r'[A-Za-z]:[/\\][^"\'<>\r\n]{3,200}', expression)
    if path_match:
        return path_match.group(0)

    # UNC path
    unc_match = re.search(r'\\\\[^"\'<>\r\n]{3,200}', expression)
    if unc_match:
        return unc_match.group(0)

    # First quoted string
    first_quoted = re.search(r'"([^"]{3,200})"', expression)
    if first_quoted:
        return first_quoted.group(1)

    return ""


def build_table_nodes(tables, schema, semantic_tables, query_nodes):
    names = set()
    hidden = set()

    for row in semantic_tables:
        table = first_value(row, ["Name", "TableName", "Table", "name"])
        if not table:
            continue
        is_hidden = str(first_value(row, ["IsHidden", "Hidden", "isHidden"])).lower() in ("true", "1", "yes")
        if is_hidden:
            hidden.add(str(table))
        elif not is_system_table(table):
            names.add(str(table))

    if not names:
        names = {str(table) for table in tables if table and not is_system_table(table)}

    for row in schema:
        table = first_value(row, ["TableName", "Table", "table"])
        if table and table not in hidden and not is_system_table(table):
            names.add(str(table))

    query_names = {node["label"] for node in query_nodes if not is_system_table(node["label"])}
    if query_names:
        names = {name for name in names if name in query_names or not is_system_table(name)}

    if not names:
        names = {node["label"] for node in query_nodes}

    return [{"id": f"model:{slug(name)}", "type": "model", "label": name, "icon": "TBL", "meta": {}} for name in sorted(names)]


def is_system_table(name):
    normalized = str(name).strip().lower()
    return (
        not normalized
        or normalized.startswith("<")
        or normalized.startswith("datetabletemplate")
        or normalized.startswith("localdatetable")
        or normalized.startswith("date table template")
        or normalized.startswith("_")
    )


def build_measure_nodes(measures):
    nodes = []
    for index, row in enumerate(measures):
        name = first_value(row, ["Name", "MeasureName", "Measure", "name"]) or f"Measure {index + 1}"
        table = first_value(row, ["TableName", "Table", "table"])
        expression = first_value(row, ["Expression", "expression"]) or ""
        nodes.append({
            "id": f"measure:{slug(table)}:{slug(name)}" if table else f"measure:{slug(name)}",
            "type": "measure",
            "label": str(name),
            "icon": "DAX",
            "meta": {"table": str(table) if table else "", "expression": str(expression), "row": row},
        })
    return nodes


def build_measure_dependency_edges(measure, measure_nodes, table_nodes):
    edges = []
    expression = measure["meta"].get("expression", "")
    if not expression:
        return edges

    expression_lower = expression.lower()
    for table in table_nodes:
        label = table["label"]
        if f"'{label.lower()}'" in expression_lower or re.search(rf"\b{re.escape(label.lower())}\b\s*\[", expression_lower):
            edges.append(edge(table["id"], measure["id"], "referenced in DAX"))

    for other in measure_nodes:
        if other["id"] == measure["id"]:
            continue
        if f"[{other['label'].lower()}]" in expression_lower:
            edges.append(edge(other["id"], measure["id"], "measure dependency"))

    return edges


def build_calc_column_dependency_edges(calc_col, measure_nodes, table_nodes):
    edges = []
    expression = calc_col["meta"].get("expression", "")
    if not expression:
        return edges
    expression_lower = expression.lower()
    for other in measure_nodes:
        if f"[{other['label'].lower()}]" in expression_lower:
            edges.append(edge(other["id"], calc_col["id"], "referenced in calc column"))
    return edges


def build_calc_column_nodes(raw_columns):
    """Build calc_column nodes from dax_columns records.

    pbixray's dax_columns table contains all model columns; we keep only
    those that have an Expression (i.e. are DAX-calculated columns).

    Power BI stores calculated columns once per user table AND once again
    inside internal hierarchy/date-template tables (LocalDateTable_*,
    DateTableTemplate_*, etc). We deduplicate in two steps:
      1. Skip rows whose TableName is a system/internal table.
      2. Deduplicate by (slug_name, normalised_expression) to catch the same
         column surfaced under different table name spellings that slipped
         past is_system_table.
    """
    nodes = []
    seen_id = set()
    seen_expr_key = set()
    for index, row in enumerate(raw_columns):
        expression = first_value(row, ["Expression", "expression"]) or ""
        if not expression.strip():
            continue  # skip plain (non-calculated) columns
        name = first_value(row, ["Name", "ColumnName", "Column", "name"]) or f"Calc Column {index + 1}"
        table = first_value(row, ["TableName", "Table", "table"]) or ""

        # Skip columns belonging to Power BI internal/system tables
        if is_system_table(table):
            continue

        node_id = f"calc_column:{slug(table)}:{slug(name)}" if table else f"calc_column:{slug(name)}"
        if node_id in seen_id:
            continue
        seen_id.add(node_id)

        # Secondary dedup: same column name + same expression avoids phantom
        # duplicates when pbixray surfaces the column under a non-system table
        # alias with a different name (e.g. auto-date hierarchy sub-tables).
        expr_key = (slug(str(name)), re.sub(r"\s+", " ", str(expression).strip().lower()))
        if expr_key in seen_expr_key:
            continue
        seen_expr_key.add(expr_key)

        nodes.append({
            "id": node_id,
            "type": "calc_column",
            "label": str(name),
            "icon": "CC",
            "meta": {"table": str(table), "expression": str(expression), "row": row},
        })
    return nodes


def extract_pages_from_layout(path: Path):
    """Extract report pages (sections) from the PBIX layout file.

    Returns a list of dicts:
      {
        "name":         str,   # displayName shown in Power BI
        "ordinal":      int,   # page order (0-based)
        "visualCount":  int,   # number of visual containers on the page
        "width":        int,   # canvas width in pixels
        "height":       int,   # canvas height in pixels
      }
    """
    try:
        with zipfile.ZipFile(path) as archive:
            layout_name = next((n for n in archive.namelist() if n.lower() == "report/layout"), "")
            if not layout_name:
                return []
            raw = archive.read(layout_name)
    except Exception:
        logger.warning("extract_pages_from_layout: falha ao ler Report/Layout de %s", path.name, exc_info=True)
        return []

    text = raw.decode("utf-16le", errors="ignore")
    if text.count("{") < 5:
        text = raw.decode("utf-8", errors="ignore")

    try:
        layout = json.loads(text)
    except Exception:
        logger.warning("extract_pages_from_layout: JSON invalido em Report/Layout de %s", path.name, exc_info=True)
        return []

    pages = []
    for section in layout.get("sections", []):
        display_name = section.get("displayName") or section.get("name") or f"Page {len(pages) + 1}"
        ordinal      = int(section.get("ordinal", len(pages)))
        containers   = section.get("visualContainers", [])
        visual_count = len(containers)
        width        = int(section.get("width",  1280))
        height       = int(section.get("height",  720))
        pages.append({
            "name":        str(display_name),
            "ordinal":     ordinal,
            "visualCount": visual_count,
            "width":       width,
            "height":      height,
        })

    pages.sort(key=lambda p: p["ordinal"])
    return pages


def extract_visuals_from_layout(path: Path):
    try:
        with zipfile.ZipFile(path) as archive:
            layout_name = next((name for name in archive.namelist() if name.lower() == "report/layout"), "")
            if not layout_name:
                return []
            raw = archive.read(layout_name)
    except Exception:
        logger.warning("extract_visuals_from_layout: falha ao ler Report/Layout de %s", path.name, exc_info=True)
        return []

    text = raw.decode("utf-16le", errors="ignore")
    if text.count("{") < 5:
        text = raw.decode("utf-8", errors="ignore")

    visuals = []
    try:
        layout = json.loads(text)
        for section in layout.get("sections", []):
            for index, container in enumerate(section.get("visualContainers", [])):
                config = parse_json_string(container.get("config"))
                query = parse_json_string(container.get("query"))
                visual_type = nested_value(config, ["singleVisual", "visualType"]) or "Visual"
                title = visual_title(config) or f"{titleize(visual_type)} {index + 1}"

                # G14: prioridade e SEMPRE a navegacao estrutural real da
                # arvore (Select/projections dentro de prototypeQuery/query) --
                # o regex (extract_query_refs) so entra como fallback quando
                # a navegacao nao acha nada, o que acontece em custom visuals
                # de terceiros ou schemas fora do padrao. Ver
                # extract_structural_refs() para o que esta coberto.
                structural_refs = extract_structural_refs(config, query)
                if structural_refs:
                    refs = sorted(structural_refs)
                    ref_source = "structural"
                else:
                    refs = sorted(extract_query_refs(config) | extract_query_refs(query))
                    ref_source = "heuristic"

                visuals.append({
                    "name": title,
                    "type": titleize(visual_type),
                    "refs": refs,
                    "refSource": ref_source,
                })
    except Exception:
        # JSON malformado -- cai para o fallback por regex logo abaixo, que
        # ainda funciona sobre o texto cru; ainda assim persistimos o motivo
        # da falha do caminho estruturado para diagnostico futuro. Sem a
        # arvore JSON parseada nao ha o que navegar, entao todo visual
        # reconstruido aqui e necessariamente "heuristic".
        logger.info("extract_visuals_from_layout: JSON invalido em Report/Layout de %s, usando fallback por regex", path.name, exc_info=True)
        for index, match in enumerate(re.finditer(r'"visualType"\s*:\s*"([^"]+)"', text)):
            visual_type = titleize(match.group(1))
            start = max(0, match.start() - 3000)
            end = min(len(text), match.end() + 3000)
            refs = sorted(extract_refs_from_text(text[start:end]))
            visuals.append({"name": f"{visual_type} {index + 1}", "type": visual_type, "refs": refs, "refSource": "heuristic"})

    deduped = {}
    for visual in visuals:
        key = visual["name"]
        if key in deduped:
            deduped[key]["refs"] = sorted(set(deduped[key]["refs"]) | set(visual["refs"]))
            # Colisao de titulo entre dois containers: se qualquer um dos
            # dois trouxe refs estruturais, a uniao mesclada conta como
            # estrutural (ha pelo menos uma aresta real por tras, mesmo que
            # o outro container tenha caido no fallback).
            if "structural" in (deduped[key]["refSource"], visual["refSource"]):
                deduped[key]["refSource"] = "structural"
        else:
            deduped[key] = visual
    return list(deduped.values())[:24]


def build_visual_nodes(visuals):
    return [
        {
            "id": f"visual:{slug(visual['name'])}",
            "type": "visual",
            "label": visual["name"],
            "icon": "VIS",
            "meta": {
                "visualType": visual.get("type", ""),
                "refs": visual.get("refs", []),
                # G14: de onde veio o conjunto de refs deste visual --
                # "structural" (navegacao real de Select/projections) ou
                # "heuristic" (fallback por regex). Ver extract_visuals_from_layout.
                "refSource": visual.get("refSource", "heuristic"),
            },
        }
        for visual in visuals
    ]


def build_visual_edges(visual_nodes, measure_nodes, table_nodes, calc_column_nodes=None):
    edges = []
    measures_by_label = {node["label"].lower(): node for node in measure_nodes}
    tables_by_label = {node["label"].lower(): node for node in table_nodes}

    # Index calc columns by bare name AND by "table.columnname" composite so that
    # refs extracted from the layout (which often appear as "Entity"/"Property" pairs
    # or as a dotted "queryRef") can match either way.
    calc_cols_by_label = {}
    calc_cols_by_composite = {}
    for node in (calc_column_nodes or []):
        bare = node["label"].lower()
        calc_cols_by_label[bare] = node
        table = node["meta"].get("table", "")
        if table:
            composite = f"{table.lower()}.{bare}"
            calc_cols_by_composite[composite] = node

    for visual in visual_nodes:
        refs = {str(ref).lower() for ref in visual["meta"].get("refs", [])}
        matched = False

        # G14: toda aresta gerada a partir do conjunto de refs deste visual
        # herda a mesma origem ("structural"/"heuristic") que o visual
        # inteiro recebeu em extract_visuals_from_layout -- da ao usuario um
        # sinal de confianca por aresta (visivel em edge.meta se/quando o
        # frontend passar a consumir isso), nao so um aviso global no rodape.
        link_type = visual["meta"].get("refSource", "heuristic")
        link_extra = {"linkType": link_type}

        for label, measure in measures_by_label.items():
            if label in refs:
                edges.append(edge(measure["id"], visual["id"], "used in visual", link_extra))
                matched = True

        for label, calc_col in calc_cols_by_label.items():
            if label in refs:
                edges.append(edge(calc_col["id"], visual["id"], "used in visual", link_extra))
                matched = True

        # Secondary pass: try composite "table.column" match for calc columns that
        # weren't caught by the bare name (e.g. when the layout stores them as
        # "Entity":"Sales","Property":"YTD Category" and the ref set contains
        # "sales.ytd category" after joining).
        for composite, calc_col in calc_cols_by_composite.items():
            if composite in refs and calc_col["id"] not in {e["from"] for e in edges if e["to"] == visual["id"]}:
                edges.append(edge(calc_col["id"], visual["id"], "used in visual", link_extra))
                matched = True

        for label, table in tables_by_label.items():
            if label in refs:
                edges.append(edge(table["id"], visual["id"], "used in visual", link_extra))
                matched = True

        # Ultimo recurso (um unico measure/table no modelo inteiro -- nao
        # existe ambiguidade a resolver): nunca vem de refs navegadas, entao
        # e sempre "heuristic" independente do refSource do visual.
        if not matched and len(measure_nodes) == 1:
            edges.append(edge(measure_nodes[0]["id"], visual["id"], "used in visual", {"linkType": "heuristic"}))
        elif not matched and not measure_nodes and len(table_nodes) == 1:
            edges.append(edge(table_nodes[0]["id"], visual["id"], "used in visual", {"linkType": "heuristic"}))

    return edges


def parse_json_string(value):
    if isinstance(value, dict):
        return value
    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        return json.loads(value)
    except Exception:
        logger.debug("parse_json_string: JSON invalido (%d chars)", len(value), exc_info=True)
        return {}


def get_path(data, path):
    """Navega um dict aninhado por uma sequencia de chaves, devolvendo None
    assim que algum passo nao bate (chave ausente ou valor no meio do
    caminho que nao e mais um dict). Generico o bastante para servir tanto
    `nested_value` (que so quer uma string) quanto a navegacao estrutural de
    Select/projections em `extract_structural_refs` (G14), que precisa do
    dict/lista inteiro em cada nivel, nao so de folhas string."""
    current = data
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def nested_value(data, path):
    value = get_path(data, path)
    return value if isinstance(value, str) else ""


def visual_title(config):
    text = json.dumps(config, ensure_ascii=False)
    match = re.search(r'"titleText"\s*:\s*"([^"]+)"', text)
    return match.group(1) if match else ""


def extract_query_refs(value):
    text = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
    return extract_refs_from_text(text)


_SELECT_ENTITY_MAX_DEPTH = 50  # ver docstring: PBIX malicioso podia forcar RecursionError


def _resolve_select_entity(expression, aliases, _depth=0):
    """Acha a entidade (tabela) por tras de uma Expression de um Select item,
    resolvendo o alias de SourceRef ("Source": "x" -> procurar "x" em
    From[].Name/Entity) quando a Entity nao vem direto em SourceRef.Entity.

    Hierarquias de data (drill-down Ano/Trimestre/Mes) aninham a SourceRef
    real mais fundo (Hierarchy.Expression.PropertyVariationSource.Expression...) --
    melhor esforco: desce recursivamente por qualquer sub-dict ate achar a
    primeira SourceRef resolvivel.

    _depth trava em _SELECT_ENTITY_MAX_DEPTH: o JSON de layout vem do .pbix
    do usuario (nao confiavel), e uma Expression aninhada de proposito (ex.
    ~1500 niveis) derrubava isso com RecursionError, que o except amplo de
    extract_visuals_from_layout engolia para o loop de visuais INTEIRO --
    limite explicito troca "descoberta best-effort de hierarquia legitima"
    (poucos niveis reais) por resiliencia a entrada adversarial, sem crashar."""
    if _depth > _SELECT_ENTITY_MAX_DEPTH or not isinstance(expression, dict):
        return ""
    source_ref = expression.get("SourceRef")
    if isinstance(source_ref, dict):
        if source_ref.get("Entity"):
            return str(source_ref["Entity"])
        alias = source_ref.get("Source")
        if alias and alias in aliases:
            return aliases[alias]
    for value in expression.values():
        if isinstance(value, dict):
            found = _resolve_select_entity(value, aliases, _depth + 1)
            if found:
                return found
    return ""


def _select_field_ref(node, aliases):
    """Le um sub-objeto tipado de um Select item (Column ou Measure) e
    devolve (entidade, propriedade) -- vazio quando o node nao e o shape
    esperado (ex.: Select item de outro tipo)."""
    if not isinstance(node, dict):
        return "", ""
    entity = _resolve_select_entity(node.get("Expression"), aliases)
    prop = node.get("Property")
    return entity, (str(prop) if prop not in (None, "") else "")


def _add_structural_ref(refs, entity, prop):
    if not prop:
        return
    bare = str(prop).strip().lower()
    if not bare:
        return
    refs.add(bare)
    if entity:
        refs.add(f"{str(entity).strip().lower()}.{bare}")


def _collect_select_refs(query_root, refs):
    """Percorre um objeto de query no shape do Power BI (From[]/Select[]) --
    tanto `config.singleVisual.prototypeQuery` quanto
    `query.Commands[].SemanticQueryDataShapeCommand.Query` usam este mesmo
    shape -- e acumula os campos referenciados em `refs` (set, lowercase).

    Cobre os quatro tipos de Select item que aparecem nos visuais mais
    comuns (tabela, cartao, barra/coluna, linha, pizza/rosca):
      - Column: campo bruto de uma tabela.
      - Measure: medida DAX.
      - Aggregation: agregacao automatica sobre Column/Measure (ex.: Power BI
        soma uma coluna numerica solta por padrao quando ela cai num "Values").
      - HierarchyLevel: nivel de uma hierarquia (tipicamente a hierarquia de
        data automatica -- Ano/Trimestre/Mes/Dia).
    """
    if not isinstance(query_root, dict):
        return

    aliases = {}
    for source in (query_root.get("From") or []):
        if isinstance(source, dict) and source.get("Name") and source.get("Entity"):
            aliases[source["Name"]] = str(source["Entity"])

    for item in (query_root.get("Select") or []):
        if not isinstance(item, dict):
            continue

        # "Name" ja vem qualificado pelo proprio Power BI (ex.: "Sales.OrderDate",
        # "Sum(Sales.Amount)") -- usamos tanto o valor inteiro quanto as partes
        # separadas por ./[]/() para casar tanto refs compostas quanto bare.
        name = item.get("Name")
        if isinstance(name, str) and name.strip():
            refs.add(name.strip().lower())
            for part in re.split(r"[.\[\]()]+", name):
                clean = part.strip("'\" ")
                if clean:
                    refs.add(clean.lower())

        entity, prop = _select_field_ref(item.get("Column"), aliases)
        _add_structural_ref(refs, entity, prop)

        entity, prop = _select_field_ref(item.get("Measure"), aliases)
        _add_structural_ref(refs, entity, prop)

        aggregation = item.get("Aggregation")
        if isinstance(aggregation, dict):
            inner = aggregation.get("Expression") or {}
            entity, prop = _select_field_ref(inner.get("Column"), aliases)
            _add_structural_ref(refs, entity, prop)
            entity, prop = _select_field_ref(inner.get("Measure"), aliases)
            _add_structural_ref(refs, entity, prop)

        hierarchy_level = item.get("HierarchyLevel")
        if isinstance(hierarchy_level, dict):
            level = hierarchy_level.get("Level")
            variation = get_path(
                hierarchy_level,
                ["Expression", "Hierarchy", "Expression", "PropertyVariationSource"],
            )
            if isinstance(variation, dict):
                entity = _resolve_select_entity(variation.get("Expression"), aliases)
                _add_structural_ref(refs, entity, variation.get("Property"))
            if level:
                refs.add(str(level).strip().lower())


def extract_structural_refs(config, query):
    """G14: navega a arvore JSON REAL do layout do visual em vez de aplicar
    regex sobre o texto bruto do container inteiro (que tambem casa
    substrings de formatacao condicional, filtros, ou qualquer outro trecho
    do JSON que tenha uma chave "Property"/"Name" sem relacao com os campos
    de fato exibidos no visual -- falsos positivos -- e pode nao capturar um
    campo que aparece num formato ligeiramente diferente do esperado pelo
    regex -- falsos negativos).

    Fontes estruturais navegadas (schema padrao do Power BI Desktop, valido
    para os tipos de visual mais comuns -- tabela, matriz, cartao,
    barra/coluna, linha, pizza/rosca -- que compartilham o mesmo shape de
    query):
      - config.singleVisual.prototypeQuery.Select[]: definicao tipada de
        cada campo do visual (ver `_collect_select_refs`).
      - query.Commands[].SemanticQueryDataShapeCommand.Query.Select[]: mesmo
        shape, na query "executavel" anexada ao container -- as vezes
        presente quando prototypeQuery falta, ou com itens adicionais
        (ex.: campos usados so para ordenacao).
      - config.singleVisual.projections{papel: [...]}[].queryRef: os papeis
        visuais (eixo, legenda, valores) referenciam os Select acima pelo
        nome qualificado -- reforco extra, mesmo shape de matching.

    Visuais que fogem desse schema (custom visuals de terceiros com schema
    proprio -- ex. visual R/Python -- ou paginas exportadas por versoes
    antigas do Power BI Desktop que nao usam prototypeQuery) simplesmente
    nao produzem nada aqui: devolvem um set vazio, e quem chama
    (`extract_visuals_from_layout`) cai para o fallback heuristico por regex.
    """
    refs = set()
    if not isinstance(config, dict):
        config = {}
    if not isinstance(query, dict):
        query = {}

    single_visual = config.get("singleVisual")
    if isinstance(single_visual, dict):
        prototype_query = single_visual.get("prototypeQuery")
        if isinstance(prototype_query, str):
            prototype_query = parse_json_string(prototype_query)
        if isinstance(prototype_query, dict):
            _collect_select_refs(prototype_query, refs)

        projections = single_visual.get("projections")
        if isinstance(projections, dict):
            for role_items in projections.values():
                for item in (role_items or []):
                    query_ref = item.get("queryRef") if isinstance(item, dict) else None
                    if isinstance(query_ref, str) and query_ref.strip():
                        refs.add(query_ref.strip().lower())
                        for part in re.split(r"[.\[\]()]+", query_ref):
                            clean = part.strip("'\" ")
                            if clean:
                                refs.add(clean.lower())

    for command in (query.get("Commands") or []):
        if not isinstance(command, dict):
            continue
        shape_query = get_path(command, ["SemanticQueryDataShapeCommand", "Query"])
        if isinstance(shape_query, dict):
            _collect_select_refs(shape_query, refs)

    return refs


def extract_refs_from_text(text):
    """G14 FALLBACK HEURISTICO -- so e chamado quando `extract_structural_refs`
    (navegacao real da arvore Select/projections) nao encontrou nada para o
    visual, ou quando o proprio Report/Layout nao parseia como JSON valido.
    Casa qualquer ocorrencia solta dessas chaves em QUALQUER LUGAR do texto
    (nao so dentro de um Select) -- por isso e mais propenso a falso positivo
    (casa uma "Property" de formatacao condicional/filtro sem relacao com o
    campo exibido) e falso negativo (formato levemente diferente do regex)
    do que a navegacao estrutural. Mantido apenas como rede de seguranca
    para custom visuals de terceiros e layouts fora do schema padrao."""
    refs = set()
    for pattern in [
        r'"queryRef"\s*:\s*"([^"]+)"',
        r'"Entity"\s*:\s*"([^"]+)"',
        r'"Property"\s*:\s*"([^"]+)"',
        r'"Measure"\s*:\s*"([^"]+)"',
        r'"Column"\s*:\s*"([^"]+)"',
        r'"Name"\s*:\s*"([^"]+)"',
    ]:
        for match in re.finditer(pattern, text):
            value = match.group(1)
            # Keep the full dotted path (e.g. "Sales.YTD Category") so that
            # build_visual_edges can attempt a "table.column" composite match.
            refs.add(value.lower())
            # Also split into individual parts so bare column/measure names match too.
            for part in re.split(r"[.\[\]]+", value):
                clean = part.strip("'\" ")
                if clean:
                    refs.add(clean.lower())
    return refs
