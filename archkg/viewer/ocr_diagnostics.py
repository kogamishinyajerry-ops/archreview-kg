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

from archkg.graph.builder import LABEL_KEYWORDS

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

    rows: list[dict[str, Any]] = []
    qa_candidates: list[dict[str, Any]] = []
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
        room_label = _room_label(room)
        if room is not None:
            bound_room_count += 1

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
    rooms = graph.get("rooms")
    if not isinstance(rooms, list):
        return []
    return [room for room in rooms if isinstance(room, Mapping)]


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


def _float(raw: object, *, default: float) -> float:
    if isinstance(raw, (int, float, str)):
        try:
            return float(raw)
        except ValueError:
            return default
    return default


__all__ = ["build_ocr_diagnostics"]
