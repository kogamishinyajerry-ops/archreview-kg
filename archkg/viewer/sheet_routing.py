from __future__ import annotations

import json
from pathlib import Path
from typing import Any

MODE_LABELS = {
    "legacy_all_pages": "legacy 全页输入",
    "classified_single_plan_page": "单页 plan 路由",
}


def load_sheet_routing_view(out_dir: Path) -> dict[str, Any]:
    path = out_dir / "sheet_routing.json"
    if not path.exists():
        return _missing_view("sheet_routing.json missing")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return _missing_view(f"could not read sheet_routing.json: {exc}")
    if not isinstance(raw, dict):
        return _missing_view("sheet_routing.json is not an object")
    return build_sheet_routing_view(raw)


def build_sheet_routing_view(payload: dict[str, Any]) -> dict[str, Any]:
    mode = _string(payload.get("mode")) or "unknown"
    selected = _ints(payload.get("selected_page_indexes"))
    excluded = _ints(payload.get("excluded_page_indexes"))
    fallback_reason = _string(payload.get("fallback_reason"))
    return {
        "available": True,
        "schema_version": _string(payload.get("schema_version")) or "unknown",
        "artifact_name": "sheet_routing.json",
        "mode": mode,
        "mode_label": MODE_LABELS.get(mode, mode),
        "selected_page_indexes": selected,
        "selected_pages_text": _join_ints(selected),
        "excluded_page_indexes": excluded,
        "excluded_pages_text": _join_ints(excluded) if excluded else "无",
        "original_page_count": _int(payload.get("original_page_count")),
        "graph_page_count": _int(payload.get("graph_page_count")),
        "confidence_floor_pct": _float(payload.get("confidence_floor")) * 100.0,
        "reason": _string(payload.get("reason")) or "—",
        "fallback_reason": fallback_reason,
        "fallback_label": fallback_reason or "无",
        "manual_sheet_region_applied": bool(payload.get("manual_sheet_region_applied")),
        "warning_text": (
            "Sheet routing is protected; unknown, low-confidence, or multiple-plan runs "
            "fall back to legacy graph input."
        ),
        "unavailable_reason": "",
    }


def _missing_view(reason: str) -> dict[str, Any]:
    return {
        "available": False,
        "schema_version": "missing",
        "artifact_name": "sheet_routing.json",
        "mode": "missing",
        "mode_label": "暂无路由",
        "selected_page_indexes": [],
        "selected_pages_text": "无",
        "excluded_page_indexes": [],
        "excluded_pages_text": "无",
        "original_page_count": 0,
        "graph_page_count": 0,
        "confidence_floor_pct": 0.0,
        "reason": "",
        "fallback_reason": reason,
        "fallback_label": reason,
        "manual_sheet_region_applied": False,
        "warning_text": "sheet_routing.json 暂无数据; 缺失路由不代表已按 sheet 类型过滤.",
        "unavailable_reason": reason,
    }


def _ints(raw: object) -> list[int]:
    if not isinstance(raw, list):
        return []
    out: list[int] = []
    for item in raw:
        if isinstance(item, bool):
            continue
        if isinstance(item, int):
            out.append(item)
    return out


def _join_ints(values: list[int]) -> str:
    return ", ".join(str(value) for value in values) if values else "无"


def _string(raw: object) -> str:
    return raw if isinstance(raw, str) else ""


def _int(raw: object) -> int:
    if isinstance(raw, bool):
        return int(raw)
    if isinstance(raw, int):
        return raw
    if isinstance(raw, float):
        return int(raw)
    return 0


def _float(raw: object) -> float:
    if isinstance(raw, int | float):
        return float(raw)
    return 0.0
