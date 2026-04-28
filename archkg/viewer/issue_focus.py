from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def build_issue_focus_view(
    issues: Sequence[Mapping[str, Any]],
    primitives: Mapping[str, Any],
) -> dict[str, Any]:
    """Build first-page issue focus rectangles for the static viewer.

    Source/overlay previews currently render page 0 only. Focus entries are
    therefore intentionally limited to primary issues with page-0 bboxes.
    """

    page = _first_page(primitives)
    if not page:
        return _empty("missing_first_page_dimensions")
    width = _float(page.get("width_pt"))
    height = _float(page.get("height_pt"))
    if width <= 0.0 or height <= 0.0:
        return _empty("invalid_first_page_dimensions")

    items: dict[str, dict[str, Any]] = {}
    omitted = 0
    for issue in issues:
        issue_id = _str(issue.get("issue_id"))
        bbox = _bbox(issue.get("bbox"))
        page_index = _int(issue.get("page_index"))
        if not issue_id or bbox is None or page_index != 0:
            omitted += 1
            continue
        normalized = _normalize_bbox(bbox, width=width, height=height)
        if normalized is None:
            omitted += 1
            continue
        items[issue_id] = {
            "issue_id": issue_id,
            "page_index": page_index,
            "bbox": list(bbox),
            "x_pct": normalized[0],
            "y_pct": normalized[1],
            "w_pct": normalized[2],
            "h_pct": normalized[3],
            "rule_card_id": _str(issue.get("rule_card_id")),
            "severity": _str(issue.get("severity")) or "info",
        }
    return {
        "available": bool(items),
        "items": items,
        "page_index": 0,
        "page_width_pt": width,
        "page_height_pt": height,
        "omitted_count": omitted,
        "warning_text": "仅映射第一页主 issue bbox; 多页 issue 暂不映射。",
    }


def _empty(reason: str) -> dict[str, Any]:
    labels = {
        "missing_first_page_dimensions": "缺少第一页尺寸, 无法定位图面。",
        "invalid_first_page_dimensions": "第一页尺寸无效, 无法定位图面。",
    }
    return {
        "available": False,
        "items": {},
        "page_index": 0,
        "page_width_pt": 0.0,
        "page_height_pt": 0.0,
        "omitted_count": 0,
        "warning_text": labels.get(reason, reason),
    }


def _first_page(primitives: Mapping[str, Any]) -> Mapping[str, Any] | None:
    pages = primitives.get("pages")
    if not isinstance(pages, list) or not pages:
        return None
    first = pages[0]
    return first if isinstance(first, Mapping) else None


def _normalize_bbox(
    bbox: tuple[float, float, float, float],
    *,
    width: float,
    height: float,
) -> tuple[float, float, float, float] | None:
    x0, y0, x1, y1 = bbox
    left = max(0.0, min(x0, x1))
    top = max(0.0, min(y0, y1))
    right = min(width, max(x0, x1))
    bottom = min(height, max(y0, y1))
    if right <= left or bottom <= top:
        return None
    return (
        100.0 * left / width,
        100.0 * top / height,
        100.0 * (right - left) / width,
        100.0 * (bottom - top) / height,
    )


def _bbox(raw: object) -> tuple[float, float, float, float] | None:
    if not isinstance(raw, list | tuple) or len(raw) != 4:
        return None
    values = [_float(item) for item in raw]
    if any(value != value for value in values):
        return None
    return (values[0], values[1], values[2], values[3])


def _str(raw: object) -> str:
    return raw if isinstance(raw, str) else ""


def _int(raw: object) -> int:
    return raw if isinstance(raw, int) else 0


def _float(raw: object) -> float:
    if isinstance(raw, int | float):
        return float(raw)
    return float("nan")


__all__ = ["build_issue_focus_view"]
