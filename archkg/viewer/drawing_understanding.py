"""Drawing-understanding summary for reviewer-facing result pages.

This layer explains what the current graph appears to contain. It is
evidence inventory, not compliance adjudication: it summarizes spaces,
openings, circulation, dimensions, OCR signals, and uncertainty flags
from existing artifacts.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
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
INVENTORY_LIMIT_MULTIPLIER = 3
SCHEMA_VERSION = "drawing_understanding.v2"


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
    pages = _mapping_list(primitives.get("pages"))
    rooms = _mapping_list(graph.get("rooms"))
    doors = _mapping_list(graph.get("doors"))
    corridors = _mapping_list(graph.get("corridors"))
    stairs = _mapping_list(graph.get("stairs"))
    vertical_hint_rows = [] if stairs else _vertical_circulation_hint_rows(pages)
    dimensions = _list(graph.get("dimensions"))
    n_lines = sum(len(_list(page.get("lines"))) for page in pages)
    n_texts = sum(len(_list(page.get("texts"))) for page in pages)
    text_inventory = _text_inventory(pages)

    vertical_circulation_count = len(stairs) + len(vertical_hint_rows)
    vertical_sources = vertical_hint_rows if vertical_hint_rows else stairs
    drawing_type = _drawing_type(n_lines, rooms, doors, corridors, vertical_sources)
    likely_design = _likely_design(drawing_type, rooms, vertical_sources)
    component_counts = {
        "lines": n_lines,
        "texts": n_texts,
        "rooms": len(rooms),
        "doors": len(doors),
        "corridors": len(corridors),
        "stairs": vertical_circulation_count,
        "dimensions": len(dimensions),
        "ocr_texts": _int(ocr_diagnostics.get("text_count")),
    }
    spaces = [_space_row(room) for room in rooms[:limit]]
    openings = [_opening_row(door) for door in doors[:limit]]
    circulation = [_corridor_row(corridor) for corridor in corridors[:limit]]
    vertical_circulation: list[Mapping[str, Any]] = [
        _stair_row(stair) for stair in stairs[:limit]
    ]
    if len(vertical_circulation) < limit:
        vertical_circulation.extend(vertical_hint_rows[: limit - len(vertical_circulation)])
    graph_dimensions = [_dimension_row(dim) for dim in dimensions[:limit]]
    ocr_dimensions = _list(ocr_diagnostics.get("dimension_rows"))[:limit]
    benchmark_signals = _benchmark_signals(
        rooms=rooms,
        doors=doors,
        corridors=corridors,
        stairs=vertical_sources,
        dimensions=dimensions,
        ocr_diagnostics=ocr_diagnostics,
    )

    summary = (
        f"{likely_design}。识别到 {len(rooms)} 个空间、{len(doors)} 个门/洞口、"
        f"{len(corridors)} 条走廊、{vertical_circulation_count} 个楼梯/垂直交通对象、"
        f"{len(dimensions) + len(ocr_dimensions)} 条尺寸证据。"
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "drawing_type": drawing_type,
        "likely_design": likely_design,
        "summary": summary,
        "component_counts": component_counts,
        "text_inventory": text_inventory,
        "drawing_profile": _drawing_profile(
            rooms=rooms,
            doors=doors,
            corridors=corridors,
            stairs=vertical_sources,
            dimensions=dimensions,
            n_lines=n_lines,
            n_texts=n_texts,
            ocr_diagnostics=ocr_diagnostics,
        ),
        "benchmark_signals": benchmark_signals,
        "component_inventory": _component_inventory(
            spaces=spaces,
            openings=openings,
            circulation=circulation,
            vertical_circulation=vertical_circulation,
            graph_dimensions=graph_dimensions,
            ocr_dimensions=ocr_dimensions,
            limit=limit * INVENTORY_LIMIT_MULTIPLIER,
        ),
        "components": {
            "spaces": spaces,
            "openings": openings,
            "circulation": circulation,
            "vertical_circulation": vertical_circulation,
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
            stairs=vertical_sources,
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
            payload = {str(key): value for key, value in raw.items()}
            if _is_current_payload(payload):
                return payload
    payload = build_drawing_understanding(primitives, graph, ocr_diagnostics)
    write_drawing_understanding(payload, path)
    return payload


def _is_current_payload(payload: Mapping[str, Any]) -> bool:
    return (
        payload.get("schema_version") == SCHEMA_VERSION
        and isinstance(payload.get("component_inventory"), list)
        and isinstance(payload.get("drawing_profile"), Mapping)
        and isinstance(payload.get("benchmark_signals"), Mapping)
    )


def _drawing_type(
    n_lines: int,
    rooms: list[Mapping[str, Any]],
    doors: list[Mapping[str, Any]],
    corridors: list[Mapping[str, Any]],
    stairs: list[Mapping[str, Any]],
) -> str:
    if rooms or doors or corridors:
        return "建筑平面图"
    if stairs:
        return "楼梯/垂直交通图"
    if n_lines > 0:
        return "线稿图纸"
    return "未知图纸"


def _likely_design(
    drawing_type: str,
    rooms: list[Mapping[str, Any]],
    stairs: list[Mapping[str, Any]],
) -> str:
    labels = {
        label
        for room in rooms
        if isinstance((label := room.get("label")), str) and label
    }
    if labels & RESIDENTIAL_LABELS:
        return "住宅平面图"
    if stairs and drawing_type == "楼梯/垂直交通图":
        return "楼梯/垂直交通设计图"
    return drawing_type


def _space_row(room: Mapping[str, Any]) -> dict[str, Any]:
    label = room.get("label")
    normalized = label if isinstance(label, str) and label else None
    area_m2 = _float(room.get("area_m2"))
    semantic_kind = (
        "residential_room" if normalized in RESIDENTIAL_LABELS else "unclassified_space"
    )
    confidence = _float(room.get("confidence"))
    uncertain = bool(room.get("uncertain", False))
    return {
        "id": _str(room.get("id")),
        "component": "空间",
        "category": "space",
        "semantic_kind": semantic_kind,
        "label": normalized,
        "label_zh": ROOM_LABEL_ZH.get(normalized or "", "未分类"),
        "area_m2": area_m2,
        "area_text": _format_m2(area_m2),
        "metric_text": _format_m2(area_m2),
        "bbox_text": _format_bbox(room.get("bbox")),
        "confidence": confidence,
        "confidence_band": _confidence_band(confidence, uncertain=uncertain),
        "uncertain": uncertain,
        "evidence_source": "graph",
    }


def _opening_row(door: Mapping[str, Any]) -> dict[str, Any]:
    width_m = _float(door.get("width_m"))
    connects = _list(door.get("connects"))
    confidence = _float(door.get("confidence"))
    uncertain = bool(door.get("uncertain", False))
    return {
        "id": _str(door.get("id")),
        "component": "门/洞口",
        "category": "opening",
        "semantic_kind": "door_opening",
        "width_m": width_m,
        "width_text": _format_m(width_m),
        "metric_text": _format_m(width_m),
        "connects_text": " / ".join(_str(v) for v in connects if v is not None) or "-",
        "bbox_text": _format_bbox(door.get("bbox")),
        "confidence": confidence,
        "confidence_band": _confidence_band(confidence, uncertain=uncertain),
        "uncertain": uncertain,
        "evidence_source": "graph",
    }


def _corridor_row(corridor: Mapping[str, Any]) -> dict[str, Any]:
    min_width_m = _float(corridor.get("min_width_m"))
    confidence = _float(corridor.get("confidence"))
    uncertain = bool(corridor.get("uncertain", False))
    return {
        "id": _str(corridor.get("id")),
        "component": "走廊/交通空间",
        "category": "horizontal_circulation",
        "semantic_kind": "horizontal_circulation",
        "min_width_m": min_width_m,
        "min_width_text": _format_m(min_width_m),
        "metric_text": _format_m(min_width_m),
        "bbox_text": _format_bbox(corridor.get("bbox")),
        "confidence": confidence,
        "confidence_band": _confidence_band(confidence, uncertain=uncertain),
        "uncertain": uncertain,
        "evidence_source": "graph",
    }


def _stair_row(stair: Mapping[str, Any]) -> dict[str, Any]:
    tread_width_m = _float(stair.get("tread_width_m"))
    riser_height_m = _float(stair.get("riser_height_m"))
    props = stair.get("properties")
    if not isinstance(props, Mapping):
        props = {}
    flight_width_m = _float(props.get("flight_width_m"))
    handrail_height_m = _float(props.get("handrail_height_m"))
    well_width_m = _float(props.get("well_width_m"))
    confidence = _float(stair.get("confidence"))
    uncertain = bool(stair.get("uncertain", False))
    metric_parts = [
        f"踏步 {_format_m(tread_width_m)}" if tread_width_m is not None else "",
        f"踢面 {_format_m(riser_height_m)}" if riser_height_m is not None else "",
        f"梯段 {_format_m(flight_width_m)}" if flight_width_m is not None else "",
    ]
    return {
        "id": _str(stair.get("id")),
        "component": "楼梯/垂直交通",
        "category": "vertical_circulation",
        "semantic_kind": "stair",
        "tread_width_m": tread_width_m,
        "tread_width_text": _format_m(tread_width_m),
        "riser_height_m": riser_height_m,
        "riser_height_text": _format_m(riser_height_m),
        "flight_width_m": flight_width_m,
        "flight_width_text": _format_m(flight_width_m),
        "handrail_height_m": handrail_height_m,
        "handrail_height_text": _format_m(handrail_height_m),
        "well_width_m": well_width_m,
        "well_width_text": _format_m(well_width_m),
        "metric_text": " / ".join(part for part in metric_parts if part) or "-",
        "bbox_text": _format_bbox(stair.get("bbox")),
        "confidence": confidence,
        "confidence_band": _confidence_band(confidence, uncertain=uncertain),
        "uncertain": uncertain,
        "evidence_source": "graph_or_schedule",
    }


def _vertical_circulation_hint_rows(
    pages: Sequence[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    rows: list[Mapping[str, Any]] = []
    for page_index, page in enumerate(pages):
        if not isinstance(page, Mapping):
            continue
        for raw_text in _list(page.get("texts")):
            if not isinstance(raw_text, Mapping):
                continue
            label = _str(raw_text.get("text")).strip()
            kind = _vertical_circulation_kind(label)
            if kind is None:
                continue
            confidence = 0.70 if kind == "stair_keyword" else 0.62
            rows.append(
                {
                    "id": f"vertical-text-{len(rows) + 1}",
                    "component": "楼梯/垂直交通",
                    "category": "vertical_circulation",
                    "semantic_kind": "stair",
                    "label": label,
                    "label_zh": (
                        "楼梯方向标注"
                        if kind == "stair_direction"
                        else "楼梯文字标注"
                    ),
                    "metric_text": f"文本提示 {label}",
                    "bbox_text": _format_bbox(raw_text.get("bbox")),
                    "page_index": page_index,
                    "confidence": confidence,
                    "confidence_band": _confidence_band(confidence, uncertain=True),
                    "uncertain": True,
                    "evidence_source": "text_hint",
                }
            )
    return rows


def _vertical_circulation_kind(text: str) -> str | None:
    normalized = text.strip().upper()
    compact = normalized.strip(" .:-_")
    if compact in {"UP", "DN", "DOWN"}:
        return "stair_direction"
    if "楼梯" in text:
        return "stair_keyword"
    words = set(re.findall(r"[A-Z]+", normalized))
    if words & {"STAIR", "STAIRS", "STAIRWAY"}:
        return "stair_keyword"
    return None


def _text_inventory(pages: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    room_counts: dict[str, int] = {}
    opening_size_counts: dict[str, int] = {}
    major_dimension_texts: list[str] = []
    seen_dimensions: set[str] = set()
    for text in _text_values(pages):
        room_kind = _room_text_kind(text)
        if room_kind is not None:
            room_counts[room_kind] = room_counts.get(room_kind, 0) + 1
        opening_size = _opening_size_label(text)
        if opening_size is not None:
            opening_size_counts[opening_size] = opening_size_counts.get(opening_size, 0) + 1
        dimension = _major_dimension_text(text)
        if dimension is not None and dimension not in seen_dimensions:
            seen_dimensions.add(dimension)
            major_dimension_texts.append(dimension)
    return {
        "room_label_counts": room_counts,
        "door_or_opening_size_label_counts": opening_size_counts,
        "major_dimension_texts": major_dimension_texts,
    }


def _text_values(pages: Sequence[Mapping[str, Any]]) -> list[str]:
    values: list[str] = []
    for page in pages:
        for raw_text in _list(page.get("texts")):
            if isinstance(raw_text, Mapping):
                text = _str(raw_text.get("text")).strip()
                if text:
                    values.append(text)
    return values


def _clean_label(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().upper()).strip(" .")


def _room_text_kind(text: str) -> str | None:
    compact = _clean_label(text)
    if re.fullmatch(r"BEDROOM(?:\s*#\d+)?", compact):
        return "bedroom"
    aliases = {
        "卧室": "bedroom",
        "LIVING": "living",
        "客厅": "living",
        "DINING": "dining",
        "餐厅": "dining",
        "KITCHEN": "kitchen",
        "厨房": "kitchen",
        "BATH": "bath",
        "卫生间": "bath",
        "WALK-IN": "walk_in",
        "WIC": "walk_in",
        "CLOSET": "closet",
        "BALCONY": "balcony",
        "阳台": "balcony",
        "FOYER": "foyer",
        "COMMON": "common",
        "STUDY": "study",
        "书房": "study",
        "MECH": "mech",
        "CLT": "clt",
        "LIN": "linen",
        "LINEN": "linen",
    }
    return aliases.get(compact)


def _opening_size_label(text: str) -> str | None:
    compact = _clean_label(text)
    if re.fullmatch(r"(?:SLD)?\d{4}", compact):
        return compact
    return None


def _major_dimension_text(text: str) -> str | None:
    label = text.strip()
    if "=" in label:
        return None
    match = re.fullmatch(r"(\d+)'-\d+\"", label)
    if match is None:
        return None
    if int(match.group(1)) < 4:
        return None
    return label


def _dimension_row(dim: Mapping[str, Any]) -> dict[str, Any]:
    value_m = _float(dim.get("value_m"))
    confidence = _float(dim.get("confidence"))
    uncertain = bool(dim.get("uncertain", False))
    return {
        "id": _str(dim.get("id")),
        "category": "dimension",
        "semantic_kind": "dimension_annotation",
        "text": _str(dim.get("text")),
        "value_m": value_m,
        "value_text": _format_m(value_m),
        "metric_text": _format_m(value_m),
        "bbox_text": _format_bbox(dim.get("bbox")),
        "confidence": confidence,
        "confidence_band": _confidence_band(confidence, uncertain=uncertain),
        "uncertain": uncertain,
        "evidence_source": "graph",
    }


def _component_inventory(
    *,
    spaces: Sequence[Mapping[str, Any]],
    openings: Sequence[Mapping[str, Any]],
    circulation: Sequence[Mapping[str, Any]],
    vertical_circulation: Sequence[Mapping[str, Any]],
    graph_dimensions: Sequence[Mapping[str, Any]],
    ocr_dimensions: list[Any],
    limit: int,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in [*spaces, *openings, *circulation, *vertical_circulation, *graph_dimensions]:
        out.append(_inventory_row(row))
    for idx, raw in enumerate(ocr_dimensions):
        if isinstance(raw, Mapping):
            out.append(
                {
                    "id": f"ocr-dim-{idx + 1}",
                    "category": "dimension",
                    "semantic_kind": "ocr_dimension",
                    "label": _str(raw.get("text")),
                    "label_zh": _str(raw.get("text")),
                    "metric_text": _str(raw.get("value_text"))
                    or _format_m(_float(raw.get("value_m"))),
                    "confidence_band": _confidence_band(_float(raw.get("confidence"))),
                    "evidence_source": "ocr",
                    "bbox_text": _str(raw.get("bbox_text")),
                    "uncertain": not bool(raw.get("target_id")),
                }
            )
    return out[:limit]


def _inventory_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": _str(row.get("id")),
        "category": _str(row.get("category")),
        "semantic_kind": _str(row.get("semantic_kind")),
        "label": _str(row.get("label")) or _str(row.get("text")) or _str(row.get("component")),
        "label_zh": _str(row.get("label_zh")) or _str(row.get("component")),
        "metric_text": _str(row.get("metric_text")),
        "confidence_band": _str(row.get("confidence_band")),
        "evidence_source": _str(row.get("evidence_source")),
        "bbox_text": _str(row.get("bbox_text")),
        "uncertain": bool(row.get("uncertain", False)),
    }


def _drawing_profile(
    *,
    rooms: list[Mapping[str, Any]],
    doors: list[Mapping[str, Any]],
    corridors: list[Mapping[str, Any]],
    stairs: list[Mapping[str, Any]],
    dimensions: list[Mapping[str, Any]],
    n_lines: int,
    n_texts: int,
    ocr_diagnostics: Mapping[str, Any],
) -> dict[str, Any]:
    signals: list[str] = []
    room_labels = {
        label
        for room in rooms
        if isinstance((label := room.get("label")), str) and label
    }
    if rooms:
        signals.append("spatial_layout")
    if room_labels & RESIDENTIAL_LABELS:
        signals.append("residential_room_labels")
    if doors:
        signals.append("openings")
    if corridors:
        signals.append("horizontal_circulation")
    if stairs:
        signals.append("vertical_circulation")
    if dimensions or _int(ocr_diagnostics.get("dimension_text_count")):
        signals.append("dimension_evidence")
    if _int(ocr_diagnostics.get("text_count")):
        signals.append("ocr_text")

    if rooms and doors and ("dimension_evidence" in signals):
        level = "layout_with_dimensions"
    elif rooms or doors or corridors or stairs:
        level = "component_inventory"
    elif n_lines or n_texts:
        level = "raw_drawing_signals"
    else:
        level = "insufficient_evidence"
    return {
        "understanding_level": level,
        "evidence_signals": signals,
        "review_note": "识别档案用于衡量图纸内容理解, 不是规范判定。",
    }


def _benchmark_signals(
    *,
    rooms: list[Mapping[str, Any]],
    doors: list[Mapping[str, Any]],
    corridors: list[Mapping[str, Any]],
    stairs: list[Mapping[str, Any]],
    dimensions: list[Mapping[str, Any]],
    ocr_diagnostics: Mapping[str, Any],
) -> dict[str, bool]:
    return {
        "has_spatial_layout": bool(rooms),
        "has_openings": bool(doors),
        "has_horizontal_circulation": bool(corridors),
        "has_vertical_circulation": bool(stairs),
        "has_dimension_evidence": bool(
            dimensions or _int(ocr_diagnostics.get("dimension_text_count"))
        ),
        "has_ocr_text": bool(_int(ocr_diagnostics.get("text_count"))),
    }


def _uncertainty_flags(
    *,
    rooms: list[Mapping[str, Any]],
    doors: list[Mapping[str, Any]],
    corridors: list[Mapping[str, Any]],
    stairs: list[Mapping[str, Any]],
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
    if any(bool(stair.get("uncertain", False)) for stair in stairs):
        flags.append("楼梯/垂直交通缺少可靠几何锚点, 位置与构造细节需人工核对。")
    if not dimensions and not _int(ocr_diagnostics.get("dimension_text_count")):
        flags.append("未识别到尺寸证据, 尺寸相关判断只能依赖几何估计。")
    qa_count = _int(ocr_diagnostics.get("qa_candidate_count"))
    if qa_count:
        flags.append(f"OCR label QA 候选: {qa_count} 条, 房间用途需复核。")
    return flags


def _list(raw: object) -> list[Any]:
    return raw if isinstance(raw, list) else []


def _mapping_list(raw: object) -> list[Mapping[str, Any]]:
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, Mapping)]


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


def _confidence_band(value: float | None, *, uncertain: bool = False) -> str:
    if value is None or value <= 0:
        return "external_or_unknown" if uncertain else "unknown"
    if value >= 0.80 and not uncertain:
        return "high"
    if value >= 0.60:
        return "medium"
    return "low"


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
