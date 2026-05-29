from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, TypedDict


class _PageDimensions(TypedDict):
    page_index: int
    page_number: int
    width_pt: float
    height_pt: float


def build_issue_focus_view(
    issues: Sequence[Mapping[str, Any]],
    primitives: Mapping[str, Any],
    *,
    preview_pages: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build sheet-aware issue focus rectangles for the static viewer.

    Source/overlay previews currently render page 0 only. Entries from other
    pages are still preserved with their page-aware normalized bbox so the UI
    can point reviewers to the correct sheet instead of projecting them onto
    the first-page preview.
    """

    pages = _page_dimensions(primitives)
    if not pages:
        return _empty("missing_first_page_dimensions")

    first_page = pages.get(0)
    first_width = first_page["width_pt"] if first_page else 0.0
    first_height = first_page["height_pt"] if first_page else 0.0

    items: dict[str, dict[str, Any]] = {}
    omitted_items: dict[str, dict[str, Any]] = {}
    omitted = 0
    for issue in issues:
        issue_id = _str(issue.get("issue_id"))
        bbox = _bbox(issue.get("bbox"))
        page_index = _int(issue.get("page_index"), default=0)
        if not issue_id:
            omitted += 1
            continue
        if bbox is None:
            omitted += 1
            omitted_items[issue_id] = _omitted_item(
                issue_id,
                page_index=page_index,
                reason="missing_bbox",
            )
            continue
        page = pages.get(page_index)
        if page is None:
            omitted += 1
            omitted_items[issue_id] = _omitted_item(
                issue_id,
                page_index=page_index,
                reason="missing_page_dimensions",
            )
            continue
        width = page["width_pt"]
        height = page["height_pt"]
        normalized = _normalize_bbox(bbox, width=width, height=height)
        if normalized is None:
            omitted += 1
            omitted_items[issue_id] = _omitted_item(
                issue_id,
                page_index=page_index,
                reason="invalid_bbox",
            )
            continue
        preview_layers = _preview_layers_for_page(preview_pages, page_index=page_index)
        items[issue_id] = {
            "issue_id": issue_id,
            "page_index": page_index,
            "page_number": page["page_number"],
            "page_label": f"第 {page['page_number']} 页",
            "page_width_pt": width,
            "page_height_pt": height,
            "preview_layer_supported": bool(preview_layers),
            "preview_layers": preview_layers,
            "bbox": list(bbox),
            "x_pct": normalized[0],
            "y_pct": normalized[1],
            "w_pct": normalized[2],
            "h_pct": normalized[3],
            "rule_card_id": _str(issue.get("rule_card_id")),
            "severity": _str(issue.get("severity")) or "info",
        }
    non_preview_page_count = sum(
        1 for item in items.values() if not bool(item.get("preview_layer_supported"))
    )
    multi_page_preview_count = sum(
        1
        for item in items.values()
        if _int(item.get("page_index"), default=0) > 0
        and bool(item.get("preview_layer_supported"))
    )
    return {
        "available": bool(items),
        "items": items,
        "omitted_items": omitted_items,
        "page_count": len(pages),
        "page_dimensions": list(pages.values()),
        "page_index": 0,
        "page_width_pt": first_width,
        "page_height_pt": first_height,
        "preview_page_index": 0,
        "non_preview_page_count": non_preview_page_count,
        "omitted_count": omitted,
        "warning_text": _warning_text(
            mapped_count=len(items),
            omitted_count=omitted,
            non_preview_page_count=non_preview_page_count,
            multi_page_preview_count=multi_page_preview_count,
        ),
    }


def _empty(reason: str) -> dict[str, Any]:
    labels = {
        "missing_first_page_dimensions": "缺少第一页尺寸, 无法定位图面。",
        "invalid_first_page_dimensions": "第一页尺寸无效, 无法定位图面。",
    }
    return {
        "available": False,
        "items": {},
        "omitted_items": {},
        "page_count": 0,
        "page_dimensions": [],
        "page_index": 0,
        "page_width_pt": 0.0,
        "page_height_pt": 0.0,
        "preview_page_index": 0,
        "non_preview_page_count": 0,
        "omitted_count": 0,
        "warning_text": labels.get(reason, reason),
    }


def _page_dimensions(primitives: Mapping[str, Any]) -> dict[int, _PageDimensions]:
    pages = primitives.get("pages")
    if not isinstance(pages, list) or not pages:
        return {}
    dimensions: dict[int, _PageDimensions] = {}
    for position, page in enumerate(pages):
        if not isinstance(page, Mapping):
            continue
        page_index = _int(page.get("page_index"), default=position)
        width = _float(page.get("width_pt"))
        height = _float(page.get("height_pt"))
        if width <= 0.0 or height <= 0.0:
            continue
        dimensions[page_index] = {
            "page_index": page_index,
            "page_number": page_index + 1,
            "width_pt": width,
            "height_pt": height,
        }
    return dict(sorted(dimensions.items()))


def _omitted_item(issue_id: str, *, page_index: int, reason: str) -> dict[str, Any]:
    return {
        "issue_id": issue_id,
        "page_index": page_index,
        "reason": reason,
    }


def _preview_layers_for_page(
    preview_pages: Mapping[str, Any] | None,
    *,
    page_index: int,
) -> list[str]:
    if preview_pages is None:
        return ["source", "overlay", "annotated"] if page_index == 0 else []
    layers = preview_pages.get("layers")
    if not isinstance(layers, Mapping):
        return ["source", "overlay", "annotated"] if page_index == 0 else []
    available_layers: list[str] = []
    for layer in ("source", "overlay", "annotated"):
        rows = layers.get(layer)
        if not isinstance(rows, list):
            continue
        if any(
            isinstance(row, Mapping)
            and _int(row.get("page_index"), default=-1) == page_index
            for row in rows
        ):
            available_layers.append(layer)
    return available_layers


def _warning_text(
    *,
    mapped_count: int,
    omitted_count: int,
    non_preview_page_count: int,
    multi_page_preview_count: int,
) -> str:
    if mapped_count <= 0:
        return "未找到可映射 issue bbox; 请检查 issue bbox/page_index 与图纸页尺寸。"
    parts = ["已按图纸页映射 issue bbox"]
    if non_preview_page_count:
        parts.append("非第一页 issue 保留页码和 bbox, 不误投射到第一页预览")
    elif multi_page_preview_count:
        parts.append("多页 issue 可在对应页预览层定位")
    else:
        parts.append("第一页 issue 可在预览层直接高亮")
    if omitted_count:
        parts.append(f"{omitted_count} 条 issue 因 bbox 或页尺寸缺失未映射")
    return "; ".join(parts) + "。"


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


def _int(raw: object, *, default: int = 0) -> int:
    return raw if isinstance(raw, int) else default


def _float(raw: object) -> float:
    if isinstance(raw, int | float):
        return float(raw)
    return float("nan")


__all__ = ["build_issue_focus_view"]
