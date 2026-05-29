"""PDF page → PNG rendering with on-disk cache (M7.W1).

Used by the workbench's PDF viewport. Renders a page once at a chosen
DPI and stores the PNG under .archkg/page_cache/. Returns the rendered
image bytes plus the page's native point dimensions so the front-end
SVG bbox overlay can size its viewBox identically.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import fitz  # PyMuPDF

DEFAULT_DPI = 144
CACHE_DIR_NAME = "page_cache"


@dataclass
class RenderedPage:
    image_bytes: bytes
    image_width_px: int
    image_height_px: int
    page_width_pts: float
    page_height_pts: float
    rotation_degrees: int
    cache_path: Path


def _cache_dir(repo_root: Path) -> Path:
    d = repo_root / ".archkg" / CACHE_DIR_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def _cache_key(pdf_path: Path, page_index: int, dpi: int) -> str:
    h = hashlib.sha256()
    h.update(str(pdf_path.resolve()).encode())
    try:
        h.update(str(pdf_path.stat().st_mtime_ns).encode())
        h.update(str(pdf_path.stat().st_size).encode())
    except OSError:
        pass
    h.update(f"|p{page_index}|d{dpi}".encode())
    return h.hexdigest()[:24]


def render_page(
    pdf_path: Path,
    page_index: int = 0,
    *,
    dpi: int = DEFAULT_DPI,
    repo_root: Path | None = None,
) -> RenderedPage:
    """Render one PDF page to PNG. Cache on disk under .archkg/page_cache/.

    Returns a RenderedPage with the image bytes + native page dimensions
    so the caller can align an SVG overlay using PDF-point coordinates.
    """

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    root = repo_root or pdf_path.parent
    cache_dir = _cache_dir(root)
    cache_file = cache_dir / f"{_cache_key(pdf_path, page_index, dpi)}.png"

    with fitz.open(str(pdf_path)) as doc:
        if page_index < 0 or page_index >= len(doc):
            raise IndexError(
                f"page {page_index} out of range for {pdf_path.name} (page count: {len(doc)})"
            )
        page = doc[page_index]
        page_w_pts = float(page.rect.width)
        page_h_pts = float(page.rect.height)
        rotation = int(page.rotation)

        if cache_file.exists():
            image_bytes = cache_file.read_bytes()
            img_w, img_h = _png_dimensions(image_bytes)
        else:
            pix = page.get_pixmap(dpi=dpi, alpha=False)
            image_bytes = pix.tobytes("png")
            cache_file.write_bytes(image_bytes)
            img_w, img_h = pix.width, pix.height

    return RenderedPage(
        image_bytes=image_bytes,
        image_width_px=img_w,
        image_height_px=img_h,
        page_width_pts=page_w_pts,
        page_height_pts=page_h_pts,
        rotation_degrees=rotation,
        cache_path=cache_file,
    )


def _png_dimensions(b: bytes) -> tuple[int, int]:
    """Read width/height from PNG IHDR — no Pillow dependency required."""

    if len(b) < 24 or not b.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("not a valid PNG")
    # IHDR starts at byte 8: 4 bytes length + 4 bytes "IHDR" + 4 width + 4 height
    width = int.from_bytes(b[16:20], "big")
    height = int.from_bytes(b[20:24], "big")
    return width, height


def resolve_pdf_for_drawing(
    repo_root: Path,
    project_slug: str,
    drawing_source_path: str | None,
) -> Path | None:
    """Find the source PDF for a drawing.

    Search order:
      1. samples/real_plans/{project_slug}.pdf           — committed real plans
      2. drawing.source_path if it points to a real file
      3. drawing.source_path resolved relative to repo_root
    Returns None if no resolution found.
    """

    candidates: list[Path] = [
        repo_root / "samples" / "real_plans" / f"{project_slug}.pdf",
    ]
    if drawing_source_path and not drawing_source_path.startswith("<unknown"):
        raw = Path(drawing_source_path)
        candidates.append(raw if raw.is_absolute() else repo_root / raw)
    for c in candidates:
        if c.exists() and c.suffix.lower() == ".pdf":
            return c
    return None
