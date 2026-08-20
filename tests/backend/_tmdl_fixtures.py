"""Fixtures TMDL sinteticas para os testes de tmdl_analysis.py (G17).

Texto puro escrito a mao, no formato real que o Power BI Desktop exporta
para pastas `.pbip`/`<Nome>.SemanticModel/definition/` -- sem depender de
nenhum arquivo `.tmdl` real no disco. Cobre deliberadamente: coluna comum +
coluna calculada (`expression = <DAX>`), medida single-line + medida
multi-linha (bloco de crase tripla), partition com M multi-linha (tambem
bloco de crase tripla) contendo um segredo sintetico (`Pwd=hunter2secret`)
para os testes de mask_secrets, `relationships.tmdl` e um `role`/
`tablePermission` (RLS) com outro segredo sintetico embutido na expressao de
filtro.

Indentacao com espacos (4 por nivel) -- `_preprocess_lines()` normaliza tabs
via `expandtabs(4)`, entao o parser trata os dois de forma equivalente; usar
espacos aqui deixa a fixture legivel sem ambiguidade visual sobre quantos
niveis cada linha tem.
"""
from __future__ import annotations

SALES_TABLE_TMDL = """\
table Sales

    column ProductID
        dataType: int64
        sourceColumn: ProductID

    column RegionID
        dataType: int64
        sourceColumn: RegionID

    column Amount
        dataType: double
        sourceColumn: Amount

    column MarginPct
        dataType: double
        isHidden
        expression = DIVIDE([Amount] - [Cost], [Amount])

    measure 'Total Sales' = SUM(Sales[Amount])
        formatString: \\$#,0

    measure 'Total Sales YTD' = ```
            CALCULATE(
                [Total Sales],
                DATESYTD('Date'[Date])
            )
            ```
        formatString: \\$#,0

    partition Sales = m
        mode: import
        source = ```
                let
                    Source = Sql.Database("myserver.database.windows.net", "SalesDB", [Query="SELECT * FROM Sales", Pwd="hunter2secret"])
                in
                    Source
                ```
"""

REGION_TABLE_TMDL = """\
table Region

    column RegionID
        dataType: int64
        sourceColumn: RegionID

    column RegionName
        dataType: string
        sourceColumn: RegionName

    partition Region = m
        mode: import
        source = ```
                let
                    Source = Sql.Database("myserver.database.windows.net", "SalesDB")
                in
                    Source
                ```
"""

# fromColumn/toColumn no formato "Tabela.Coluna" -- o mesmo que o Power BI
# Desktop grava de verdade em relationships.tmdl.
RELATIONSHIPS_TMDL = """\
relationship 8f2e1a3b-1234-5678-9abc-def012345678

    fromColumn: Sales.RegionID
    toColumn: Region.RegionID
    crossFilteringBehavior: bothDirections
"""

# RLS basico: um papel com uma unica tablePermission cuja expressao de
# filtro carrega um segredo sintetico (mesmo padrao "Pwd=..." coberto por
# graph_utils.mask_secrets/_SECRET_KV_PATTERNS, ver test_mask_secrets.py).
ROLE_TMDL = """\
role 'Region Manager'
    modelPermission: read

    tablePermission Sales = [ConnectionNote] = "Pwd=hunter2secret;"
"""

# Conteudo .tmdl sintaticamente valido (nao lanca excecao de parsing) mas
# sem NENHUM bloco reconhecivel (sem "table"/"measure"/"relationship"/
# "role"/"expression" de topo) -- dispara TmdlAnalysisError em
# analyze_tmdl_files().
UNRECOGNIZABLE_TMDL = """\
this is just some random prose
with no table or measure keyword at all
just free text that happens to be inside a .tmdl file
"""


def full_semantic_model_files(prefix: str = "SalesModel.SemanticModel/definition"):
    """Lista de (caminho_relativo, conteudo) cobrindo tabela+coluna comum+
    coluna calculada+medida single-line+medida multi-linha+partition M
    multi-linha (Sales.tmdl), uma segunda tabela simples (Region.tmdl),
    relacionamento entre as duas e um papel RLS -- o mesmo shape de upload
    que o frontend monta a partir de uma pasta .pbip/.SemanticModel real
    selecionada pelo usuario."""
    return [
        (f"{prefix}/tables/Sales.tmdl", SALES_TABLE_TMDL),
        (f"{prefix}/tables/Region.tmdl", REGION_TABLE_TMDL),
        (f"{prefix}/relationships.tmdl", RELATIONSHIPS_TMDL),
        (f"{prefix}/roles.tmdl", ROLE_TMDL),
    ]


def deep_nesting_tmdl(depth: int = 5000) -> str:
    """Gera um `.tmdl` sintetico com `depth` niveis de indentacao CRESCENTE
    (uma linha a mais de indentacao por linha) -- entrada adversarial que um
    tokenizador recursivo nao sobreviveria (RecursionError, mesma licao do
    G14/extract_visuals_from_layout). `_build_tree()`/`_preprocess_lines()`
    sao iterativos (pilha explicita) de proposito -- ver docstring de
    tmdl_analysis.py."""
    lines = ["table Root"]
    for level in range(1, depth):
        lines.append(" " * level + f"child{level}")
    return "\n".join(lines)
