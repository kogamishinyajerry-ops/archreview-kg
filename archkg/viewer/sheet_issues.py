from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_sheet_issues_view(out_dir: Path, *, limit: int = 8) -> dict[str, Any]:
    path = out_dir / "sheet_issues.json"
    if not path.exists():
        return _missing_view("sheet_issues.json missing")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return _missing_view(f"could not read sheet_issues.json: {exc}")
    if not isinstance(raw, dict):
        return _missing_view("sheet_issues.json is not an object")
    return build_sheet_issues_view(raw, limit=limit)


def build_sheet_issues_view(payload: dict[str, Any], *, limit: int = 8) -> dict[str, Any]:
    sheets = _list_of_dicts(payload.get("sheets"))
    rows = [_sheet_row(sheet) for sheet in sheets]
    return {
        "available": True,
        "schema_version": _string(payload.get("schema_version")) or "unknown",
        "artifact_name": "sheet_issues.json",
        "sheet_count": _int(payload.get("sheet_count")),
        "issue_count": _int(payload.get("issue_count")),
        "preview_only": bool(payload.get("preview_only", True)),
        "review_state_linked": bool(payload.get("review_state_linked", False)),
        "sheets": rows[:limit],
        "omitted_sheet_count": max(0, len(rows) - limit),
        "warning_text": (
            "Per-sheet issues are preview evidence only; they are not merged into "
            "primary issues.json or review_state.json in P39-02."
        ),
        "unavailable_reason": "",
    }


def _missing_view(reason: str) -> dict[str, Any]:
    return {
        "available": False,
        "schema_version": "missing",
        "artifact_name": "sheet_issues.json",
        "sheet_count": 0,
        "issue_count": 0,
        "preview_only": True,
        "review_state_linked": False,
        "sheets": [],
        "omitted_sheet_count": 0,
        "warning_text": "sheet_issues.json 暂无数据; 缺失 per-sheet issue preview 不代表多页无候选问题.",
        "unavailable_reason": reason,
    }


def _sheet_row(sheet: dict[str, Any]) -> dict[str, Any]:
    issues = _list_of_dicts(sheet.get("issues"))
    rule_ids = sorted(
        {
            rule_id
            for issue in issues
            if isinstance((rule_id := issue.get("rule_card_id")), str) and rule_id
        }
    )
    return {
        "page_index": _int(sheet.get("page_index")),
        "issue_count": _int(sheet.get("issue_count")),
        "skipped_rule_count": _int(sheet.get("skipped_rule_count")),
        "rule_ids": rule_ids[:6],
        "omitted_rule_count": max(0, len(rule_ids) - 6),
    }


def _list_of_dicts(raw: object) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    return [dict(item) for item in raw if isinstance(item, dict)]


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
