"""BI Flow Mapper -- orquestrador do backend (G12: modularizacao).

Ate a Fase 3, este arquivo tinha ~4000 linhas cobrindo roteamento HTTP,
extracao pbixray, geracao DOCX/HTML, desenho SVG/PNG, logging e seguranca.
Foi dividido em modulos por responsabilidade:

  - logging_setup.py       -- configure_logging()/logger/LOG_FILE (G13)
  - graph_utils.py          -- helpers puros sem estado (edge/slug/first_value/
                               record_text/scalar/clean_records/doc_value/
                               mask_secrets G7) -- "leaf", zero dependencia
                               interna, para poder ser importado tanto por
                               pbix_analysis.py quanto por doc_export.py sem
                               criar ciclo.
  - connector_catalog.py    -- (ja existia) catalogo de conectores conhecidos.
  - connector_matching.py   -- deteccao/normalizacao de conectores Power
                               Query (detect_connector_nodes e afins).
  - pbix_analysis.py        -- pipeline de extracao (Power Query, datasources,
                               schema, medidas, colunas calculadas, paginas/
                               visuais, linhagem estrutural G14, objetos nao
                               usados G15, seguranca estruturada G19,
                               diagnostico G18) + analyze_pbix().
  - tmdl_analysis.py        -- G17: caminho paralelo de analise para pastas
                               .pbip/TMDL (sem pbixray) -- parser TMDL
                               pragmatico + analyze_tmdl_files(), reaproveitando
                               os build_* de pbix_analysis.py.
  - render_graphics.py      -- ERD/arquitetura em SVG e PNG (Pillow/cairosvg).
  - doc_export.py           -- build_documentation_docx/build_documentation_html
                               (G20) + os helpers build_*_rows compartilhados.
  - bi_server.py            -- Handler (roteamento HTTP, allowlist estatico
                               G6, validacao de Origin/Content-Length G5) +
                               bootstrap do processo (find_port/main).

Este arquivo continua sendo o entry point que `main_app.py`/
`BI_Flow_Mapper.spec` importam e que a suite de testes em `tests/backend/`
importa via `from backend import <nome>` -- por isso reexporta, sem mudar
nenhuma assinatura, TODO nome publico que existia aqui antes da
modularizacao (ver BACKLOG.md G12 para o racional completo de cada corte).

Excecao deliberada (documentada, nao um descuido): PBIXRay/load_pbixray()/
PBIXRAY_IMPORT_ERROR/_PBIXRAY_IMPORT_ATTEMPTED FICAM aqui, nao foram movidos
para pbix_analysis.py/doc_export.py junto com analyze_pbix()/
build_documentation_docx()/build_documentation_html(). Motivo:
`tests/backend/_pbix_fixtures.py::patch_pbixray` faz
`monkeypatch.setattr(backend, "PBIXRay", FakeClass)` -- o monkeypatch so
alcanca quem resolve o nome `PBIXRay` a partir do NAMESPACE do modulo
`backend` em tempo de chamada. pbix_analysis.py e doc_export.py fazem
`import backend` (nao `from backend import PBIXRay`) e usam
`backend.PBIXRay(...)`/`backend.load_pbixray()`/`backend.PBIXRAY_IMPORT_ERROR`
qualificados dentro do corpo das suas funcoes, exatamente para que esse
monkeypatch continue funcionando sem mudar nenhum teste.

Nota tecnica sobre `python backend.py` direto (dev/`biflowmapper-packaging-release`,
`launch.ps1`): quando este arquivo roda como `__main__`, o Python registra o
modulo em `sys.modules["__main__"]`, NAO em `sys.modules["backend"]`. Sem o
alias abaixo, o `import backend` feito por pbix_analysis.py/doc_export.py
(ver acima) NAO encontraria nada em `sys.modules["backend"]` e tentaria
IMPORTAR backend.py DE NOVO do zero -- uma segunda execucao concorrente do
mesmo arquivo, que bate exatamente na mesma linha `from pbix_analysis import
...` enquanto a primeira execucao ainda esta dentro do `import backend` de
pbix_analysis.py, causando `ImportError: cannot import name ... from
partially initialized module`. O alias faz `sys.modules["backend"]` apontar
para o MESMO objeto de modulo que ja esta em execucao como `__main__`, entao
o `import backend` dos outros modulos so vincula o nome (sem reexecutar
nada) -- o mesmo truque que faz `import backend` funcionar quando o teste
faz soh `import backend` (unica identidade de modulo, sem esse desvio).
"""
from __future__ import annotations

import sys as _sys

if __name__ == "__main__" and "backend" not in _sys.modules:
    _sys.modules["backend"] = _sys.modules[__name__]

from logging_setup import logger

# ── Lazy-loading do pbixray -- FICA aqui, ver docstring do modulo acima ────
PBIXRay = None
PBIXRAY_IMPORT_ERROR = ""
_PBIXRAY_IMPORT_ATTEMPTED = False


def load_pbixray() -> bool:
    global PBIXRay, PBIXRAY_IMPORT_ERROR, _PBIXRAY_IMPORT_ATTEMPTED
    if not _PBIXRAY_IMPORT_ATTEMPTED:
        _PBIXRAY_IMPORT_ATTEMPTED = True
        try:
            from pbixray import PBIXRay as _PBIXRay
            PBIXRay = _PBIXRay
        except Exception as import_error:
            PBIXRAY_IMPORT_ERROR = str(import_error)
            logger.warning("pbixray nao pode ser importado: %s", import_error, exc_info=True)
    return PBIXRay is not None


# ── Reexports, na ordem que resolve os imports circulares com seguranca ────
# (ver docstrings de cada modulo para o motivo de cada `import` bare vs.
# `from X import Y`; NAO reordene sem entender essas notas.)

from logging_setup import LOG_FILE, configure_logging  # noqa: E402  (logger ja importado acima)
from local_metrics import LOCAL_METRICS, LocalMetrics, lineage_coverage  # noqa: E402

from graph_utils import (  # noqa: E402
    _LONG_TOKEN_PATTERN,
    _SECRET_KV_PATTERNS,
    clean_records,
    doc_value,
    edge,
    first_value,
    initials,
    mask_secrets,
    record_text,
    scalar,
    slug,
    titleize,
    unique_by_id,
    unique_edges,
)

from connector_matching import (  # noqa: E402
    CANONICAL_CONNECTOR_NAMES,
    CONNECTORS,
    PREFERRED_PATTERN_CONNECTORS,
    canonical_connector_name,
    datasource_match_score,
    datasource_matches,
    detect_connector_nodes,
    has_connector_call,
    source_matches_query,
    source_node,
    source_node_from_connector,
)

from pbix_analysis import (  # noqa: E402
    USAGE_EDGE_LABELS,
    _add_structural_ref,
    _collect_select_refs,
    _resolve_select_entity,
    _select_field_ref,
    analyze_pbix,
    build_calc_column_dependency_edges,
    build_calc_column_nodes,
    build_measure_dependency_edges,
    build_measure_nodes,
    build_query_nodes,
    build_structured_diagnostics,
    build_structured_relationships,
    build_structured_security,
    build_table_nodes,
    build_unused_objects,
    build_visual_edges,
    build_visual_nodes,
    extract_connection_path_from_m,
    extract_pages_from_layout,
    extract_query_refs,
    extract_refs_from_text,
    extract_structural_refs,
    extract_visuals_from_layout,
    get_path,
    is_system_table,
    list_from,
    nested_value,
    parse_json_string,
    query_search_text,
    records_from,
    scalar_from,
    visual_title,
)

from render_graphics import (  # noqa: E402
    CAIROSVG_AVAILABLE,
    PIL_AVAILABLE,
    _cairosvg,
    _hex,
    _pil_png,
    _PILDraw,
    _PILFont,
    _PILImage,
    build_architecture_svg,
    build_erd_svg,
    load_cairosvg,
    load_pillow,
    make_arch_png,
    make_banner_png,
    make_erd_png,
    svg_to_png_bytes,
)

from doc_export import (  # noqa: E402
    DOC_TEXT,
    DOCX_IMPORT_ERROR,
    Document,
    _DOCX_IMPORT_ATTEMPTED,
    _html_banner,
    _html_code_block,
    _html_document_css,
    _html_escape,
    _html_expression_inventory,
    _html_key_value_table,
    _html_metric_grid,
    _html_svg_figure,
    _html_table,
    _html_toc,
    add_code_block,
    add_cover,
    add_doc_heading,
    add_expression_inventory,
    add_generic_records_table,
    add_key_value_table,
    add_metric_grid,
    add_paragraph,
    add_paragraph_bottom_border,
    add_power_query_evidence,
    add_records_table,
    add_section_banner,
    add_table_of_contents,
    bold_cell,
    bool_label,
    build_column_rows,
    build_datasource_rows,
    build_documentation_docx,
    build_documentation_html,
    build_edge_rows,
    build_expression_rows,
    build_page_rows,
    build_query_rows,
    build_readable_warnings,
    build_relationship_rows,
    build_source_rows,
    build_table_documentation_rows,
    build_visual_rows,
    clip,
    configure_document_styles,
    doc_text,
    insert_svg_image,
    load_docx,
    normalize_code_text,
    normalize_doc_locale,
    set_cell_font,
    set_cell_margins,
    set_table_borders,
    set_table_width,
    shade_cell,
    summarize_expression,
    summarize_m_expression,
    unique_texts,
)

from tmdl_analysis import (  # noqa: E402
    TmdlAnalysisError,
    analyze_tmdl_files,
    parse_tmdl_model,
)

from bi_server import (  # noqa: E402
    ASSETS_DIR,
    ANALYSIS_ACQUIRE_TIMEOUT_SECONDS,
    ANALYSIS_SEMAPHORE,
    DEFAULT_PORT,
    HOST,
    MAX_CONCURRENT_ANALYSES,
    MAX_UPLOAD_BYTES,
    MAX_ZIP_COMPRESSION_RATIO,
    MAX_ZIP_ENTRIES,
    MAX_ZIP_UNCOMPRESSED_BYTES,
    PORT_FILE,
    ROOT,
    RUNTIME_DIR,
    SPOOL_MAX_MEMORY_BYTES,
    STATIC_ALLOWLIST_EXACT,
    STATIC_ALLOWLIST_PREFIXES,
    Handler,
    UploadValidationError,
    derive_tmdl_model_name,
    find_port,
    is_healthy,
    is_port_open,
    main,
    open_browser,
    requested_port,
    split_multipart,
    validate_pbix_archive,
    write_port_file,
)


if __name__ == "__main__":
    main()
