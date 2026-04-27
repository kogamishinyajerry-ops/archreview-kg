"""Drawing-understanding summary for reviewer-facing result pages.

This layer explains what the current graph appears to contain. It is
evidence inventory, not compliance adjudication: it summarizes spaces,
openings, circulation, dimensions, OCR signals, and uncertainty flags
from existing artifacts.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

ROOM_LABEL_ZH = {
    "bedroom": "卧室",
    "bathroom": "卫生间",
    "living": "客厅",
    "kitchen": "厨房",
    "balcony": "阳台",
    "study": "书房",
    "dining": "餐厅",
    "kids": "儿童房",
}
RESIDENTIAL_LABELS = frozenset(ROOM_LABEL_ZH)
MAX_ROWS = 12


def build_drawing_understanding(
    primitives: Mapping[str, Any],
    graph: Mapping[str, Any],
    ocr_diagnostics: Mapping[str, Any] | None = None,
    *,
    limit: int = MAX_ROWS,
) -> dict[str, Any]:
    """Return a compact drawing-content inventory.

    Inputs are serialized artifact dictionaries so Studio pre-rendering,
    standalone viewer re-rendering, and tests can use the same function.
    """
    ocr_diagnostics = ocr_diagnostics or {}
    pages = _list(primitives.get("pages"))
    rooms = _list(graph.get("rooms"))
    doors = _list(graph.get("doors"))
    corridors = _list(graph.get("corridors"))
    dimensions = _list(graph.get("dimensions"))
    n_lines = sum(len(_list(page.get("lines"))) for page in pages)
    n_texts = sum(len(_list(page.get("texts"))) for page in pages)

    drawing_type = _drawing_type(n_lines, rooms, doors, corridors)
    likely_design = _likely_design(drawing_type, rooms)
    component_counts = {
        "lines": n_lines,
        "texts": n_texts,
        "rooms": len(rooms),
        "doors": len(doors),
        "corridors": len(corridors),
        "dimensions": len(dimensions),
        "ocr_texts": _int(ocr_diagnostics.get("text_count")),
    }
    spaces = [_space_row(room) for room in rooms[:limit]]
    openings = [_opening_row(door) for door in doors[:limit]]
    circulation = [_corridor_row(corridor) for corridor in corridors[:limit]]
    graph_dimensions = [_dimension_row(dim) for dim in dimensions[:limit]]
    ocr_dimensions = _list(ocr_diagnostics.get("dimension_rows"))[:limit]

    summary = (
        f"{likely_design}。识别到 {len(rooms)} 个空间、{len(doors)} 个门/洞口、"
        f"{len(corridors)} 条走廊、{len(dimensions) + len(ocr_dimensions)} 条尺寸证据。"
    )
    return {
        "drawing_type": drawing_type,
        "likely_design": likely_design,
        "summary": summary,
        "component_counts": component_counts,
        "components": {
            "spaces": spaces,
            "openings": openings,
            "circulation": circulation,
        },
        "dimension_evidence": {
            "graph_dimensions": graph_dimensions,
            "ocr_dimensions": ocr_dimensions,
            "ocr_dimension_count": _int(ocr_diagnostics.get("dimension_text_count")),
            "ocr_bound_count": _int(ocr_diagnostics.get("bound_dimension_count")),
        },
        "uncertainty_flags": _uncertainty_flags(
            rooms=rooms,
            doors=doors,
            corridors=corridors,
            dimensions=dimensions,
            ocr_diagnostics=ocr_diagnostics,
        ),
    }


def write_drawing_understanding(
    payload: Mapping[str, Any],
    out_path: Path,
) -> Path:
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), "utf-8")
    return out_path


def load_or_build_drawing_understanding(
    out_dir: Path,
    primitives: Mapping[str, Any],
    graph: Mapping[str, Any],
    ocr_diagnostics: Mapping[str, Any],
) -> dict[str, Any]:
    path = out_dir / "drawing_understanding.json"
    if path.exists():
        raw = json.loads(path.read_text("utf-8"))
        if isinstance(raw, dict):
            return {str(key): value for key, value in raw.items()}
    return build_drawing_understanding(primitives, graph, ocr_diagnostics)


def _drawing_type(
    n_lines: int,
    rooms: list[Mapping[str, Any]],
    doors: list[Mapping[str, Any]],
    corridors: list[Mapping[str, Any]],
) -> str:
    if rooms or doors or corridors:
        return "建筑平面图"
    if n_lines > 0:
        return "线稿图纸"
    return "未知图纸"


def _likely_design(drawing_type: str, rooms: list[Mapping[str, Any]]) -> str:
    labels = {
        label
        for room in rooms
        if isinstance((label := room.get("label")), str) and label
    }
    if labels & RESIDENTIAL_LABELS:
        return "住宅平面图"
    return drawing_type


def _space_row(room: Mapping[str, Any]) -> dict[str, Any]:
    label = room.get("label")
    normalized = label if isinstance(label, str) and label else None
    area_m2 = _float(room.get("area_m2"))
    return {
        "id": _str(room.get("id")),
        "component": "空间",
        "label": normalized,
        "label_zh": ROOM_LABEL_ZH.get(normalized or "", "未分类"),
        "area_m2": area_m2,
        "area_text": _format_m2(area_m2),
        "bbox_text": _format_bbox(room.get("bbox")),
        "confidence": _float(room.get("confidence")),
        "uncertain": bool(room.get("uncertain", False)),
    }


def _opening_row(door: Mapping[str, Any]) -> dict[str, Any]:
    width_m = _float(door.get("width_m"))
    connects = _list(door.get("connects"))
    return {
        "id": _str(door.get("id")),
        "component": "门/洞口",
        "width_m": width_m,
        "width_text": _format_m(width_m),
        "connects_text": " / ".join(_str(v) for v in connects if v is not None) or "-",
        "bbox_text": _format_bbox(door.get("bbox")),
        "confidence": _float(door.get("confidence")),
    }


def _corridor_row(corridor: Mapping[str, Any]) -> dict[str, Any]:
    min_width_m = _float(corridor.get("min_width_m"))
    return {
        "id": _str(corridor.get("id")),
        "component": "走廊/交通空间",
        "min_width_m": min_width_m,
        "min_width_text": _format_m(min_width_m),
        "bbox_text": _format_bbox(corridor.get("bbox")),
        "confidence": _float(corridor.get("confidence")),
    }


def _dimension_row(dim: Mapping[str, Any]) -> dict[str, Any]:
    value_m = _float(dim.get("value_m"))
    return {
        "id": _str(dim.get("id")),
        "text": _str(dim.get("text")),
        "value_m": value_m,
        "value_text": _format_m(value_m),
        "bbox_text": _format_bbox(dim.get("bbox")),
        "confidence": _float(dim.get("confidence")),
    }


def _uncertainty_flags(
    *,
    rooms: list[Mapping[str, Any]],
    doors: list[Mapping[str, Any]],
    corridors: list[Mapping[str, Any]],
    dimensions: list[Mapping[str, Any]],
    ocr_diagnostics: Mapping[str, Any],
) -> list[str]:
    flags: list[str] = []
    unlabeled_rooms = sum(
        1 for room in rooms if not isinstance(room.get("label"), str) or not room.get("label")
    )
    if unlabeled_rooms:
        flags.append(f"存在未分类房间: {unlabeled_rooms} 个, 需要人工核对用途。")
    if rooms and not doors:
        flags.append("识别到空间但没有门/洞口, 可能漏检门洞或输入图纸不完整。")
    if rooms and not corridors:
        flags.append("未识别到走廊/交通空间, 复杂户型可能需要人工核对动线。")
    if not dimensions and not _int(ocr_diagnostics.get("dimension_text_count")):
        flags.append("未识别到尺寸证据, 尺寸相关判断只能依赖几何估计。")
    qa_count = _int(ocr_diagnostics.get("qa_candidate_count"))
    if qa_count:
        flags.append(f"OCR label QA 候选: {qa_count} 条, 房间用途需复核。")
    return flags


def _list(raw: object) -> list[Any]:
    return raw if isinstance(raw, list) else []


def _str(raw: object) -> str:
    return raw if isinstance(raw, str) else ""


def _int(raw: object) -> int:
    return raw if isinstance(raw, int) else 0


def _float(raw: object) -> float | None:
    if isinstance(raw, (int, float, str)):
        try:
            return float(raw)
        except ValueError:
            return None
    return None


def _format_m(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.2f} m"


def _format_m2(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.1f} m²"


def _format_bbox(raw: object) -> str:
    if not isinstance(raw, (list, tuple)) or len(raw) != 4:
        return "-"
    try:
        return ", ".join(f"{float(v):.1f}" for v in raw)
    except (TypeError, ValueError):
        return "-"


__all__ = [
    "build_drawing_understanding",
    "load_or_build_drawing_understanding",
    "write_drawing_understanding",
]
