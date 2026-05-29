from __future__ import annotations

import json
from pathlib import Path

from archkg.ingest.sheet_classification import (
    build_sheet_classification,
    write_sheet_classification,
)
from archkg.schemas import LinePrimitive, PagePrimitives, Primitives, TextPrimitive


def _line(y: float) -> LinePrimitive:
    return LinePrimitive(p0=(0.0, y), p1=(500.0, y))


def _text(text: str, x0: float = 20.0, y0: float = 20.0) -> TextPrimitive:
    return TextPrimitive(text=text, bbox=(x0, y0, x0 + 120.0, y0 + 16.0))


def test_build_sheet_classification_identifies_plan_schedule_and_title_pages() -> None:
    primitives = Primitives(
        source_pdf="multi-sheet.pdf",
        pages=[
            PagePrimitives(
                page_index=0,
                width_pt=600,
                height_pt=400,
                lines=[_line(float(i * 8)) for i in range(24)],
                texts=[_text("FIRST FLOOR PLAN"), _text("BEDROOM", y0=44), _text("CORRIDOR", y0=68)],
            ),
            PagePrimitives(
                page_index=1,
                width_pt=600,
                height_pt=400,
                lines=[_line(float(i * 12)) for i in range(18)],
                texts=[_text("DOOR SCHEDULE"), _text("MARK WIDTH HEIGHT", y0=44)],
            ),
            PagePrimitives(
                page_index=2,
                width_pt=600,
                height_pt=400,
                lines=[_line(0), _line(380)],
                texts=[_text("TITLE SHEET"), _text("PROJECT DATA", y0=44), _text("REVISION", y0=68)],
            ),
        ],
    )

    report = build_sheet_classification(primitives)
    by_page = {page.page_index: page for page in report.pages}

    assert report.schema_version == "sheet_classification.v1"
    assert report.summary == {"plan": 1, "schedule": 1, "title": 1}
    assert by_page[0].sheet_type == "plan"
    assert by_page[0].eligible_for_graph is True
    assert by_page[1].sheet_type == "schedule"
    assert by_page[1].eligible_for_graph is False
    assert by_page[2].sheet_type == "title"
    assert by_page[2].eligible_for_graph is False
    assert by_page[1].evidence_texts == ["DOOR SCHEDULE", "MARK WIDTH HEIGHT"]


def test_write_sheet_classification_round_trips(tmp_path: Path) -> None:
    primitives = Primitives(
        source_pdf="one-sheet.pdf",
        pages=[
            PagePrimitives(
                page_index=0,
                width_pt=600,
                height_pt=400,
                lines=[_line(float(i * 10)) for i in range(12)],
                texts=[_text("FLOOR PLAN")],
            )
        ],
    )
    report = build_sheet_classification(primitives)
    out = write_sheet_classification(report, tmp_path / "sheet_classification.json")

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "sheet_classification.v1"
    assert payload["pages"][0]["sheet_type"] == "plan"
    assert payload["pages"][0]["eligible_for_graph"] is True
