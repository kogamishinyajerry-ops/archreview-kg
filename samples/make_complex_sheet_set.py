"""Generate a deterministic mixed-sheet architectural PDF fixture.

This fixture is generated in-repo for repeatable benchmark coverage. It
resembles a small residential drawing packet with two plan sheets plus
non-graph sheets, so it can lock sheet classification, per-plan graphing,
and skipped-sheet behavior without relying on a private project PDF.
"""

from __future__ import annotations

from pathlib import Path

import fitz

PT_PER_M = 50.0
PAGE_W_PT, PAGE_H_PT = 1120.0, 700.0
OX, OY = 45.0, 55.0
DESIGN_W_M, DESIGN_H_M = 15.0, 10.5


def m_to_pt(x_m: float, y_m: float) -> tuple[float, float]:
    return OX + x_m * PT_PER_M, OY + y_m * PT_PER_M


def _line(page: fitz.Page, x0: float, y0: float, x1: float, y1: float) -> None:
    page.draw_line(m_to_pt(x0, y0), m_to_pt(x1, y1), color=(0, 0, 0), width=1.0)


def _pt_line(page: fitz.Page, x0: float, y0: float, x1: float, y1: float) -> None:
    page.draw_line((x0, y0), (x1, y1), color=(0, 0, 0), width=0.8)


def _label(page: fitz.Page, x_m: float, y_m: float, text: str, *, size: float = 7.0) -> None:
    page.insert_text(m_to_pt(x_m, y_m), text, fontsize=size, color=(0, 0, 0))


def _pt_label(page: fitz.Page, x: float, y: float, text: str, *, size: float = 7.0) -> None:
    page.insert_text((x, y), text, fontsize=size, color=(0, 0, 0))


def _plan_sheet(page: fitz.Page, *, title: str, upper: bool) -> None:
    _pt_label(page, 45.0, 34.0, title, size=10.0)
    _pt_label(page, 760.0, 34.0, "RESIDENTIAL FLOOR PLAN", size=8.0)
    _line(page, 0, 0, DESIGN_W_M, 0)
    _line(page, DESIGN_W_M, 0, DESIGN_W_M, DESIGN_H_M)
    _line(page, DESIGN_W_M, DESIGN_H_M, 0, DESIGN_H_M)
    _line(page, 0, DESIGN_H_M, 0, 0)

    # Corridor with staggered door gaps.
    _line(page, 0, 4.4, 1.0, 4.4)
    _line(page, 1.75, 4.4, 4.6, 4.4)
    _line(page, 5.35, 4.4, 8.1, 4.4)
    _line(page, 8.85, 4.4, 11.6, 4.4)
    _line(page, 12.35, 4.4, 15.0, 4.4)
    _line(page, 0, 5.6, 1.0, 5.6)
    _line(page, 1.75, 5.6, 4.6, 5.6)
    _line(page, 5.35, 5.6, 8.1, 5.6)
    _line(page, 8.85, 5.6, 11.6, 5.6)
    _line(page, 12.35, 5.6, 15.0, 5.6)

    for x in (3.0, 6.0, 9.0, 12.0):
        _line(page, x, 0, x, 4.4)
        _line(page, x, 5.6, x, DESIGN_H_M)
    _line(page, 7.5, 4.4, 7.5, 5.6)

    # Repeatable apartment partitions on both sides of the corridor.
    for x0 in (0.0, 3.0, 6.0, 9.0, 12.0):
        _line(page, x0, 2.4, x0 + 3.0, 2.4)
        _line(page, x0 + 1.35, 0.0, x0 + 1.35, 2.4)
        _line(page, x0 + 1.35, 5.6, x0 + 1.35, 8.0)
        _line(page, x0, 8.0, x0 + 3.0, 8.0)

    room_prefix = "KIDS" if upper else "BEDROOM"
    for x in (0.55, 3.55, 6.55, 9.55, 12.55):
        _label(page, x, 1.15, room_prefix)
        _label(page, x + 1.42, 1.15, "BATH")
        _label(page, x, 3.55, "LIVING")
        _label(page, x + 1.42, 3.55, "KITCHEN")
        _label(page, x, 7.15, "BEDROOM")
        _label(page, x + 1.42, 7.15, "BATH")
        _label(page, x, 9.35, "DINING")
        _label(page, x + 1.42, 9.35, "BALCONY")

    _label(page, 6.65, 4.95, "UP" if not upper else "DN")
    _label(page, 7.8, 4.95, "STAIR")
    _label(page, 5.65, 5.25, "CORRIDOR W=1.20")
    for x in (1.05, 4.65, 8.15, 11.65):
        _label(page, x, 4.28, "3068", size=6.0)
        _label(page, x, 5.48, "2868", size=6.0)
    _label(page, 0.2, 10.88, "150'-0\"", size=7.0)
    _label(page, 15.35, 0.4, "52'-6\"", size=7.0)


def _schedule_sheet(page: fitz.Page) -> None:
    _pt_label(page, 50.0, 45.0, "DOOR SCHEDULE / ROOM SCHEDULE / LEGEND", size=11.0)
    x0, y0, x1, y1 = 50.0, 80.0, 1040.0, 620.0
    for y in range(int(y0), int(y1) + 1, 36):
        _pt_line(page, x0, float(y), x1, float(y))
    for x in (50.0, 170.0, 320.0, 480.0, 650.0, 820.0, 1040.0):
        _pt_line(page, x, y0, x, y1)
    _pt_label(page, 65.0, 103.0, "MARK")
    _pt_label(page, 190.0, 103.0, "WIDTH")
    _pt_label(page, 345.0, 103.0, "HEIGHT")
    _pt_label(page, 505.0, 103.0, "ROOM")
    _pt_label(page, 675.0, 103.0, "TYPE")
    _pt_label(page, 845.0, 103.0, "NOTES")
    for row in range(1, 13):
        y = 103.0 + row * 36.0
        _pt_label(page, 65.0, y, f"D{row:02d}")
        _pt_label(page, 190.0, y, "3068" if row % 2 else "2868")
        _pt_label(page, 345.0, y, "6'-8\"")
        _pt_label(page, 505.0, y, "BEDROOM" if row % 2 else "BATH")
        _pt_label(page, 675.0, y, "SWING")
        _pt_label(page, 845.0, y, "SEE PLAN")
    _pt_label(page, 50.0, 650.0, "SYMBOL LEGEND: STAIR, DOOR, WINDOW, DIMENSION")


def _elevation_sheet(page: fitz.Page) -> None:
    _pt_label(page, 50.0, 45.0, "BUILDING ELEVATION AND SECTION", size=11.0)
    base_y = 560.0
    _pt_line(page, 80.0, base_y, 1030.0, base_y)
    for x in range(110, 1000, 110):
        _pt_line(page, float(x), base_y, float(x + 60), 450.0)
        _pt_line(page, float(x + 60), 450.0, float(x + 110), base_y)
        _pt_line(page, float(x + 30), 510.0, float(x + 80), 510.0)
    for y in (500.0, 440.0, 380.0, 320.0):
        _pt_line(page, 90.0, y, 1010.0, y)
    _pt_label(page, 90.0, 610.0, "ELEVATION GRID")
    _pt_label(page, 90.0, 635.0, "SECTION A-A")
    _pt_label(page, 760.0, 635.0, "NOT A PLAN SHEET")


def build(path: Path) -> Path:
    doc = fitz.open()
    _plan_sheet(doc.new_page(width=PAGE_W_PT, height=PAGE_H_PT), title="A-101 FIRST FLOOR PLAN", upper=False)
    _schedule_sheet(doc.new_page(width=PAGE_W_PT, height=PAGE_H_PT))
    _plan_sheet(doc.new_page(width=PAGE_W_PT, height=PAGE_H_PT), title="A-102 SECOND FLOOR PLAN", upper=True)
    _elevation_sheet(doc.new_page(width=PAGE_W_PT, height=PAGE_H_PT))
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(path))
    doc.close()
    return path


if __name__ == "__main__":
    out = build(Path(__file__).parent / "generated_complex_sheet_set.pdf")
    print(f"wrote {out}")
