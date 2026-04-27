"""Generate a deterministic complex floor-plan PDF with a title block.

This fixture is intentionally generated, not a public real drawing. It
exercises two things that real architectural sheets commonly have:

- a dense design region with multiple rooms, doors, dimensions, and
  vertical-circulation text hints;
- a title block / revision table that must be cropped out before
  graphing or benchmark authoring.
"""

from __future__ import annotations

from pathlib import Path

import fitz

PT_PER_M = 50.0
OX, OY = 35.0, 35.0
DESIGN_W_M, DESIGN_H_M = 16.0, 12.0
PAGE_W_PT, PAGE_H_PT = 1120.0, 700.0


def m_to_pt(x_m: float, y_m: float) -> tuple[float, float]:
    return OX + x_m * PT_PER_M, OY + y_m * PT_PER_M


def _line(page: fitz.Page, x0: float, y0: float, x1: float, y1: float) -> None:
    page.draw_line(m_to_pt(x0, y0), m_to_pt(x1, y1), color=(0, 0, 0), width=1.0)


def _pt_line(page: fitz.Page, x0: float, y0: float, x1: float, y1: float) -> None:
    page.draw_line((x0, y0), (x1, y1), color=(0, 0, 0), width=0.8)


def _label(page: fitz.Page, x_m: float, y_m: float, text: str, *, size: float = 7.0) -> None:
    page.insert_text(m_to_pt(x_m, y_m), text, fontsize=size, color=(0, 0, 0))


def _pt_label(page: fitz.Page, x: float, y: float, text: str, *, size: float = 6.0) -> None:
    page.insert_text((x, y), text, fontsize=size, color=(0, 0, 0))


def _design_shell(page: fitz.Page) -> None:
    _line(page, 0, 0, DESIGN_W_M, 0)
    _line(page, DESIGN_W_M, 0, DESIGN_W_M, DESIGN_H_M)
    _line(page, DESIGN_W_M, DESIGN_H_M, 0, DESIGN_H_M)
    _line(page, 0, DESIGN_H_M, 0, 0)


def _apartment_grid(page: fitz.Page) -> None:
    # Horizontal corridor band with deliberate door gaps.
    _line(page, 0, 5.0, 1.1, 5.0)
    _line(page, 2.0, 5.0, 5.2, 5.0)
    _line(page, 6.1, 5.0, 9.8, 5.0)
    _line(page, 10.7, 5.0, 14.0, 5.0)
    _line(page, 14.9, 5.0, 16.0, 5.0)

    _line(page, 0, 6.2, 1.1, 6.2)
    _line(page, 2.0, 6.2, 5.2, 6.2)
    _line(page, 6.1, 6.2, 9.8, 6.2)
    _line(page, 10.7, 6.2, 14.0, 6.2)
    _line(page, 14.9, 6.2, 16.0, 6.2)

    # Vertical separations, with a central stair/core zone.
    for x in (3.2, 6.4, 9.6, 12.8):
        _line(page, x, 0, x, 5.0)
        _line(page, x, 6.2, x, 12.0)
    _line(page, 8.0, 5.0, 8.0, 6.2)

    # Internal apartment partitions.
    for x0 in (0.0, 3.2, 6.4, 9.6, 12.8):
        _line(page, x0, 2.7, x0 + 3.2, 2.7)
        _line(page, x0 + 1.45, 0, x0 + 1.45, 2.7)
        _line(page, x0 + 1.45, 6.2, x0 + 1.45, 9.0)
        _line(page, x0, 9.0, x0 + 3.2, 9.0)


def _labels(page: fitz.Page) -> None:
    for x in (0.6, 3.8, 7.0, 10.2, 13.4):
        _label(page, x, 1.3, "BEDROOM")
        _label(page, x + 1.55, 1.3, "BATH")
        _label(page, x, 4.0, "LIVING")
        _label(page, x + 1.55, 4.0, "KITCHEN")
        _label(page, x, 8.1, "BEDROOM #1")
        _label(page, x + 1.55, 8.1, "BATH")
        _label(page, x, 10.7, "DINING")
        _label(page, x + 1.55, 10.7, "BALCONY")
    _label(page, 7.45, 5.55, "UP")
    _label(page, 8.2, 5.55, "DN")
    _label(page, 7.2, 5.95, "STAIR")
    _label(page, 6.1, 5.72, "CORRIDOR W=1.20")
    for x in (1.15, 5.25, 9.85, 14.05):
        _label(page, x, 4.88, "3068", size=6.0)
        _label(page, x, 6.08, "3068", size=6.0)
    _label(page, 0.2, 12.35, "160'-0\"", size=7.0)
    _label(page, 16.25, 0.4, "60'-0\"", size=7.0)


def _title_block(page: fitz.Page) -> None:
    x0, x1 = 875.0, 1085.0
    y0, y1 = 55.0, 650.0
    _pt_line(page, x0, y0, x1, y0)
    _pt_line(page, x1, y0, x1, y1)
    _pt_line(page, x1, y1, x0, y1)
    _pt_line(page, x0, y1, x0, y0)
    for y in range(110, 640, 45):
        _pt_line(page, x0, float(y), x1, float(y))
    for x in (930.0, 985.0, 1040.0):
        _pt_line(page, x, 110.0, x, y1)
    _pt_label(page, 895.0, 85.0, "RANDOM GENERATED COMPLEX PLAN", size=7.0)
    _pt_label(page, 895.0, 130.0, "TITLE BLOCK")
    _pt_label(page, 895.0, 175.0, "SHEET A-9")
    _pt_label(page, 895.0, 220.0, "NOT FOR REVIEW")
    _pt_label(page, 895.0, 265.0, "REV 01")
    _pt_label(page, 895.0, 310.0, "SCALE 1/8 = 1-0")
    for idx in range(8):
        _pt_label(page, 895.0, 360.0 + idx * 28.0, f"SCHEDULE ROW {idx + 1}")


def build(path: Path) -> Path:
    doc = fitz.open()
    page = doc.new_page(width=PAGE_W_PT, height=PAGE_H_PT)
    _design_shell(page)
    _apartment_grid(page)
    _labels(page)
    _title_block(page)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(path))
    doc.close()
    return path


if __name__ == "__main__":
    out = build(Path(__file__).parent / "generated_complex_titleblock.pdf")
    print(f"wrote {out}")
