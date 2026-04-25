"""Optional PaddleOCR pass for raster regions.

PaddleOCR is heavy (paddlepaddle wheel ~hundreds of MB) and not installed by
default — install with `pip install -e '.[ocr]'`. When unavailable, this module
returns an empty list rather than crashing the ingest pipeline.

ASSUMPTION: for the synthetic sample PDF all text is vector, so the MVP
end-to-end can run without PaddleOCR. OCR is wired up so real scanned drawings
can be added later without touching the rest of the pipeline.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from archkg.schemas import TextPrimitive

# Match dimension strings like "1.05", "0.9 m", "1200 mm".
DIMENSION_RE = re.compile(r"\d+(?:\.\d+)?\s*(?:mm|m)?", re.IGNORECASE)


def _try_import_paddle() -> Any | None:
    try:
        from paddleocr import PaddleOCR
    except Exception:
        return None
    return PaddleOCR


def is_available() -> bool:
    return _try_import_paddle() is not None


def ocr_page_image(
    image_path: Path,
    *,
    lang: str = "ch",
    keep_only_dimensions: bool = True,
) -> list[TextPrimitive]:
    """Run PaddleOCR over a rasterized page image.

    Returns vector-text-shaped primitives so the rest of the pipeline doesn't care
    about the text origin.  When PaddleOCR is not installed, returns [].
    """
    paddle_cls = _try_import_paddle()
    if paddle_cls is None:
        return []

    ocr = paddle_cls(lang=lang, show_log=False)
    raw = ocr.ocr(str(image_path), cls=True)
    out: list[TextPrimitive] = []
    if not raw or not raw[0]:
        return out
    for line in raw[0]:
        poly, (text, conf) = line
        text = (text or "").strip()
        if not text:
            continue
        if keep_only_dimensions and not DIMENSION_RE.search(text):
            continue
        xs = [float(p[0]) for p in poly]
        ys = [float(p[1]) for p in poly]
        bbox = (min(xs), min(ys), max(xs), max(ys))
        out.append(
            TextPrimitive(text=text, bbox=bbox, source="ocr", confidence=float(conf))
        )
    return out
