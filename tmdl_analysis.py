"""G17 (metade backend): caminho PARALELO de analise para pastas .pbip/TMDL,
sem depender de pbixray nem de um arquivo .pbix binario -- parseia os
`*.tmdl` (texto plano indentado) direto.

Escopo desta rodada (deliberadamente limitado -- ver BACKLOG.md G17):
tabelas, colunas (incluindo colunas calculadas), medidas (DAX),
relacionamentos, expressoes M de Power Query (de dentro de `partition`/
`source` de cada tabela e de `expressions.tmdl` se existir) e papeis RLS
basicos (`role`/`tablePermission`) -- o essencial para reconstruir o MESMO
grafo de linhagem que /api/analyze ja produz.

FORA de escopo (documentado, nao forcado): linhagem visual<->campo
(paginas/visuais do `.Report/`, formato PBIR -- outro formato inteiro,
nao-trivial, nao reaproveitavel do parser de layout do .pbix). `pages` e os
nos tipo "visual" ficam vazios; `unusedObjects` tambem fica vazio (o
algoritmo de build_unused_objects em pbix_analysis.py parte de nos "visual"
-- sem eles, TUDO apareceria como "nao usado", o que seria enganoso, nao
apenas incompleto -- ver nota em analyze_tmdl_files()).

Reaproveita ao maximo os build_*/extract_* de pbix_analysis.py: este modulo
so PRODUZ registros no MESMO shape de dict que records_from()/list_from()
normalmente extraem do pbixray (ver build_table_nodes/build_measure_nodes/
build_calc_column_nodes/build_query_nodes/build_structured_security em
pbix_analysis.py), sem duplicar nenhuma logica de grafo.

Nota de seguranca (mesma familia de risco documentada em pbix_analysis.py):
o conteudo dos `.tmdl` vem de um upload do usuario, tratado como entrada
adversarial. `_build_tree()` e ITERATIVO (pilha explicita), nao recursivo --
sem o RecursionError que ja mordeu a extracao de layout do .pbix (G14). Os
arquivos nunca sao escritos em disco (tudo em memoria, como bytes/str) --
sem superficie de path traversal a partir do `filename` do multipart, que
aqui so vira texto de exibicao (ver bi_server.py: `derive_tmdl_model_name`).
Tamanho total do upload continua limitado por MAX_UPLOAD_BYTES em
bi_server.py, aplicado uniformemente a qualquer POST antes deste modulo ver
um unico byte.
"""
from __future__ import annotations

from logging_setup import logger


class TmdlAnalysisError(Exception):
    """Erro de negocio (nao um crash): a pasta enviada nao parece um
    .pbip/SemanticModel valido, ou nenhum .tmdl reconhecivel foi encontrado.
    bi_server.py converte isso em HTTP 400 com mensagem clara, em vez do 500
    generico usado para falhas inesperadas."""


# ── Camada 1: tokenizacao TMDL (indentacao + blocos de crase tripla) ───────

def _decode_tmdl(content) -> str:
    if isinstance(content, str):
        return content
    for encoding in ("utf-8-sig", "utf-8"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="replace")


def _dedent_block(lines: list[str]) -> str:
    content_lines = [line for line in lines if line.strip()]
    if not content_lines:
        return ""
    min_indent = min(len(line) - len(line.lstrip(" ")) for line in content_lines)
    dedented = [line[min_indent:] if len(line) >= min_indent else line.lstrip(" ") for line in lines]
    return "\n".join(dedented).strip("\n")


def _preprocess_lines(text: str) -> list[tuple[int, str]]:
    """Converte o texto de um .tmdl numa lista de (indent, content):
    - remove linhas em branco e comentarios `///`;
    - funde blocos delimitados por crase tripla (tres caracteres ` seguidos)
      numa UNICA entrada multi-linha, no indent da linha que abriu o bloco --
      assim uma expressao M/DAX multi-linha vira um valor de texto opaco,
      nunca "estrutura TMDL" a ser tokenizada de novo.
    """
    raw_lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    entries: list[tuple[int, str]] = []
    i = 0
    n = len(raw_lines)
    while i < n:
        expanded = raw_lines[i].expandtabs(4)
        stripped = expanded.strip()
        if not stripped:
            i += 1
            continue
        if stripped.startswith("///"):
            i += 1
            continue
        indent = len(expanded) - len(expanded.lstrip(" "))
        if stripped.endswith("```"):
            prefix = stripped[:-3].rstrip()
            block_lines: list[str] = []
            i += 1
            while i < n:
                block_raw = raw_lines[i].expandtabs(4)
                if block_raw.strip() == "```":
                    i += 1
                    break
                block_lines.append(block_raw)
                i += 1
            block_text = _dedent_block(block_lines)
            content = f"{prefix} {block_text}" if prefix else block_text
            entries.append((indent, content))
            continue
        entries.append((indent, stripped))
        i += 1
    return entries


def _build_tree(entries: list[tuple[int, str]]) -> list[dict]:
    """Constroi a arvore de blocos a partir de (indent, content) -- ITERATIVO
    (pilha explicita), nunca recursivo: o texto vem de um .tmdl enviado pelo
    usuario (nao confiavel), e um arquivo com milhares de niveis de
    indentacao adversariais nao pode derrubar isso com RecursionError (mesma
    licao do G14, ver docstring do modulo)."""
    root_children: list[dict] = []
    stack: list[tuple[int, list[dict]]] = [(-1, root_children)]
    for indent, content in entries:
        node = {"text": content, "children": []}
        while stack[-1][0] >= indent:
            stack.pop()
        stack[-1][1].append(node)
        stack.append((indent, node["children"]))
    return root_children


# ── Camada 2: leitura de declaracoes/propriedades de uma linha TMDL ────────

def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == "'" and value[-1] == "'":
        return value[1:-1].replace("\\'", "'")
    return value


def _first_token(text: str) -> str:
    text = text.strip()
    return text.split(None, 1)[0] if text else ""


def _parse_declaration(text: str) -> tuple[str, str, str]:
    """Le uma linha do tipo "table 'Nome'", "column Nome",
    "measure 'Nome' = <expr>", "relationship guid", "role 'Nome'". Devolve
    (keyword, nome, valor) -- valor e '' quando nao ha '=' na linha."""
    text = text.strip()
    eq_index = text.find("=")
    if eq_index != -1:
        head = text[:eq_index].strip()
        value = text[eq_index + 1:].strip()
    else:
        head = text
        value = ""
    parts = head.split(None, 1)
    keyword = parts[0] if parts else ""
    name = _strip_quotes(parts[1]) if len(parts) > 1 else ""
    return keyword, name, value


def _parse_property_line(text: str) -> tuple[str, str | None]:
    """Le uma linha de propriedade simples ("dataType: int64",
    "expression = <DAX>", "isHidden"). Devolve (chave, valor) -- valor e
    None para uma flag booleana sem separador (ex.: "isHidden" sozinho)."""
    text = text.strip()
    colon_idx = text.find(":")
    eq_idx = text.find("=")
    if eq_idx != -1 and (colon_idx == -1 or eq_idx < colon_idx):
        return text[:eq_idx].strip(), text[eq_idx + 1:].strip()
    if colon_idx != -1:
        return text[:colon_idx].strip(), text[colon_idx + 1:].strip()
    return text, None


def _is_truthy_flag(value: str | None) -> bool:
    if value is None:
        return True
    return str(value).strip().lower() not in ("false", "0", "no")


# ── Camada 3: extracao por tipo de bloco de topo ────────────────────────────

_TABLE_CHILD_SKIP = {"annotation", "changedProperty", "hierarchy", "level"}


def _extract_column(node: dict, name: str, decl_value: str) -> dict:
    expression = decl_value or ""
    for child in node["children"]:
        if _first_token(child["text"]) in _TABLE_CHILD_SKIP:
            continue
        key, value = _parse_property_line(child["text"])
        if key.lower() == "expression" and value:
            expression = value
    return {"name": name, "expression": expression}


def _extract_measure(name: str, decl_value: str) -> dict:
    # A expressao DAX de uma medida sempre vem na propria linha de
    # declaracao (single-line ou bloco de crase tripla, ja mesclado por
    # _preprocess_lines) -- filhos como formatString/displayFolder/
    # annotation nao importam para o grafo de linhagem.
    return {"name": name, "expression": decl_value or ""}


def _extract_partition(node: dict) -> str:
    source = ""
    for child in node["children"]:
        if _first_token(child["text"]) in _TABLE_CHILD_SKIP:
            continue
        key, value = _parse_property_line(child["text"])
        if key.lower() == "source" and value:
            source = value
    return source


def _extract_table(node: dict) -> dict:
    _, name, _ = _parse_declaration(node["text"])
    columns: list[dict] = []
    measures: list[dict] = []
    partition_sources: list[str] = []
    is_hidden = False

    for child in node["children"]:
        first = _first_token(child["text"])
        if first == "column":
            _, cname, cvalue = _parse_declaration(child["text"])
            columns.append(_extract_column(child, cname, cvalue))
        elif first == "measure":
            _, cname, cvalue = _parse_declaration(child["text"])
            measures.append(_extract_measure(cname, cvalue))
        elif first == "partition":
            partition_sources.append(_extract_partition(child))
        elif first in _TABLE_CHILD_SKIP:
            continue
        else:
            key, value = _parse_property_line(child["text"])
            if key.lower() == "ishidden":
                is_hidden = _is_truthy_flag(value)

    return {
        "name": name,
        "columns": columns,
        "measures": measures,
        "partitionSources": [source for source in partition_sources if source],
        "isHidden": is_hidden,
    }


def _split_table_column(value: str) -> tuple[str, str]:
    value = (value or "").strip()
    if not value:
        return "", ""
    table, sep, column = value.rpartition(".")
    if not sep:
        return "", _strip_quotes(value)
    return _strip_quotes(table), _strip_quotes(column)


def _extract_relationship(node: dict) -> dict:
    _, name, _ = _parse_declaration(node["text"])
    props: dict[str, str] = {}
    for child in node["children"]:
        key, value = _parse_property_line(child["text"])
        if value is not None:
            props[key.lower()] = value
    return {"name": name, "props": props}


def _relationship_to_record(rel: dict) -> dict:
    props = rel["props"]
    from_table, from_col = _split_table_column(props.get("fromcolumn", ""))
    to_table, to_col = _split_table_column(props.get("tocolumn", ""))
    is_active = _is_truthy_flag(props.get("isactive"))
    return {
        "FromTableName": from_table,
        "FromColumnName": from_col,
        "ToTableName": to_table,
        "ToColumnName": to_col,
        "Cardinality": props.get("cardinality", "") or props.get("tocardinality", ""),
        "IsActive": is_active,
        "CrossFilteringBehavior": props.get("crossfilteringbehavior", ""),
    }


def _extract_role(node: dict) -> dict:
    _, name, _ = _parse_declaration(node["text"])
    row_filters = []
    for child in node["children"]:
        if _first_token(child["text"]) == "tablePermission":
            _, table_name, expression = _parse_declaration(child["text"])
            row_filters.append({"table": table_name, "expression": expression})
    return {"name": name, "rowFilters": row_filters}


def _role_to_rls_records(role: dict) -> list[dict]:
    return [
        {
            "RoleName": role["name"],
            "TableName": row_filter["table"],
            "FilterExpression": row_filter["expression"],
            "State": "",
        }
        for row_filter in role["rowFilters"]
    ]


# ── Camada 4: parse_tmdl_model -- normaliza para os shapes ja consumidos
#    pelos build_*/records_from de pbix_analysis.py ─────────────────────────

def parse_tmdl_model(files) -> dict:
    """files: iteravel de (caminho_relativo, bytes|str) -- todos os .tmdl
    relevantes de uma pasta .pbip/.SemanticModel. Devolve um dict com os
    registros nos MESMOS shapes que `records_from`/`list_from` (ver
    pbix_analysis.py) extrairiam do pbixray, prontos para os build_*
    existentes -- nenhuma logica de grafo nova aqui, so normalizacao.

    Falha de parsing de UM arquivo (JSON/TMDL invalido, encoding
    inesperado) e isolada por arquivo -- registrada em "parse_errors" e
    pulada, nunca derruba a analise inteira (mesma postura defensiva do
    resto do pipeline diante de entrada adversarial do usuario).
    """
    table_blocks: list[dict] = []
    relationship_blocks: list[dict] = []
    role_blocks: list[dict] = []
    power_query_records: list[dict] = []
    parse_errors: list[str] = []

    for rel_path, content in files:
        try:
            text = _decode_tmdl(content)
            top_nodes = _build_tree(_preprocess_lines(text))
        except Exception as error:  # noqa: BLE001 - entrada adversarial, nunca deve derrubar a analise inteira
            parse_errors.append(f"{rel_path}: falha ao parsear ({error})")
            logger.warning("parse_tmdl_model: falha ao parsear %s", rel_path, exc_info=True)
            continue

        for node in top_nodes:
            first = _first_token(node["text"])
            if first == "table":
                table_blocks.append(_extract_table(node))
            elif first == "relationship":
                relationship_blocks.append(_extract_relationship(node))
            elif first == "role":
                role_blocks.append(_extract_role(node))
            elif first == "expression":
                _, expr_name, expr_value = _parse_declaration(node["text"])
                if expr_value:
                    power_query_records.append({"TableName": expr_name, "Expression": expr_value})
            # demais nos de topo (model, database, culture, ref, annotation...)
            # ignorados de proposito -- fora do escopo desta rodada.

    table_names: list[str] = []
    semantic_table_records: list[dict] = []
    measure_records: list[dict] = []
    calc_column_records: list[dict] = []

    for table in table_blocks:
        name = table["name"]
        if not name:
            continue
        table_names.append(name)
        semantic_table_records.append({"Name": name, "IsHidden": table["isHidden"]})

        for source in table["partitionSources"]:
            power_query_records.append({"TableName": name, "Expression": source})

        for column in table["columns"]:
            if column["expression"]:
                calc_column_records.append({
                    "TableName": name,
                    "Name": column["name"],
                    "Expression": column["expression"],
                })

        for measure in table["measures"]:
            if measure["name"]:
                measure_records.append({
                    "TableName": name,
                    "Name": measure["name"],
                    "Expression": measure["expression"],
                })

    relationship_records = []
    for rel in relationship_blocks:
        record = _relationship_to_record(rel)
        if record["FromTableName"] and record["ToTableName"]:
            relationship_records.append(record)

    rls_records: list[dict] = []
    for role in role_blocks:
        rls_records.extend(_role_to_rls_records(role))

    return {
        "tables": table_names,
        "schema": [],
        "semantic_tables": semantic_table_records,
        "measures": measure_records,
        "calc_columns": calc_column_records,
        "relationships": relationship_records,
        "power_query": power_query_records,
        "rls_records": rls_records,
        "ols_records": [],
        "parse_errors": parse_errors,
    }


# ── Camada 5: analyze_tmdl_files -- MESMO shape de retorno de analyze_pbix ─

def analyze_tmdl_files(files, model_name: str = "Modelo TMDL") -> dict:
    """G17: caminho paralelo a `pbix_analysis.analyze_pbix()` para pastas
    .pbip/TMDL -- MESMO shape de retorno (nodes/edges/warnings/
    relationships/pages/unusedObjects/securityRoles/diagnostics), consumido
    pelo mesmo `/api/analyze*` -> frontend sem distincao de formato.

    `files`: lista de (caminho_relativo, bytes) -- so os *.tmdl relevantes,
    ja filtrados por `bi_server.Handler.read_tmdl_uploads()`.

    Levanta TmdlAnalysisError (-> HTTP 400 claro em bi_server.py) quando
    nada de reconhecivel foi encontrado -- sinal de que a pasta enviada nao
    e um .pbip/SemanticModel valido, em vez de devolver silenciosamente um
    grafo vazio.
    """
    # Import local dos build_*/helpers -- nao ha ciclo real aqui (nem
    # pbix_analysis.py nem connector_matching.py/graph_utils.py importam
    # tmdl_analysis.py), entao isso e so para manter o custo de import deste
    # modulo minimo ate o momento em que a analise TMDL e de fato pedida
    # (mesma logica de cold-start rapido do .exe que motiva os load_*()
    # lazy em render_graphics.py/doc_export.py).
    from connector_matching import detect_connector_nodes, source_matches_query
    from graph_utils import edge, slug, unique_by_id, unique_edges
    from pbix_analysis import (
        build_calc_column_dependency_edges,
        build_calc_column_nodes,
        build_measure_dependency_edges,
        build_measure_nodes,
        build_query_nodes,
        build_structured_relationships,
        build_structured_security,
        build_table_nodes,
        query_search_text,
    )

    parsed = parse_tmdl_model(files)
    diagnostics = list(parsed["parse_errors"])

    has_content = any([
        parsed["tables"],
        parsed["measures"],
        parsed["calc_columns"],
        parsed["relationships"],
        parsed["power_query"],
        parsed["rls_records"],
    ])
    if not has_content:
        raise TmdlAnalysisError(
            "Nao foi possivel reconhecer nenhuma tabela, medida ou relacionamento TMDL "
            "nos arquivos enviados. Confirme que selecionou a pasta "
            "<Nome>.SemanticModel/definition (ou a raiz do .pbip)."
        )

    power_query = parsed["power_query"]
    connector_nodes = detect_connector_nodes(power_query, [])
    query_nodes = build_query_nodes(power_query, connector_nodes)
    table_nodes = build_table_nodes(parsed["tables"], parsed["schema"], parsed["semantic_tables"], query_nodes)
    measure_nodes = build_measure_nodes(parsed["measures"])
    calc_column_nodes = build_calc_column_nodes(parsed["calc_columns"])

    nodes = unique_by_id(connector_nodes + query_nodes + table_nodes + measure_nodes + calc_column_nodes)
    edges = []
    valid_node_ids = {node["id"] for node in nodes}

    for query in query_nodes:
        query_text = query_search_text(query)
        matched_sources = [source for source in connector_nodes if source_matches_query(source, query_text)]
        if not matched_sources and len(connector_nodes) == 1:
            matched_sources = connector_nodes
        for source in matched_sources:
            edges.append(edge(source["id"], query["id"], "uses connector"))

    table_by_label = {node["label"].lower(): node for node in table_nodes}
    for query in query_nodes:
        table = table_by_label.get(query["label"].lower())
        if table:
            edges.append(edge(query["id"], table["id"], "loads table"))

    for measure in measure_nodes:
        table_name = measure["meta"].get("table")
        if table_name and f"model:{slug(table_name)}" in valid_node_ids:
            edges.append(edge(f"model:{slug(table_name)}", measure["id"], "defines measure"))
        edges.extend(build_measure_dependency_edges(measure, measure_nodes, table_nodes))

    for calc_col in calc_column_nodes:
        table_name = calc_col["meta"].get("table")
        if table_name and f"model:{slug(table_name)}" in valid_node_ids:
            edges.append(edge(f"model:{slug(table_name)}", calc_col["id"], "defines calc column"))
        edges.extend(build_calc_column_dependency_edges(calc_col, measure_nodes, table_nodes))

    if not nodes:
        nodes.append({
            "id": "file:tmdl",
            "type": "source",
            "label": model_name,
            "icon": "TMDL",
            "meta": {"expression": "\n".join(diagnostics) or "Nenhum metadado TMDL reconhecido."},
        })

    diagnostics.append(f"Tabelas TMDL: {len(table_nodes)}")
    diagnostics.append(f"Medidas: {len(measure_nodes)}")
    diagnostics.append(f"Colunas calculadas: {len(calc_column_nodes)}")
    diagnostics.append(f"Consultas Power Query (M): {len(query_nodes)}")
    diagnostics.append(f"Relacionamentos: {len(parsed['relationships'])}")

    structured_rels = build_structured_relationships(parsed["relationships"])
    deduped_edges = unique_edges(edges)

    security_roles = build_structured_security(parsed["rls_records"], parsed["ols_records"])
    diagnostics.append(f"Papeis de seguranca (RLS): {len(security_roles)}")

    # G17: sem dados de paginas/visuais do .Report/ (PBIR) nesta rodada (ver
    # docstring do modulo) -- build_unused_objects (pbix_analysis.py) parte
    # de nos tipo "visual" para saber o que e "usado"; sem nenhum visual,
    # TODA medida/coluna calculada apareceria como "nao usada", o que seria
    # ativamente enganoso (nao apenas incompleto). Por isso unusedObjects
    # fica deliberadamente vazio aqui, em vez de chamar build_unused_objects
    # e devolver um falso positivo em massa.
    diagnostics.append(
        "Objetos nao usados: nao calculado nesta analise TMDL (requer dados de "
        "visuais do .Report/, fora do escopo desta rodada)."
    )

    return {
        "nodes": nodes,
        "edges": deduped_edges,
        "warnings": diagnostics,
        "source": "tmdl",
        "relationships": structured_rels,
        "pages": [],
        "unusedObjects": [],
        "securityRoles": security_roles,
        # G18 (diagnostico de armazenamento) depende do log VertiPaq do
        # .pbix binario -- nao existe equivalente barato a partir de TMDL
        # texto puro; mesma postura de "nao fingir" documentada em
        # build_structured_diagnostics() (pbix_analysis.py) para rowCount.
        "diagnostics": {"totalSizeBytes": 0, "tables": [], "columns": []},
    }
