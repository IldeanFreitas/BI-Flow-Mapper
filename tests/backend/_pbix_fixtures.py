"""Fixtures sinteticas para simular o objeto `pbixray.PBIXRay` sem precisar
de um .pbix real e sem depender do parser binario do pbixray.

`analyze_pbix`/`build_documentation_docx`/`build_documentation_html`
instanciam `PBIXRay(str(path))` e leem atributos "amigaveis" (`model.schema`,
`model.dax_measures`, `model.rls`, etc -- ver `records_from`/`list_from` em
backend.py) que o pbixray ja expoe prontos, sem exigir o binario real de um
.pbix. Para os testes de G7/G15/G19/G20 aqui, que exercitam o PIPELINE de
documentacao (nao o parser binario em si -- isso e responsabilidade do
pacote pbixray, ja teria seus proprios testes upstream), uma classe Python
pura com esses atributos e suficiente e muito mais rapida/legivel que gerar
um .pbix binario de verdade.
"""
from __future__ import annotations

DEFAULT_RECORDS = {
    "power_query": [],
    "tmschema_datasources": [],
    "dax_measures": [],
    "dax_columns": [],
    "relationships": [],
    "schema": [],
    "tmschema_tables": [],
    "tmschema_columns": [],
    "tables": [],
    "rls": [],
    "ols": [],
}


def make_fake_pbixray_class(records: dict, scalars: dict | None = None):
    """Devolve uma classe substituta de `pbixray.PBIXRay`.

    Instanciavel com um unico argumento posicional (o path do .pbix,
    ignorado -- os dados vem inteiramente de `records`/`scalars`), expondo
    cada chave de `records` (mesclada sobre `DEFAULT_RECORDS`) como atributo,
    do mesmo jeito que `model.<attr>` funciona no pbixray real.

    `scalars` (G18): atributos escalares de verdade (ex. `model.size`, um
    int, nao um DataFrame/lista de registros) lidos via `scalar_from()`.
    Mantido separado de `records`/`DEFAULT_RECORDS` (que documentam um shape
    de lista de dicts) por clareza de intencao, mesmo que `__getattr__`
    devolvesse qualquer tipo de qualquer um dos dois dicts igualmente --
    um atributo ausente de `scalars` (nao passado pelo teste) continua
    ausente do FakePBIXRay, levantando AttributeError como o pbixray real
    faria numa versao mais antiga sem esse atributo.
    """
    merged = {**DEFAULT_RECORDS, **records}
    scalar_attrs = dict(scalars or {})

    class FakePBIXRay:
        def __init__(self, path):
            self.path = path

        def __getattr__(self, name):
            if name in scalar_attrs:
                return scalar_attrs[name]
            try:
                return merged[name]
            except KeyError:
                raise AttributeError(name)

    return FakePBIXRay


def patch_pbixray(monkeypatch, backend_module, records: dict, scalars: dict | None = None):
    """Substitui `backend.PBIXRay` pela classe fake para o teste corrente.

    Tambem trava `_PBIXRAY_IMPORT_ATTEMPTED = True` para que `load_pbixray()`
    (chamado de dentro de `analyze_pbix`/`build_documentation_docx`/
    `build_documentation_html`) nao tente reimportar o pacote real por cima
    do fake -- funciona igual esteja ou nao o pbixray de verdade instalado
    no ambiente de teste.
    """
    fake_class = make_fake_pbixray_class(records, scalars)
    monkeypatch.setattr(backend_module, "PBIXRay", fake_class)
    monkeypatch.setattr(backend_module, "_PBIXRAY_IMPORT_ATTEMPTED", True)
    return fake_class


def make_empty_pbix_bytes() -> bytes:
    """Corpo de upload minimo que passa por `zipfile.ZipFile` sem erro.

    `extract_visuals_from_layout` abre o arquivo recebido como zip (Report/
    Layout) antes de qualquer chamada a `PBIXRay` -- um zip valido sem essa
    entrada e tratado normalmente (visuals fica vazio), enquanto bytes
    arbitrarios fariam esse passo logar uma falha (ainda tolerada, mas
    desnecessaria para os testes que nao exercitam essa falha em si).
    """
    import io
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("placeholder.txt", "valid zip container, not a real pbix")
    return buffer.getvalue()
