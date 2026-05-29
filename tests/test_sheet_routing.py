from __future__ import annotations

from archkg.ingest.sheet_classification import build_sheet_classification
from archkg.ingest.sheet_routing import route_primitives_for_graph
from archkg.schemas import LinePrimitive, PagePrimitives, Primitives, TextPrimitive


def _line(y: float) -> LinePrimitive:
    return LinePrimitive(p0=(0.0, y), p1=(500.0, y))


def _text(text: str, x0: float = 20.0, y0: float = 20.0) -> TextPrimitive:
    return TextPrimitive(text=text, bbox=(x0, y0, x0 + 140.0, y0 + 16.0))


def _plan_page(page_index: int) -> PagePrimitives:
    return PagePrimitives(
        page_index=page_index,
        width_pt=600,
        height_pt=400,
        lines=[_line(float(i * 8)) for i in range(24)],
        texts=[_text("FIRST FLOOR PLAN"), _text("BEDROOM", y0=44), _text("CORRIDOR", y0=68)],
    )


def test_route_primitives_selects_single_confident_plan_page() -> None:
    primitives = Primitives(
        source_pdf="multi-sheet.pdf",
        pages=[
            PagePrimitives(
                page_index=0,
                width_pt=600,
                height_pt=400,
                lines=[_line(0), _line(380)],
                texts=[_text("TITLE SHEET"), _text("PROJECT DATA", y0=44)],
            ),
            _plan_page(1),
            PagePrimitives(
                page_index=2,
                width_pt=600,
                height_pt=400,
                lines=[_line(float(i * 12)) for i in range(18)],
                texts=[_text("DOOR SCHEDULE"), _text("MARK WIDTH HEIGHT", y0=44)],
            ),
        ],
    )
    classification = build_sheet_classification(primitives)

    result = route_primitives_for_graph(primitives, classification)

    assert result.decision.schema_version == "sheet_routing.v1"
    assert result.decision.mode == "classified_single_plan_page"
    assert result.decision.selected_page_indexes == [1]
    assert result.decision.excluded_page_indexes == [0, 2]
    assert result.decision.fallback_reason is None
    assert [page.page_index for page in result.primitives.pages] == [1]


def test_route_primitives_falls_back_when_non_plan_page_is_unknown() -> None:
    primitives = Primitives(
        source_pdf="multi-sheet.pdf",
        pages=[
            _plan_page(0),
            PagePrimitives(
                page_index=1,
                width_pt=600,
                height_pt=400,
                lines=[_line(0)],
                texts=[_text("unlabeled scanned sheet")],
            ),
        ],
    )
    classification = build_sheet_classification(primitives)

    result = route_primitives_for_graph(primitives, classification)

    assert result.decision.mode == "legacy_all_pages"
    assert result.decision.selected_page_indexes == [0, 1]
    assert result.decision.excluded_page_indexes == []
    assert result.decision.fallback_reason == "unknown_or_low_confidence_non_plan_page"
    assert [page.page_index for page in result.primitives.pages] == [0, 1]


def test_route_primitives_falls_back_when_multiple_plan_pages_exist() -> None:
    primitives = Primitives(
        source_pdf="multi-plan.pdf",
        pages=[_plan_page(0), _plan_page(1)],
    )
    classification = build_sheet_classification(primitives)

    result = route_primitives_for_graph(primitives, classification)

    assert result.decision.mode == "legacy_all_pages"
    assert result.decision.fallback_reason == "multiple_eligible_plan_pages"
    assert result.decision.selected_page_indexes == [0, 1]
