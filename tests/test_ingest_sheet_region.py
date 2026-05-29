from __future__ import annotations

from archkg.ingest.sheet_region import crop_primitives_to_region, parse_sheet_region
from archkg.ingest.sheet_region_candidates import build_sheet_region_candidates
from archkg.schemas import LinePrimitive, PagePrimitives, Primitives, TextPrimitive


def test_crop_primitives_to_region_drops_title_block_text_and_lines() -> None:
    primitives = Primitives(
        source_pdf="fixture.pdf",
        points_per_meter=50.0,
        pages=[
            PagePrimitives(
                page_index=0,
                width_pt=500.0,
                height_pt=300.0,
                lines=[
                    LinePrimitive(p0=(10.0, 10.0), p1=(120.0, 10.0)),
                    LinePrimitive(p0=(420.0, 40.0), p1=(490.0, 40.0)),
                ],
                texts=[
                    TextPrimitive(text="BEDROOM", bbox=(20.0, 20.0, 80.0, 40.0)),
                    TextPrimitive(text="PROJECT TITLE", bbox=(420.0, 220.0, 490.0, 240.0)),
                ],
            )
        ],
    )

    cropped = crop_primitives_to_region(primitives, (0.0, 0.0, 300.0, 300.0))

    assert [line.p0 for line in cropped.pages[0].lines] == [(10.0, 10.0)]
    assert [text.text for text in cropped.pages[0].texts] == ["BEDROOM"]


def test_parse_sheet_region_requires_four_ordered_numbers() -> None:
    assert parse_sheet_region("0,10,200,300") == (0.0, 10.0, 200.0, 300.0)

    for raw in ["0,1,2", "0,0,0,10", "0,10,20,5", "left,0,10,20"]:
        try:
            parse_sheet_region(raw)
        except ValueError:
            continue
        raise AssertionError(f"expected invalid sheet region: {raw}")


def test_sheet_region_candidates_detect_title_block_and_design_region() -> None:
    primitives = Primitives(
        source_pdf="fixture.pdf",
        points_per_meter=50.0,
        pages=[
            PagePrimitives(
                page_index=0,
                width_pt=1000.0,
                height_pt=600.0,
                lines=[
                    LinePrimitive(p0=(30.0, 30.0), p1=(720.0, 30.0)),
                    LinePrimitive(p0=(720.0, 30.0), p1=(720.0, 520.0)),
                    LinePrimitive(p0=(720.0, 520.0), p1=(30.0, 520.0)),
                    LinePrimitive(p0=(30.0, 520.0), p1=(30.0, 30.0)),
                    LinePrimitive(p0=(780.0, 40.0), p1=(970.0, 40.0)),
                    LinePrimitive(p0=(970.0, 40.0), p1=(970.0, 560.0)),
                    LinePrimitive(p0=(970.0, 560.0), p1=(780.0, 560.0)),
                    LinePrimitive(p0=(780.0, 560.0), p1=(780.0, 40.0)),
                    LinePrimitive(p0=(780.0, 140.0), p1=(970.0, 140.0)),
                    LinePrimitive(p0=(835.0, 40.0), p1=(835.0, 560.0)),
                ],
                texts=[
                    TextPrimitive(text="BEDROOM", bbox=(80.0, 80.0, 140.0, 100.0)),
                    TextPrimitive(text="KITCHEN", bbox=(280.0, 80.0, 340.0, 100.0)),
                    TextPrimitive(text="TITLE BLOCK", bbox=(800.0, 80.0, 900.0, 100.0)),
                    TextPrimitive(text="SHEET A-9", bbox=(800.0, 130.0, 870.0, 150.0)),
                    TextPrimitive(text="REV 01", bbox=(800.0, 180.0, 850.0, 200.0)),
                    TextPrimitive(text="SCHEDULE ROW 1", bbox=(800.0, 230.0, 920.0, 250.0)),
                    TextPrimitive(text="SCHEDULE ROW 2", bbox=(800.0, 280.0, 920.0, 300.0)),
                ],
            )
        ],
    )

    report = build_sheet_region_candidates(primitives)
    page = report.pages[0]
    by_kind = {candidate.kind: candidate for candidate in page.candidates}

    assert by_kind["design_region"].region[2] < by_kind["title_block"].region[0]
    assert by_kind["title_block"].region[0] >= 760.0
    assert by_kind["schedule"].region[0] >= 760.0
    assert any("TITLE BLOCK" in row.text for row in page.excluded_texts)
    assert any("title keyword" in row.reason for row in by_kind["title_block"].evidence)
