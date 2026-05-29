"""OCR evidence diagnostics for viewer result pages.

The OCR bridge is intentionally a beta capability. This module turns
raw OCR ``TextPrimitive`` entries plus the emitted entity graph into a
small, auditable payload: how many OCR texts exist, how many look
low-confidence, and which room polygon each text falls inside.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from shapely.geometry import Point, Polygon

from archkg.graph.builder import (
    CORRIDOR_KEYWORDS,
    DIM_VALUE_RE,
    DOOR_KEYWORDS,
    LABEL_KEYWORDS,
)

LOW_CONFIDENCE_THRESHOLD = 0.70
HIGH_CONFIDENCE_LABEL_THRESHOLD = 0.85
MAX_OCR_ROWS = 12


def build_ocr_diagnostics(
    primitives: Mapping[str, Any],
    graph: Mapping[str, Any],
    *,
    low_confidence_threshold: float = LOW_CONFIDENCE_THRESHOLD,
    high_confidence_label_threshold: float = HIGH_CONFIDENCE_LABEL_THRESHOLD,
    limit: int = MAX_OCR_ROWS,
) -> dict[str, Any]:
    """Return a template-friendly OCR evidence summary.

    The function accepts already-serialized ``primitives.json`` and
    ``entity_graph.json`` mappings so both Studio's pre-render path and
    ``archkg viewer``'s standalone re-render path can use exactly the
    same diagnostics.
    """
    ocr_texts = _ocr_texts(primitives)
    rooms = _rooms(graph)
    doors = _entities(graph, "doors")
    corridors = _entities(graph, "corridors")
    ppm = _points_per_meter(primitives, graph)

    rows: list[dict[str, Any]] = []
    qa_candidates: list[dict[str, Any]] = []
    dimension_rows: list[dict[str, Any]] = []
    low_confidence_count = 0
    bound_room_count = 0
    label_conflict_count = 0
    unbound_high_confidence_label_count = 0
    low_confidence_label_count = 0
    for text in ocr_texts:
        confidence = _float(text.get("confidence"), default=0.0)
        is_low_confidence = confidence < low_confidence_threshold
        if is_low_confidence:
            low_confidence_count += 1

        room = _find_room_for_text(text, rooms)
        bbox = _bbox(text.get("bbox"))
        raw_text = str(text.get("text") or "")
        normalized_label = _classify_label(raw_text)
        dimension_value_m = _dimension_value_m(raw_text)
        room_label = _room_label(room)
        if room is not None:
            bound_room_count += 1

        if dimension_value_m is not None:
            dimension_rows.append(
                _dimension_row(
                    text,
                    raw_text=raw_text,
                    value_m=dimension_value_m,
                    confidence=confidence,
                    bbox=bbox,
                    doors=doors,
                    corridors=corridors,
                    ppm=ppm,
                )
            )

        if normalized_label is not None:
            candidate_base = {
                "text": raw_text,
                "normalized_label": normalized_label,
                "confidence": confidence,
                "confidence_pct": confidence * 100.0,
                "bbox": bbox,
                "bbox_text": _format_bbox(bbox),
                "room_id": room.get("id") if room is not None else None,
                "room_label": room_label,
            }
            if room_label is not None and room_label != normalized_label:
                label_conflict_count += 1
                qa_candidates.append(
                    candidate_base
                    | {
                        "reason_code": "label_conflict",
                        "reason": "label 冲突",
                        "detail": (
                            f"OCR label={normalized_label}, "
                            f"但绑定 Room 当前 label={room_label}。"
                        ),
                    }
                )
            if room is None and confidence >= high_confidence_label_threshold:
                unbound_high_confidence_label_count += 1
                qa_candidates.append(
                    candidate_base
                    | {
                        "reason_code": "unbound_high_confidence_label",
                        "reason": "未绑定高置信度 label",
                        "detail": "OCR 识别到支持的房间 label, 但中心点未落入任何 Room polygon。",
                    }
                )
            if is_low_confidence:
                low_confidence_label_count += 1
                qa_candidates.append(
                    candidate_base
                    | {
                        "reason_code": "low_confidence_label",
                        "reason": "低置信度 label",
                        "detail": "OCR label 置信度低于阈值, 需人工核对后再信任 label-dependent 规则。",
                    }
                )

        if len(rows) < limit:
            rows.append(
                {
                    "text": raw_text,
                    "normalized_label": normalized_label,
                    "confidence": confidence,
                    "confidence_pct": confidence * 100.0,
                    "low_confidence": is_low_confidence,
                    "bbox": bbox,
                    "bbox_text": _format_bbox(bbox),
                    "room_id": room.get("id") if room is not None else None,
                    "room_label": room_label,
                    "binding_state": "已绑定房间" if room is not None else "未绑定",
                }
            )

    labeled_room_count = sum(
        1
        for room in rooms
        if isinstance(room.get("label"), str) and str(room.get("label")).strip()
    )
    bound_dimension_count = sum(1 for row in dimension_rows if row["target_id"])
    return {
        "text_count": len(ocr_texts),
        "displayed_count": len(rows),
        "omitted_count": max(len(ocr_texts) - len(rows), 0),
        "bound_room_count": bound_room_count,
        "unbound_count": len(ocr_texts) - bound_room_count,
        "low_confidence_count": low_confidence_count,
        "labeled_room_count": labeled_room_count,
        "low_confidence_threshold": low_confidence_threshold,
        "high_confidence_label_threshold": high_confidence_label_threshold,
        "qa_candidate_count": len(qa_candidates),
        "label_conflict_count": label_conflict_count,
        "unbound_high_confidence_label_count": unbound_high_confidence_label_count,
        "low_confidence_label_count": low_confidence_label_count,
        "qa_candidates": qa_candidates[:limit],
        "qa_omitted_count": max(len(qa_candidates) - limit, 0),
        "dimension_text_count": len(dimension_rows),
        "bound_dimension_count": bound_dimension_count,
        "unbound_dimension_count": len(dimension_rows) - bound_dimension_count,
        "dimension_rows": dimension_rows[:limit],
        "dimension_omitted_count": max(len(dimension_rows) - limit, 0),
        "rows": rows,
    }


def _ocr_texts(primitives: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    out: list[Mapping[str, Any]] = []
    pages = primitives.get("pages")
    if not isinstance(pages, list):
        return out
    for page in pages:
        if not isinstance(page, Mapping):
            continue
        texts = page.get("texts")
        if not isinstance(texts, list):
            continue
        for text in texts:
            if isinstance(text, Mapping) and text.get("source") == "ocr":
                out.append(text)
    return out


def _rooms(graph: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return _entities(graph, "rooms")


def _entities(graph: Mapping[str, Any], key: str) -> list[Mapping[str, Any]]:
    entities = graph.get(key)
    if not isinstance(entities, list):
        return []
    return [entity for entity in entities if isinstance(entity, Mapping)]


def _find_room_for_text(
    text: Mapping[str, Any],
    rooms: list[Mapping[str, Any]],
) -> Mapping[str, Any] | None:
    bbox = _bbox(text.get("bbox"))
    if bbox is None:
        return None
    cx = (bbox[0] + bbox[2]) / 2
    cy = (bbox[1] + bbox[3]) / 2
    point = Point(cx, cy)
    for room in rooms:
        polygon = room.get("polygon")
        if not isinstance(polygon, list) or len(polygon) < 3:
            continue
        try:
            if Polygon(polygon).covers(point):
                return room
        except Exception:
            continue
    return None


def _classify_label(text: str) -> str | None:
    lo = text.lower()
    for keyword, normalized in LABEL_KEYWORDS.items():
        if keyword in lo:
            return normalized
    return None


def _dimension_value_m(text: str) -> float | None:
    match = DIM_VALUE_RE.search(text)
    if match is None:
        return None
    value_m = float(match.group(1))
    if value_m >= 100:
        value_m = value_m / 1000.0
    return value_m


def _dimension_row(
    text: Mapping[str, Any],
    *,
    raw_text: str,
    value_m: float,
    confidence: float,
    bbox: tuple[float, float, float, float] | None,
    doors: list[Mapping[str, Any]],
    corridors: list[Mapping[str, Any]],
    ppm: float,
) -> dict[str, Any]:
    target = _find_dimension_target(text, doors, corridors, ppm)
    target_kind = target["kind"] if target is not None else None
    target_id = target["id"] if target is not None else None
    target_value_m = target["value_m"] if target is not None else None
    return {
        "text": raw_text,
        "value_m": value_m,
        "value_text": _format_m(value_m),
        "confidence": confidence,
        "confidence_pct": confidence * 100.0,
        "bbox": bbox,
        "bbox_text": _format_bbox(bbox),
        "target_kind": target_kind,
        "target_id": target_id,
        "target_value_m": target_value_m,
        "target_value_text": _format_m(target_value_m),
        "binding_state": f"绑定 {target_kind}" if target_kind else "未绑定尺寸实体",
    }


def _find_dimension_target(
    text: Mapping[str, Any],
    doors: list[Mapping[str, Any]],
    corridors: list[Mapping[str, Any]],
    ppm: float,
) -> dict[str, Any] | None:
    bbox = _bbox(text.get("bbox"))
    if bbox is None:
        return None
    cx = (bbox[0] + bbox[2]) / 2
    cy = (bbox[1] + bbox[3]) / 2
    raw_text = str(text.get("text") or "").lower()
    prefer_door = any(keyword in raw_text for keyword in DOOR_KEYWORDS)
    prefer_corridor = any(keyword in raw_text for keyword in CORRIDOR_KEYWORDS)

    candidates: list[dict[str, Any]] = []
    if prefer_corridor or not prefer_door:
        candidates.extend(
            _dimension_candidates(corridors, kind="Corridor", value_key="min_width_m")
        )
    if prefer_door or not prefer_corridor:
        candidates.extend(_dimension_candidates(doors, kind="Door", value_key="width_m"))

    best: dict[str, Any] | None = None
    best_dist = 1.0 * ppm
    for candidate in candidates:
        ex, ey = candidate["center"]
        dist = ((cx - ex) ** 2 + (cy - ey) ** 2) ** 0.5
        if dist < best_dist:
            best_dist = dist
            best = candidate
    return best


def _dimension_candidates(
    entities: list[Mapping[str, Any]],
    *,
    kind: str,
    value_key: str,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for entity in entities:
        bbox = _bbox(entity.get("bbox"))
        entity_id = entity.get("id")
        if bbox is None or not isinstance(entity_id, str):
            continue
        out.append(
            {
                "kind": kind,
                "id": entity_id,
                "center": ((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2),
                "value_m": _float(entity.get(value_key), default=0.0),
            }
        )
    return out


def _room_label(room: Mapping[str, Any] | None) -> str | None:
    if room is None:
        return None
    label = room.get("label")
    if not isinstance(label, str):
        return None
    stripped = label.strip()
    return stripped or None


def _bbox(raw: object) -> tuple[float, float, float, float] | None:
    if not isinstance(raw, (list, tuple)) or len(raw) != 4:
        return None
    try:
        x0, y0, x1, y1 = (float(v) for v in raw)
    except (TypeError, ValueError):
        return None
    return (x0, y0, x1, y1)


def _format_bbox(bbox: tuple[float, float, float, float] | None) -> str:
    if bbox is None:
        return "-"
    return ", ".join(f"{v:.1f}" for v in bbox)


def _format_m(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.2f} m"


def _points_per_meter(
    primitives: Mapping[str, Any],
    graph: Mapping[str, Any],
) -> float:
    raw = graph.get("points_per_meter", primitives.get("points_per_meter"))
    value = _float(raw, default=50.0)
    return value if value > 0 else 50.0


def _float(raw: object, *, default: float) -> float:
    if isinstance(raw, (int, float, str)):
        try:
            return float(raw)
        except ValueError:
            return default
    return default


__all__ = ["build_ocr_diagnostics"]
