from __future__ import annotations

from archkg.graph.sheet_graphs import build_sheet_graphs
from archkg.ingest.sheet_classification import build_sheet_classification
from archkg.schemas import LinePrimitive, PagePrimitives, Primitives, TextPrimitive


def _rect(x0: float, y0: float, x1: float, y1: float) -> list[LinePrimitive]:
    return [
        LinePrimitive(p0=(x0, y0), p1=(x1, y0)),
        LinePrimitive(p0=(x1, y0), p1=(x1, y1)),
        LinePrimitive(p0=(x1, y1), p1=(x0, y1)),
        LinePrimitive(p0=(x0, y1), p1=(x0, y0)),
    ]


def _text(text: str, x0: float = 20.0, y0: float = 20.0) -> TextPrimitive:
    return TextPrimitive(text=text, bbox=(x0, y0, x0 + 140.0, y0 + 16.0))


def test_build_sheet_graphs_builds_each_plan_page_and_skips_schedule() -> None:
    primitives = Primitives(
        source_pdf="multi-plan.pdf",
        points_per_meter=50.0,
        pages=[
            PagePrimitives(
                page_index=0,
                width_pt=500.0,
                height_pt=300.0,
                lines=_rect(10.0, 10.0, 110.0, 110.0),
                texts=[_text("FIRST FLOOR PLAN"), _text("BEDROOM", y0=44.0)],
            ),
            PagePrimitives(
                page_index=1,
                width_pt=500.0,
                height_pt=300.0,
                lines=_rect(210.0, 10.0, 310.0, 110.0),
                texts=[_text("SECOND FLOOR PLAN"), _text("LIVING", x0=220.0, y0=44.0)],
            ),
            PagePrimitives(
                page_index=2,
                width_pt=500.0,
                height_pt=300.0,
                lines=[],
                texts=[_text("DOOR SCHEDULE"), _text("MARK WIDTH HEIGHT", y0=44.0)],
            ),
        ],
    )
    classification = build_sheet_classification(primitives)

    report = build_sheet_graphs(primitives, classification)

    assert report.schema_version == "sheet_graphs.v1"
    assert report.graph_count == 2
    assert [entry.page_index for entry in report.graphs] == [0, 1]
    assert [entry.graph.page_index for entry in report.graphs] == [0, 1]
    assert [entry.component_counts["rooms"] for entry in report.graphs] == [1, 1]
    assert report.skipped_pages[0].page_index == 2
    assert report.skipped_pages[0].sheet_type == "schedule"
