from __future__ import annotations

from archkg.ingest.sheet_region import crop_primitives_to_region, parse_sheet_region
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
