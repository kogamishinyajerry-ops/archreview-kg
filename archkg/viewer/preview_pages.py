from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any, TypedDict

from archkg.graph.builder import EntityGraph


class PreviewPage(TypedDict):
    page_index: int
    page_number: int
    src: str
    width_px: int
    height_px: int
    layer: str


def render_pdf_preview_pages(
    pdf: Path,
    out_dir: Path,
    *,
    layer: str,
    legacy_name: str,
    dpi: int = 200,
) -> list[PreviewPage]:
    """Render every PDF page to PNGs while preserving the legacy first-page name."""

    import fitz

    out_dir.mkdir(parents=True, exist_ok=True)
    legacy_path = Path(legacy_name)
    pages: list[PreviewPage] = []
    doc = fitz.open(str(pdf))
    try:
        zoom = dpi / 72.0
        matrix = fitz.Matrix(zoom, zoom)
        for page_index in range(doc.page_count):
            page = doc[page_index]
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            filename = (
                legacy_name
                if page_index == 0
                else f"{legacy_path.stem}_page_{page_index + 1}{legacy_path.suffix}"
            )
            pix.save(str(out_dir / filename))
            pages.append(
                {
                    "page_index": page_index,
                    "page_number": page_index + 1,
                    "src": filename,
                    "width_px": pix.width,
                    "height_px": pix.height,
                    "layer": layer,
                }
            )
    finally:
        doc.close()
    return pages


def render_entity_overlay_preview_pages(
    pdf: Path,
    out_dir: Path,
    *,
    graphs: Sequence[EntityGraph],
    legacy_name: str = "entity_overlay.png",
    dpi: int = 144,
) -> list[PreviewPage]:
    """Render one entity overlay image per graph page.

    The first graph keeps the historical ``entity_overlay.png`` filename.
    Additional graph pages use page-indexed names so ``preview_pages.json``
    can switch overlay images without breaking old links.
    """

    from PIL import Image

    from archkg.graph.builder import render_overlay

    out_dir.mkdir(parents=True, exist_ok=True)
    unique_graphs: list[EntityGraph] = []
    seen: set[int] = set()
    for graph in graphs:
        if graph.page_index in seen:
            continue
        unique_graphs.append(graph)
        seen.add(graph.page_index)

    pages: list[PreviewPage] = []
    for order, graph in enumerate(unique_graphs):
        filename = (
            legacy_name
            if order == 0
            else _indexed_preview_name(legacy_name, graph.page_index)
        )
        out_png = render_overlay(graph, pdf, out_dir / filename, dpi=dpi)
        with Image.open(out_png) as image:
            width, height = image.size
        pages.append(
            {
                "page_index": graph.page_index,
                "page_number": graph.page_index + 1,
                "src": filename,
                "width_px": width,
                "height_px": height,
                "layer": "overlay",
            }
        )
    return pages


def write_preview_pages_manifest(
    out_dir: Path,
    *,
    source_pages: Sequence[PreviewPage],
    annotated_pages: Sequence[PreviewPage],
    overlay_available: bool = False,
    overlay_pages: Sequence[PreviewPage] | None = None,
) -> Path:
    source_layer = list(source_pages)
    annotated_layer = list(annotated_pages)
    overlay_layer: list[PreviewPage] = list(overlay_pages) if overlay_pages is not None else (
        [
            {
                "page_index": 0,
                "page_number": 1,
                "src": "entity_overlay.png",
                "width_px": 0,
                "height_px": 0,
                "layer": "overlay",
            }
        ]
        if overlay_available
        else []
    )
    layers: dict[str, list[PreviewPage]] = {
        "source": source_layer,
        "annotated": annotated_layer,
        "overlay": overlay_layer,
    }
    page_count = max(
        len(source_layer),
        len(annotated_layer),
        len(overlay_layer),
        0,
    )
    payload = {
        "schema_version": "preview_pages.v1",
        "available": page_count > 0,
        "page_count": page_count,
        "layers": layers,
        "warning_text": _warning_text(
            source_count=len(source_layer),
            annotated_count=len(annotated_layer),
            overlay_count=len(overlay_layer),
        ),
    }
    path = out_dir / "preview_pages.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_preview_pages_view(out_dir: Path) -> dict[str, Any]:
    path = out_dir / "preview_pages.json"
    if path.exists():
        try:
            payload = json.loads(path.read_text("utf-8"))
        except json.JSONDecodeError:
            return _legacy_preview_pages(out_dir, warning_text="preview_pages.json 无法解析。")
        if isinstance(payload, dict):
            return _normalize_payload(payload)
    return _legacy_preview_pages(out_dir, warning_text="preview_pages.json 暂无数据。")


def _normalize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    layers = payload.get("layers")
    normalized_layers = _empty_layers()
    if isinstance(layers, dict):
        for layer in ("source", "annotated", "overlay"):
            rows = layers.get(layer)
            if isinstance(rows, list):
                normalized_layers[layer] = [
                    row for row in rows if isinstance(row, dict)
                ]
    return {
        "schema_version": "preview_pages.v1",
        "available": bool(payload.get("available")),
        "page_count": _int(payload.get("page_count")),
        "layers": normalized_layers,
        "warning_text": _str(payload.get("warning_text")),
    }


def _legacy_preview_pages(out_dir: Path, *, warning_text: str) -> dict[str, Any]:
    layers = _empty_layers()
    if (out_dir / "source_preview.png").exists():
        layers["source"].append(_legacy_page("source", "source_preview.png"))
    if (out_dir / "annotated_preview.png").exists():
        layers["annotated"].append(_legacy_page("annotated", "annotated_preview.png"))
    if (out_dir / "entity_overlay.png").exists():
        layers["overlay"].append(_legacy_page("overlay", "entity_overlay.png"))
    page_count = 1 if any(layers.values()) else 0
    return {
        "schema_version": "preview_pages.v1",
        "available": page_count > 0,
        "page_count": page_count,
        "layers": layers,
        "warning_text": warning_text,
    }


def _legacy_page(layer: str, src: str) -> dict[str, Any]:
    return {
        "page_index": 0,
        "page_number": 1,
        "src": src,
        "width_px": 0,
        "height_px": 0,
        "layer": layer,
    }


def _empty_layers() -> dict[str, list[dict[str, Any]]]:
    return {"source": [], "annotated": [], "overlay": []}


def _warning_text(
    *,
    source_count: int,
    annotated_count: int,
    overlay_count: int,
) -> str:
    if source_count and annotated_count:
        if overlay_count > 1:
            overlay_note = "entity overlay 多页可用"
        elif overlay_count == 1:
            overlay_note = "entity overlay 仍仅第一页"
        else:
            overlay_note = "entity overlay 暂无预览"
        return f"多页 source / annotated preview 可用; {overlay_note}。"
    if source_count:
        return "多页 source preview 可用; annotated preview 暂无多页页集。"
    if annotated_count:
        return "多页 annotated preview 可用; source preview 暂无多页页集。"
    if overlay_count > 1:
        return "多页 entity overlay preview 可用。"
    if overlay_count == 1:
        return "entity overlay preview 可用。"
    return "多页 preview 暂无数据。"


def _indexed_preview_name(legacy_name: str, page_index: int) -> str:
    legacy_path = Path(legacy_name)
    return f"{legacy_path.stem}_page_{page_index + 1}{legacy_path.suffix}"


def _str(raw: object) -> str:
    return raw if isinstance(raw, str) else ""


def _int(raw: object) -> int:
    return raw if isinstance(raw, int) else 0


__all__ = [
    "PreviewPage",
    "load_preview_pages_view",
    "render_entity_overlay_preview_pages",
    "render_pdf_preview_pages",
    "write_preview_pages_manifest",
]
