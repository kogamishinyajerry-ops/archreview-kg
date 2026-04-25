"""Generate a synthetic architectural floor plan PDF for ingest/graph tests.

ASSUMPTION: until a real drawing PDF is provided, we use a deterministic
4-room + corridor + 2-door layout drawn with PyMuPDF vector primitives.
Scale: 1 m = 50 pt. Wall thickness: 4 pt (~0.08 m, irrelevant to rules).

Layout (top-down, units = meters):

    0,0          5,0          10,0
     +-----------+-------------+
     |           |             |
     |  BEDROOM  |   LIVING    |     <- north strip, 4 m tall
     |  (5x4)    |   (5x4)     |
     |           |             |
     +---door----+----door-----+ y=4
     |        CORRIDOR         |     <- corridor 1.05 m wide (FAILS rule)
     +---door----+----door-----+ y=5.05
     |           |             |
     | BATHROOM  |  KITCHEN    |     <- south strip
     |  (5x2.95) |  (5x2.95)   |
     |           |             |
     +-----------+-------------+ y=8
"""

from __future__ import annotations

from pathlib import Path

import fitz  # PyMuPDF

PT_PER_M = 50.0
PAGE_W_M, PAGE_H_M = 10.0, 8.0


def m_to_pt(x_m: float, y_m: float) -> tuple[float, float]:
    return x_m * PT_PER_M, y_m * PT_PER_M


def _line(page: fitz.Page, x0: float, y0: float, x1: float, y1: float) -> None:
    p0 = m_to_pt(x0, y0)
    p1 = m_to_pt(x1, y1)
    page.draw_line(p0, p1, color=(0, 0, 0), width=1.2)


def _label(page: fitz.Page, x_m: float, y_m: float, text: str) -> None:
    page.insert_text(m_to_pt(x_m, y_m), text, fontsize=8, color=(0, 0, 0))


def build(path: Path) -> Path:
    doc = fitz.open()
    page = doc.new_page(width=PAGE_W_M * PT_PER_M, height=PAGE_H_M * PT_PER_M)

    # Outer walls (rectangle 10x8 m)
    _line(page, 0, 0, 10, 0)
    _line(page, 10, 0, 10, 8)
    _line(page, 10, 8, 0, 8)
    _line(page, 0, 8, 0, 0)

    # Vertical mid-wall split (with door gaps in north & south rooms)
    _line(page, 5, 0, 5, 1.5)
    _line(page, 5, 2.4, 5, 4)  # north door gap 0.9 m
    _line(page, 5, 5.05, 5, 6.5)
    _line(page, 5, 7.4, 5, 8)  # south door gap 0.9 m

    # Top corridor wall (with doors into bedroom @ x=2..2.85 and into living @ x=7..7.85)
    _line(page, 0, 4, 2, 4)
    _line(page, 2.85, 4, 7, 4)
    _line(page, 7.85, 4, 10, 4)

    # Bottom corridor wall (with doors into bathroom and kitchen)
    _line(page, 0, 5.05, 2, 5.05)
    _line(page, 2.85, 5.05, 7, 5.05)
    _line(page, 7.85, 5.05, 10, 5.05)

    # Room labels (vector text — captured by PyMuPDF, no OCR needed)
    _label(page, 1.6, 2.0, "BEDROOM")
    _label(page, 6.6, 2.0, "LIVING")
    _label(page, 1.6, 6.5, "BATHROOM")
    _label(page, 6.6, 6.5, "KITCHEN")

    # Dimension annotations (text near the entity they describe)
    _label(page, 4.2, 4.55, "CORRIDOR W=1.05")  # corridor width text — < 1.20 (FAIL)
    _label(page, 2.05, 3.9, "DOOR 0.85")  # door width text — < 0.90 (FAIL)
    _label(page, 7.05, 3.9, "DOOR 0.85")  # second door — < 0.90 (FAIL)

    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(path))
    doc.close()
    return path


if __name__ == "__main__":
    out = build(Path(__file__).parent / "sample_clean.pdf")
    print(f"wrote {out}")
