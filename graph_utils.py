"""Utilitarios genericos e sem estado, compartilhados por pbix_analysis.py,
connector_matching.py e doc_export.py (G12 -- modularizacao de backend.py).

Modulo "leaf" deliberado: zero dependencia de outro modulo do projeto, so
stdlib (json/re). Existe para que pbix_analysis.py e connector_matching.py
possam compartilhar estes helpers (edge/slug/first_value/record_text/...)
sem um depender do outro (ver connector_matching.py), e para que
mask_secrets/doc_value (G7) fiquem disponiveis tanto para o pipeline de
analise (build_structured_security -- RLS tambem precisa mascarar segredos)
quanto para o pipeline de export (doc_export.py), sem criar uma dependencia
doc_export -> pbix_analysis -> doc_export.
"""
from __future__ import annotations

import json
import re


def edge(source, target, label, extra=None):
    data = {"id": f"{source}->{target}", "from": source, "to": target, "label": label}
    if extra:
        data.update(extra)
    return data


def first_value(record, keys):
    for key in keys:
        if key in record and record[key] not in ("", None):
            return record[key]
    return ""


def slug(value):
    value = str(value).lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "item"


def initials(value):
    parts = [part for part in re.split(r"[^A-Za-z0-9]+", str(value)) if part]
    return ("".join(part[0] for part in parts[:3]).upper() or "SRC")[:4]


def titleize(value):
    value = re.sub(r"[_-]+", " ", str(value))
    value = re.sub(r"([a-z])([A-Z])", r"\1 \2", value)
    return value.title()


def unique_by_id(items):
    result = {}
    for item in items:
        result[item["id"]] = item
    return list(result.values())


def unique_edges(items):
    result = {}
    for item in items:
        result[item["id"]] = item
    return list(result.values())


def record_text(record):
    if not isinstance(record, dict):
        return str(record)
    values = []
    for value in record.values():
        if isinstance(value, (dict, list)):
            values.append(json.dumps(value, ensure_ascii=False, default=str))
        elif value not in ("", None):
            values.append(str(value))
    return " ".join(values)


def scalar(value):
    if value is None:
        return ""
    try:
        if value != value:
            return ""
    except Exception:
        # G13: deliberadamente NAO logado -- e um teste de NaN (`value != value`)
        # rodado por valor de CADA celula de CADA dataframe do pbixray (pode ser
        # centenas de milhares de chamadas por analise). Um tipo cujo `__ne__`
        # lanca excecao aqui e um caso defensivo esperado, nao um erro real;
        # logar aqui inundaria o arquivo de log sem valor diagnostico.
        pass
    return value.item() if hasattr(value, "item") else value


def clean_records(records):
    cleaned = []
    for record in records:
        if not isinstance(record, dict):
            continue
        cleaned.append({str(key): scalar(value) for key, value in record.items()})
    return cleaned


def doc_value(value):
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, default=str)
    return str(value)


# G7: padroes de segredo a mascarar antes de qualquer connection string ou
# codigo M/DAX ir para o DOCX exportado. Cada padrao captura a CHAVE +
# separador em group(1)/group(2) e substitui so o VALOR por "***MASKED***",
# preservando o resto da string legivel (ex. "Server=x;Pwd=***MASKED***;...").
_SECRET_KV_PATTERNS = [
    # Pwd=/Password=: convencao de connection string ODBC/OLEDB/ADO.NET --
    # o valor vai ate o proximo ';' (nao paramos em espaco: senhas podem
    # conter espacos nesse formato).
    re.compile(r'(?i)\b(pwd|password)(\s*=\s*)[^;\r\n]*'),
    # api_key=/apikey=: convencao de query string / config / literal M --
    # termina no primeiro separador comum desses contextos.
    re.compile(r'(?i)\b(api[_-]?key)(\s*=\s*)[^\s;&"\'\]\r\n]*'),
    # Authorization: <esquema> <token> -- header HTTP, tambem comum dentro
    # de registros M como Headers=[Authorization="Bearer ..."].
    re.compile(r'(?i)\b(authorization)(\s*[:=]\s*"?)[^"\];,\r\n]*'),
]

# Catch-all: tokens de 20+ caracteres alfanumericos contiguos sem separador
# (padrao comum de API key/token/hash) que nao foram pegos pelos padroes
# nomeados acima.
_LONG_TOKEN_PATTERN = re.compile(r"\b[A-Za-z0-9]{20,}\b")


def mask_secrets(value) -> str:
    """Redige segredos de uma connection string ou trecho de codigo M/DAX.

    Usado em todo texto cru que entra no DOCX exportado (G7): connection
    strings de TMSCHEMA_DATASOURCES, expressoes M do Power Query e
    expressoes DAX de medidas/colunas calculadas podem conter credenciais
    literais (ex. Sql.Database com Pwd embutido, ou um header Authorization
    hardcoded numa chamada Web.Contents).
    """
    text = doc_value(value)
    if not text:
        return text
    masked = text
    for pattern in _SECRET_KV_PATTERNS:
        masked = pattern.sub(lambda m: f"{m.group(1)}{m.group(2)}***MASKED***", masked)
    masked = _LONG_TOKEN_PATTERN.sub("***MASKED***", masked)
    return masked
