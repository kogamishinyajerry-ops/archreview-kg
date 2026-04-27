from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from archkg.ingest.sheet_region_candidates import (
    SheetRegionCandidate,
    SheetRegionCandidateReport,
)

_COLORS: dict[str, tuple[int, int, int]] = {
    "design_region": (54, 211, 122),
    "title_block": (235, 76, 76),
    "schedule": (255, 184, 75),
    "legend": (58, 131, 255),
}


def render_sheet_region_candidate_overlay(
    source_pdf: Path,
    candidates: SheetRegionCandidateReport,
    out_png: Path,
    *,
    dpi: int = 200,
) -> Path:
    """Render page-0 source preview with advisory sheet-region boxes."""

    import fitz

    doc = fitz.open(str(source_pdf))
    try:
        page = doc[0]
        zoom = dpi / 72.0
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        draw = ImageDraw.Draw(image)
        scale_x = pix.width / float(page.rect.width)
        scale_y = pix.height / float(page.rect.height)
        for candidate in _page_zero_candidates(candidates):
            _draw_candidate(draw, candidate, scale_x=scale_x, scale_y=scale_y)
        out_png.parent.mkdir(parents=True, exist_ok=True)
        image.save(out_png)
        image.close()
        return out_png
    finally:
        doc.close()


def _page_zero_candidates(
    report: SheetRegionCandidateReport,
) -> list[SheetRegionCandidate]:
    for page in report.pages:
        if page.page_index == 0:
            return page.candidates
    return []


def _draw_candidate(
    draw: ImageDraw.ImageDraw,
    candidate: SheetRegionCandidate,
    *,
    scale_x: float,
    scale_y: float,
) -> None:
    x0, y0, x1, y1 = candidate.region
    scaled = (
        x0 * scale_x,
        y0 * scale_y,
        x1 * scale_x,
        y1 * scale_y,
    )
    color = _COLORS.get(candidate.kind, (255, 255, 255))
    width = 5 if candidate.kind == "design_region" else 4
    draw.rectangle(scaled, outline=color, width=width)
    label = f"{candidate.kind} {candidate.confidence:.0%}"
    lx0, ly0 = scaled[0], max(0.0, scaled[1] - 22.0)
    lx1, ly1 = lx0 + max(125.0, len(label) * 8.0), ly0 + 20.0
    draw.rectangle((lx0, ly0, lx1, ly1), fill=color)
    draw.text((lx0 + 5.0, ly0 + 3.0), label, fill=(0, 0, 0))
