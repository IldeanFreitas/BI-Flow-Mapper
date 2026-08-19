"""Testes de G14 -- linhagem visual<->campo estrutural.

Cobre `extract_structural_refs` (navegacao real da arvore
prototypeQuery.Select/projections em vez de regex sobre o texto bruto),
`extract_visuals_from_layout` fim-a-fim (zip sintetico com Report/Layout em
utf-16le) e a propagacao de `refSource`/`linkType` ate `build_visual_edges`.

Fixtures sinteticas no mesmo shape que o motor de query do Power BI Desktop
gera para prototypeQuery (From[]/Select[]) -- import direto de backend, sem
.pbix real.
"""
from __future__ import annotations

import io
import json
import zipfile

from backend import (
    build_visual_edges,
    build_visual_nodes,
    extract_structural_refs,
    extract_visuals_from_layout,
)


# ---------------------------------------------------------------------------
# Helpers sugeridos (adaptados) para montar Select items sinteticos no shape
# real do motor de query do Power BI.
# ---------------------------------------------------------------------------
def prototype_query(entity, select_items, extra_sources=None):
    sources = [{"Name": "s", "Entity": entity, "Type": 0}]
    if extra_sources:
        sources.extend(extra_sources)
    return {"From": sources, "Select": select_items}


def col_item(entity, prop, name=None, source="s"):
    return {
        "Column": {"Expression": {"SourceRef": {"Source": source}}, "Property": prop},
        "Name": name or f"{entity}.{prop}",
    }


def measure_item(entity, prop, name=None, source="s"):
    return {
        "Measure": {"Expression": {"SourceRef": {"Source": source}}, "Property": prop},
        "Name": name or f"{entity}.{prop}",
    }


def agg_item(entity, prop, name=None, source="s"):
    return {
        "Aggregation": {
            "Expression": {"Column": {"Expression": {"SourceRef": {"Source": source}}, "Property": prop}},
            "Function": 0,
        },
        "Name": name or f"Sum({entity}.{prop})",
    }


def single_visual_config(visual_type, select_items, entity="Sales", projections=None, extra_sources=None):
    return {
        "singleVisual": {
            "visualType": visual_type,
            "prototypeQuery": prototype_query(entity, select_items, extra_sources=extra_sources),
            "projections": projections or {},
        }
    }


# ---------------------------------------------------------------------------
# (1) extract_structural_refs por tipo de visual coberto
# ---------------------------------------------------------------------------
class TestStructuralRefsPerVisualType:
    def test_card_with_measure_select_yields_refs(self):
        config = single_visual_config(
            "card",
            [measure_item("Sales", "Total")],
            projections={"Values": [{"queryRef": "Sales.Total"}]},
        )
        refs = extract_structural_refs(config, {})
        assert refs
        assert "total" in refs
        assert "sales.total" in refs

    def test_table_with_column_selects_yields_refs_for_each_column(self):
        config = single_visual_config(
            "tableEx",
            [col_item("Sales", "Region"), col_item("Sales", "Amount")],
        )
        refs = extract_structural_refs(config, {})
        assert "region" in refs
        assert "amount" in refs
        assert "sales.region" in refs
        assert "sales.amount" in refs

    def test_bar_chart_with_column_axis_and_aggregation_value_yields_refs(self):
        config = single_visual_config(
            "barChart",
            [col_item("Sales", "Category"), agg_item("Sales", "Amount")],
        )
        refs = extract_structural_refs(config, {})
        assert "category" in refs
        assert "amount" in refs
        assert "sales.category" in refs
        assert "sales.amount" in refs

    def test_pie_chart_with_column_legend_and_measure_value_yields_refs(self):
        config = single_visual_config(
            "pieChart",
            [col_item("Sales", "Category"), measure_item("Sales", "Total")],
        )
        refs = extract_structural_refs(config, {})
        assert "category" in refs
        assert "total" in refs
        assert "sales.total" in refs


# ---------------------------------------------------------------------------
# (2) set() vazio para custom visual / config fora do schema padrao
# ---------------------------------------------------------------------------
class TestStructuralRefsEmptyForCustomVisuals:
    def test_config_without_single_visual_returns_empty_set(self):
        config = {"objects": {"general": [{"properties": {"formatString": "0"}}]}}
        assert extract_structural_refs(config, {}) == set()

    def test_single_visual_without_prototype_query_or_projections_returns_empty_set(self):
        config = {"singleVisual": {"visualType": "CustomVisual3rdParty"}}
        assert extract_structural_refs(config, {}) == set()

    def test_non_dict_config_and_query_do_not_raise_and_return_empty_set(self):
        assert extract_structural_refs(None, None) == set()
        assert extract_structural_refs("not a dict", []) == set()


# ---------------------------------------------------------------------------
# (5) resolucao de alias SourceRef.Source -> From[].Entity com multiplas fontes
# ---------------------------------------------------------------------------
class TestMultiSourceAliasResolution:
    def test_select_item_referencing_second_source_resolves_to_correct_entity(self):
        config = single_visual_config(
            "tableEx",
            [
                col_item("Sales", "Amount", source="s"),
                col_item("Region", "Name", name="Region.Name", source="r"),
            ],
            entity="Sales",
            extra_sources=[{"Name": "r", "Entity": "Region", "Type": 0}],
        )
        refs = extract_structural_refs(config, {})
        assert "sales.amount" in refs
        # A ref composta deve levar a entidade CORRETA (Region), resolvida via
        # alias "r" -> From[1].Entity, nao a primeira entidade do From por
        # coincidencia/ordem.
        assert "region.name" in refs
        assert "sales.name" not in refs


# ---------------------------------------------------------------------------
# (3) extract_visuals_from_layout fim-a-fim com zip sintetico
# ---------------------------------------------------------------------------
class _FakePathWrapper(io.BytesIO):
    """zipfile.ZipFile aceita um file-like diretamente (read/seek), e
    extract_visuals_from_layout so usa `path.name` para mensagens de log --
    um BytesIO com `.name` de classe basta, sem precisar de um Path real
    apontando pra disco."""

    name = "synthetic.pbix"


def _make_pbix_zip(layout_dict, encoding="utf-16le"):
    buffer = io.BytesIO()
    text = json.dumps(layout_dict, ensure_ascii=False)
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("Report/Layout", text.encode(encoding))
    return _FakePathWrapper(buffer.getvalue())


def _container(config_dict, query_dict=None):
    entry = {"config": json.dumps(config_dict, ensure_ascii=False)}
    if query_dict is not None:
        entry["query"] = json.dumps(query_dict, ensure_ascii=False)
    return entry


class TestExtractVisualsFromLayoutEndToEnd:
    def test_structural_visual_gets_structural_ref_source(self):
        layout = {
            "sections": [
                {
                    "displayName": "Page 1",
                    "visualContainers": [
                        _container(
                            single_visual_config(
                                "card",
                                [measure_item("Sales", "Total")],
                                projections={"Values": [{"queryRef": "Sales.Total"}]},
                            )
                        )
                    ],
                }
            ]
        }
        path = _make_pbix_zip(layout)
        visuals = extract_visuals_from_layout(path)

        assert len(visuals) == 1
        assert visuals[0]["refSource"] == "structural"
        assert "sales.total" in visuals[0]["refs"]

    def test_visual_without_structural_shape_falls_back_to_heuristic_per_visual(self):
        # JSON geral valido, mas ESTE container nao tem prototypeQuery/
        # projections reconheciveis (custom visual de terceiros) -- ainda
        # assim carrega texto com "Property"/"Entity" soltos que o regex
        # heuristico consegue casar.
        custom_config = {
            "singleVisual": {
                "visualType": "R_Script_Visual_By_ThirdParty",
                "objects": {"general": [{"properties": {"Entity": {"expr": {"Literal": {"Value": "'Sales'"}}}}}]},
            }
        }
        layout = {
            "sections": [
                {
                    "displayName": "Page 1",
                    "visualContainers": [_container(custom_config)],
                }
            ]
        }
        path = _make_pbix_zip(layout)
        visuals = extract_visuals_from_layout(path)

        assert len(visuals) == 1
        assert visuals[0]["refSource"] == "heuristic"

    def test_two_visuals_get_independent_ref_sources_in_the_same_valid_layout(self):
        structural_config = single_visual_config(
            "tableEx",
            [col_item("Sales", "Region")],
        )
        heuristic_config = {"singleVisual": {"visualType": "CustomVisual3rdParty"}}
        layout = {
            "sections": [
                {
                    "displayName": "Page 1",
                    "visualContainers": [
                        _container(structural_config),
                        _container(heuristic_config),
                    ],
                }
            ]
        }
        path = _make_pbix_zip(layout)
        visuals = extract_visuals_from_layout(path)

        assert len(visuals) == 2
        by_source = {v["refSource"] for v in visuals}
        assert by_source == {"structural", "heuristic"}

    def test_corrupted_report_layout_json_falls_back_to_regex_for_all_visuals(self):
        # Report/Layout inteiro NAO e JSON valido -- extract_visuals_from_layout
        # cai no fallback global por regex sobre o texto cru; todo visual
        # reconstruido dai e necessariamente "heuristic" (nao ha arvore para
        # navegar estruturalmente).
        # extract_visuals_from_layout decodifica primeiro como utf-16le e SO
        # cai para utf-8 se o resultado tiver menos de 5 "{" (heuristica para
        # detectar decodificacao errada) -- por isso o texto quebrado ainda
        # precisa de >=5 chaves literais soltas no INICIO para permanecer
        # decodificado como utf-16le (preservando o texto legivel de onde o
        # regex de fallback consegue extrair "visualType": "card" depois);
        # com menos de 5, o codigo tentaria reinterpretar os MESMOS bytes
        # como utf-8, intercalando bytes nulos entre cada caractere ASCII e
        # quebrando a contiguidade que o regex de fallback exige.
        broken_text = '{{{{{"visualType": "card", this is not valid json}'
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("Report/Layout", broken_text.encode("utf-16le"))

        path = _FakePathWrapper(buffer.getvalue())
        visuals = extract_visuals_from_layout(path)

        assert len(visuals) >= 1
        assert all(v["refSource"] == "heuristic" for v in visuals)


# ---------------------------------------------------------------------------
# (4) build_visual_edges propaga linkType
# ---------------------------------------------------------------------------
class TestBuildVisualEdgesPropagatesLinkType:
    def test_structural_visual_edge_carries_structural_link_type(self):
        visuals = [{"name": "Card1", "type": "Card", "refs": ["total"], "refSource": "structural"}]
        visual_nodes = build_visual_nodes(visuals)
        measure_nodes = [
            {"id": "measure:Sales:Total", "type": "measure", "label": "Total", "icon": "DAX", "meta": {"table": "Sales"}}
        ]

        edges = build_visual_edges(visual_nodes, measure_nodes, table_nodes=[])
        assert len(edges) == 1
        assert edges[0]["linkType"] == "structural"
        assert edges[0]["label"] == "used in visual"

    def test_heuristic_visual_edge_carries_heuristic_link_type(self):
        visuals = [{"name": "Table1", "type": "Table", "refs": ["region"], "refSource": "heuristic"}]
        visual_nodes = build_visual_nodes(visuals)
        table_nodes = [{"id": "model:sales", "type": "model", "label": "Region", "icon": "TBL", "meta": {}}]

        edges = build_visual_edges(visual_nodes, measure_nodes=[], table_nodes=table_nodes)
        assert len(edges) == 1
        assert edges[0]["linkType"] == "heuristic"

    def test_last_resort_single_measure_match_is_always_heuristic_even_for_structural_visual(self):
        # Visual estrutural cujas refs NAO batem com o nome da unica medida
        # do modelo -- o ultimo recurso (matched=False + len(measure_nodes)==1)
        # ainda dispara, mas a aresta resultante nao veio de nenhuma
        # navegacao/regex real, entao e sempre "heuristic" independente do
        # refSource do visual de origem.
        visuals = [{"name": "Card1", "type": "Card", "refs": ["campo-que-nao-bate"], "refSource": "structural"}]
        visual_nodes = build_visual_nodes(visuals)
        measure_nodes = [
            {"id": "measure:Sales:Total", "type": "measure", "label": "Total", "icon": "DAX", "meta": {"table": "Sales"}}
        ]

        edges = build_visual_edges(visual_nodes, measure_nodes, table_nodes=[])
        assert len(edges) == 1
        assert edges[0]["linkType"] == "heuristic"


# ---------------------------------------------------------------------------
# (5) resiliencia a Expression adversarialmente aninhada (achado de seguranca
# da auditoria da Fase 3 -- ver BACKLOG.md/G14)
# ---------------------------------------------------------------------------
class TestDeeplyNestedExpressionDoesNotCrash:
    def test_expression_nested_far_beyond_depth_limit_does_not_raise_recursion_error(self):
        # .pbix e entrada nao confiavel; um Report/Layout malicioso podia
        # aninhar Column.Expression centenas/milhares de niveis (drill-down
        # de hierarquia legitimo soh aninha uns poucos niveis reais) e
        # derrubava extract_structural_refs inteiro com RecursionError, que
        # o except amplo de extract_visuals_from_layout engolia para TODOS
        # os visuais do layout, nao so o malicioso.
        nested = {"SourceRef": {"Source": "unreachable"}}
        for _ in range(2000):
            nested = {"PropertyVariationSource": {"Expression": nested}}

        select_items = [{"Column": {"Expression": nested, "Property": "Ano"}, "Name": "x"}]
        query = prototype_query("Sales", select_items)

        # nao deve lancar RecursionError (nem nenhuma outra excecao) -- o
        # resultado pode ser vazio (a SourceRef real esta fora do limite de
        # profundidade), o que e aceitavel: resiliencia > descoberta best-effort.
        refs = extract_structural_refs({"singleVisual": {"prototypeQuery": query}}, query)
        assert isinstance(refs, set)

    def test_expression_nested_within_depth_limit_still_resolves(self):
        # Confirma que o limite nao quebrou o caso legitimo (hierarquia de
        # data com poucos niveis de aninhamento real).
        nested = {"SourceRef": {"Entity": "Calendar"}}
        for _ in range(5):
            nested = {"PropertyVariationSource": {"Expression": nested}}

        select_items = [{"Column": {"Expression": nested, "Property": "Ano"}, "Name": "x"}]
        query = prototype_query("Sales", select_items)

        refs = extract_structural_refs({"singleVisual": {"prototypeQuery": query}}, query)
        assert "calendar.ano" in refs
