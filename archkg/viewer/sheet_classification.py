from __future__ import annotations

import json
from pathlib import Path
from typing import Any

TYPE_LABELS = {
    "plan": "平面图",
    "detail": "详图",
    "elevation": "立面/剖面",
    "schedule": "表格/排表",
    "title": "标题/封面",
    "legend": "图例/说明",
    "unknown": "未知",
}


def load_sheet_classification_view(out_dir: Path, *, limit: int = 12) -> dict[str, Any]:
    path = out_dir / "sheet_classification.json"
    if not path.exists():
        return _missing_view("sheet_classification.json missing")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return _missing_view(f"could not read sheet_classification.json: {exc}")
    if not isinstance(raw, dict):
        return _missing_view("sheet_classification.json is not an object")
    return build_sheet_classification_view(raw, limit=limit)


def build_sheet_classification_view(
    payload: dict[str, Any],
    *,
    limit: int = 12,
) -> dict[str, Any]:
    pages = _list_of_dicts(payload.get("pages"))
    rows = [_page_row(page) for page in pages]
    eligible_count = sum(1 for row in rows if row["eligible_for_graph"])
    return {
        "available": True,
        "schema_version": _string(payload.get("schema_version")) or "unknown",
        "artifact_name": "sheet_classification.json",
        "summary_rows": _summary_rows(payload.get("summary")),
        "pages": rows[:limit],
        "page_total": len(rows),
        "eligible_count": eligible_count,
        "omitted_page_count": max(0, len(rows) - limit),
        "warning_text": "Sheet classification is advisory; P38-01 does not skip pages during graph build.",
        "unavailable_reason": "",
    }


def _missing_view(reason: str) -> dict[str, Any]:
    return {
        "available": False,
        "schema_version": "missing",
        "artifact_name": "sheet_classification.json",
        "summary_rows": [],
        "pages": [],
        "page_total": 0,
        "eligible_count": 0,
        "omitted_page_count": 0,
        "warning_text": "sheet_classification.json 暂无数据; 缺失分类不代表可直接进入 graph.",
        "unavailable_reason": reason,
    }


def _page_row(page: dict[str, Any]) -> dict[str, Any]:
    sheet_type = _string(page.get("sheet_type")) or "unknown"
    return {
        "page_index": _int(page.get("page_index")),
        "sheet_type": sheet_type,
        "sheet_label": TYPE_LABELS.get(sheet_type, sheet_type),
        "confidence_pct": _float(page.get("confidence")) * 100.0,
        "eligible_for_graph": bool(page.get("eligible_for_graph")),
        "eligible_label": "graph eligible" if page.get("eligible_for_graph") else "not routed",
        "reason": _string(page.get("reason")) or "—",
        "evidence_texts": _strings(page.get("evidence_texts")),
        "line_count": _int(page.get("line_count")),
        "text_count": _int(page.get("text_count")),
    }


def _summary_rows(raw: object) -> list[dict[str, Any]]:
    if not isinstance(raw, dict):
        return []
    rows: list[dict[str, Any]] = []
    for sheet_type, count in raw.items():
        key = _string(sheet_type) or "unknown"
        rows.append(
            {
                "sheet_type": key,
                "sheet_label": TYPE_LABELS.get(key, key),
                "count": _int(count),
            }
        )
    return rows


def _list_of_dicts(raw: object) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    return [dict(item) for item in raw if isinstance(item, dict)]


def _strings(raw: object) -> list[str]:
    if not isinstance(raw, list):
        return []
    return [str(item) for item in raw if item is not None][:4]


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
