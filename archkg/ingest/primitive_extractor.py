"""Aggregate vector + OCR primitives into a single `primitives.json`."""

from __future__ import annotations

import json
from pathlib import Path

from archkg.ingest import ocr, pdf_loader
from archkg.schemas import Primitives


def extract(
    pdf_path: Path,
    *,
    points_per_meter: float = 50.0,
    use_ocr: bool = False,
) -> Primitives:
    pages = pdf_loader.extract_pages(pdf_path)
    if use_ocr and ocr.is_available():
        # OCR over rasterized pages would happen here; left as a no-op for MVP
        # because the synthetic sample is fully vector. Wiring exists so a real
        # scanned PDF can be supported by adding a rasterize step.
        pass
    return Primitives(
        source_pdf=str(pdf_path),
        points_per_meter=points_per_meter,
        pages=pages,
    )


def write_json(primitives: Primitives, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(primitives.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return out_path
