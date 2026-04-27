"""Explicit sheet-region cropping for noisy drawing sheets.

The crop is a pre-graphing hygiene step: it lets callers isolate the
design area and exclude title blocks, borders, schedules, and legends
that should not become rooms, doors, or text-inventory evidence.
"""

from __future__ import annotations

from archkg.schemas import LinePrimitive, PagePrimitives, Primitives, TextPrimitive

SheetRegion = tuple[float, float, float, float]


def parse_sheet_region(raw: str) -> SheetRegion:
    parts = [part.strip() for part in raw.split(",")]
    if len(parts) != 4:
        raise ValueError("sheet-region must be four comma-separated numbers: x0,y0,x1,y1")
    try:
        x0, y0, x1, y1 = (float(part) for part in parts)
    except ValueError as exc:
        raise ValueError("sheet-region values must be numbers") from exc
    if x1 <= x0 or y1 <= y0:
        raise ValueError("sheet-region must satisfy x1 > x0 and y1 > y0")
    return (x0, y0, x1, y1)


def crop_primitives_to_region(
    primitives: Primitives,
    region: SheetRegion,
) -> Primitives:
    return Primitives(
        source_pdf=primitives.source_pdf,
        points_per_meter=primitives.points_per_meter,
        pages=[
            PagePrimitives(
                page_index=page.page_index,
                width_pt=page.width_pt,
                height_pt=page.height_pt,
                lines=[line for line in page.lines if _line_midpoint_inside(line, region)],
                texts=[text for text in page.texts if _text_center_inside(text, region)],
            )
            for page in primitives.pages
        ],
    )


def _line_midpoint_inside(line: LinePrimitive, region: SheetRegion) -> bool:
    x = (line.p0[0] + line.p1[0]) / 2
    y = (line.p0[1] + line.p1[1]) / 2
    return _point_inside(x, y, region)


def _text_center_inside(text: TextPrimitive, region: SheetRegion) -> bool:
    x0, y0, x1, y1 = text.bbox
    return _point_inside((x0 + x1) / 2, (y0 + y1) / 2, region)


def _point_inside(x: float, y: float, region: SheetRegion) -> bool:
    x0, y0, x1, y1 = region
    return x0 <= x <= x1 and y0 <= y <= y1


__all__ = ["SheetRegion", "crop_primitives_to_region", "parse_sheet_region"]
