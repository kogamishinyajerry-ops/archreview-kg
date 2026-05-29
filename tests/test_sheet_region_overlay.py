from __future__ import annotations

from pathlib import Path

from PIL import Image

from archkg.annotate.sheet_region_overlay import render_sheet_region_candidate_overlay
from archkg.ingest.primitive_extractor import extract
from archkg.ingest.sheet_region_candidates import build_sheet_region_candidates

REPO_ROOT = Path(__file__).resolve().parents[1]
GENERATED_COMPLEX_PDF = REPO_ROOT / "samples" / "generated_complex_titleblock.pdf"


def test_sheet_region_candidate_overlay_writes_visible_region_boxes(
    tmp_path: Path,
) -> None:
    primitives = extract(GENERATED_COMPLEX_PDF)
    candidates = build_sheet_region_candidates(primitives)

    out_png = render_sheet_region_candidate_overlay(
        GENERATED_COMPLEX_PDF,
        candidates,
        tmp_path / "sheet_region_candidates_overlay.png",
    )

    assert out_png.exists()
    image = Image.open(out_png)
    try:
        colors = image.getcolors(maxcolors=1_000_000)
    finally:
        image.close()
    assert colors is not None
    # Overlay should add saturated marker colors on top of the grayscale
    # PDF preview, not just re-save a blank source render.
    assert any(r > 180 and g < 120 and b < 120 for _, (r, g, b) in colors)
