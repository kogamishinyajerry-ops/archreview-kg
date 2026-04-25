"""PyMuPDF-driven primitive extraction (vector lines + vector text)."""

from __future__ import annotations

from pathlib import Path

import fitz

from archkg.schemas import LinePrimitive, PagePrimitives, TextPrimitive


def _normalize_bbox(bbox: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    x0, y0, x1, y1 = bbox
    return (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))


def _extract_lines(page: fitz.Page) -> list[LinePrimitive]:
    """Walk the page's drawing dictionary and emit one LinePrimitive per line item.

    PyMuPDF's `page.get_drawings()` returns each path as a dict with an `items` list
    where each item is a tuple `("l", p1, p2)` for line segments and `("re", rect)`
    for rectangles. We flatten rectangles into 4 lines so downstream code only deals
    with line segments.
    """
    out: list[LinePrimitive] = []
    for path in page.get_drawings():
        for item in path.get("items", []):
            kind = item[0]
            if kind == "l":
                p0 = (float(item[1].x), float(item[1].y))
                p1 = (float(item[2].x), float(item[2].y))
                if p0 != p1:
                    out.append(LinePrimitive(p0=p0, p1=p1))
            elif kind == "re":
                r = item[1]
                x0, y0, x1, y1 = float(r.x0), float(r.y0), float(r.x1), float(r.y1)
                out.append(LinePrimitive(p0=(x0, y0), p1=(x1, y0)))
                out.append(LinePrimitive(p0=(x1, y0), p1=(x1, y1)))
                out.append(LinePrimitive(p0=(x1, y1), p1=(x0, y1)))
                out.append(LinePrimitive(p0=(x0, y1), p1=(x0, y0)))
    return out


def _extract_texts(page: fitz.Page) -> list[TextPrimitive]:
    out: list[TextPrimitive] = []
    blocks = page.get_text("dict").get("blocks", [])
    for block in blocks:
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = (span.get("text") or "").strip()
                if not text:
                    continue
                bbox = _normalize_bbox(tuple(span["bbox"]))
                out.append(TextPrimitive(text=text, bbox=bbox, source="vector"))
    return out


def extract_pages(pdf_path: Path) -> list[PagePrimitives]:
    if not pdf_path.exists():
        raise FileNotFoundError(pdf_path)
    doc = fitz.open(str(pdf_path))
    try:
        pages: list[PagePrimitives] = []
        for i, page in enumerate(doc):
            pages.append(
                PagePrimitives(
                    page_index=i,
                    width_pt=float(page.rect.width),
                    height_pt=float(page.rect.height),
                    lines=_extract_lines(page),
                    texts=_extract_texts(page),
                )
            )
        return pages
    finally:
        doc.close()
