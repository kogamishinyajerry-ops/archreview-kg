from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "sheet_issue_review_queue.v1"

ALLOWED_ACTIONS: tuple[str, ...] = (
    "inspect_visual_evidence",
    "compare_with_primary_issues",
    "record_external_note",
    "request_primary_promotion_design",
)

FORBIDDEN_ACTIONS: tuple[str, ...] = (
    "Do not run archkg review-state on sheet preview ids; "
    "archkg review-state only accepts primary issues.json issue_id values.",
    "Do not auto-merge sheet_issues.json rows into primary issues.json or review_state.json.",
)

RECOMMENDED_ACTION = "inspect_then_decide_if_primary_promotion_needed"


def build_sheet_issue_review_queue(
    sheet_issues: Mapping[str, Any],
    *,
    limit_per_sheet: int = 12,
) -> dict[str, Any]:
    """Build a bounded human review bridge from sheet_issues.json.

    This artifact intentionally does not create primary issue ids and does
    not link into review_state.json. It is a stable checklist for reviewers
    to inspect per-sheet preview findings before any future promotion design.
    """

    sheets = _list_of_mappings(sheet_issues.get("sheets"))
    queue_sheets = [
        _queue_sheet(sheet, limit_per_sheet=max(0, limit_per_sheet)) for sheet in sheets
    ]
    queued_issue_count = sum(_int(sheet.get("queued_issue_count")) for sheet in queue_sheets)
    return {
        "schema_version": SCHEMA_VERSION,
        "source_artifact": "sheet_issues.json",
        "preview_only": True,
        "primary_review_state_linked": False,
        "mutation_policy": "preview_only_no_primary_write",
        "allowed_actions": list(ALLOWED_ACTIONS),
        "forbidden_actions": list(FORBIDDEN_ACTIONS),
        "recommended_action": RECOMMENDED_ACTION,
        "sheet_count": len(queue_sheets),
        "source_issue_count": _int(sheet_issues.get("issue_count")),
        "queued_issue_count": queued_issue_count,
        "sheets": queue_sheets,
        "note": (
            "Sheet Issue Review Queue is a preview-only bounded bridge for "
            "human inspection of per-sheet candidate issues; it does not mutate "
            "issues.json or review_state.json."
        ),
    }


def write_sheet_issue_review_queue(payload: Mapping[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_sheet_issue_review_queue_view(
    out_dir: Path,
    *,
    limit: int = 8,
    item_limit: int = 4,
) -> dict[str, Any]:
    path = out_dir / "sheet_issue_review_queue.json"
    if not path.exists():
        return _missing_view("sheet_issue_review_queue.json missing")
    try:
        raw = json.loads(path.read_text("utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return _missing_view(f"could not read sheet_issue_review_queue.json: {exc}")
    if not isinstance(raw, Mapping):
        return _missing_view("sheet_issue_review_queue.json is not an object")
    return build_sheet_issue_review_queue_view(raw, limit=limit, item_limit=item_limit)


def build_sheet_issue_review_queue_view(
    payload: Mapping[str, Any],
    *,
    limit: int = 8,
    item_limit: int = 4,
) -> dict[str, Any]:
    sheets = [
        _sheet_view(sheet, item_limit=max(0, item_limit))
        for sheet in _list_of_mappings(payload.get("sheets"))
    ]
    return {
        "available": True,
        "schema_version": _str(payload.get("schema_version")) or "unknown",
        "artifact_name": "sheet_issue_review_queue.json",
        "source_artifact": _str(payload.get("source_artifact")) or "sheet_issues.json",
        "preview_only": bool(payload.get("preview_only", True)),
        "primary_review_state_linked": bool(
            payload.get("primary_review_state_linked", False)
        ),
        "mutation_policy": _str(payload.get("mutation_policy")),
        "queued_issue_count": _int(payload.get("queued_issue_count")),
        "sheet_count": _int(payload.get("sheet_count")),
        "note": _str(payload.get("note")),
        "allowed_actions": _list_of_strings(payload.get("allowed_actions")),
        "forbidden_actions": _list_of_strings(payload.get("forbidden_actions")),
        "sheets": sheets[:limit],
        "omitted_sheet_count": max(0, len(sheets) - limit),
        "warning_text": (
            "preview-only bounded bridge; these preview ids are not valid "
            "review_state issue ids."
        ),
        "unavailable_reason": "",
    }


def _queue_sheet(sheet: Mapping[str, Any], *, limit_per_sheet: int) -> dict[str, Any]:
    page_index = _int(sheet.get("page_index"))
    issues = _list_of_mappings(sheet.get("issues"))
    items = [
        _queue_item(issue, page_index=page_index, ordinal=ordinal)
        for ordinal, issue in enumerate(issues[:limit_per_sheet], start=1)
    ]
    return {
        "page_index": page_index,
        "source_issue_count": _int(sheet.get("issue_count")),
        "queued_issue_count": len(items),
        "omitted_issue_count": max(0, len(issues) - len(items)),
        "items": items,
    }


def _queue_item(
    issue: Mapping[str, Any],
    *,
    page_index: int,
    ordinal: int,
) -> dict[str, Any]:
    evidence = issue.get("evidence")
    evidence_payload = dict(evidence) if isinstance(evidence, Mapping) else {}
    return {
        "preview_id": f"sheet-{page_index}-preview-{ordinal:03d}",
        "source_issue_id": _str(issue.get("issue_id")),
        "page_index": page_index,
        "rule_card_id": _str(issue.get("rule_card_id")),
        "standard_clause_id": _str(issue.get("standard_clause_id")),
        "severity": _str(issue.get("severity")) or "info",
        "message": _str(issue.get("message")),
        "entity_ids": _list_of_strings(issue.get("entity_ids")),
        "bbox": issue.get("bbox"),
        "evidence": {
            "snippet": _str(evidence_payload.get("snippet")),
            "measured_value": evidence_payload.get("measured_value"),
            "threshold_value": evidence_payload.get("threshold_value"),
            "unit": evidence_payload.get("unit"),
        },
        "allowed_actions": list(ALLOWED_ACTIONS),
        "recommended_action": RECOMMENDED_ACTION,
    }


def _sheet_view(sheet: Mapping[str, Any], *, item_limit: int) -> dict[str, Any]:
    items = [_item_view(item) for item in _list_of_mappings(sheet.get("items"))]
    return {
        "page_index": _int(sheet.get("page_index")),
        "source_issue_count": _int(sheet.get("source_issue_count")),
        "queued_issue_count": _int(sheet.get("queued_issue_count")),
        "omitted_issue_count": _int(sheet.get("omitted_issue_count")),
        "items": items[:item_limit],
        "omitted_item_count": max(0, len(items) - item_limit),
    }


def _item_view(item: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "preview_id": _str(item.get("preview_id")),
        "source_issue_id": _str(item.get("source_issue_id")),
        "rule_card_id": _str(item.get("rule_card_id")),
        "standard_clause_id": _str(item.get("standard_clause_id")),
        "severity": _str(item.get("severity")),
        "message": _str(item.get("message")),
        "recommended_action": _str(item.get("recommended_action")),
    }


def _missing_view(reason: str) -> dict[str, Any]:
    return {
        "available": False,
        "schema_version": "missing",
        "artifact_name": "sheet_issue_review_queue.json",
        "source_artifact": "sheet_issues.json",
        "preview_only": True,
        "primary_review_state_linked": False,
        "mutation_policy": "preview_only_no_primary_write",
        "queued_issue_count": 0,
        "sheet_count": 0,
        "note": "",
        "allowed_actions": list(ALLOWED_ACTIONS),
        "forbidden_actions": list(FORBIDDEN_ACTIONS),
        "sheets": [],
        "omitted_sheet_count": 0,
        "warning_text": (
            "sheet_issue_review_queue.json unavailable; per-sheet preview issues "
            "still must not be written to primary review_state.json."
        ),
        "unavailable_reason": reason,
    }


def _list_of_mappings(raw: object) -> list[Mapping[str, Any]]:
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes, bytearray)):
        return []
    return [item for item in raw if isinstance(item, Mapping)]


def _list_of_strings(raw: object) -> list[str]:
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes, bytearray)):
        return []
    return [item for item in raw if isinstance(item, str)]


def _str(raw: object) -> str:
    return raw if isinstance(raw, str) else ""


def _int(raw: object) -> int:
    if isinstance(raw, bool):
        return int(raw)
    if isinstance(raw, int):
        return raw
    if isinstance(raw, float):
        return int(raw)
    return 0


__all__ = [
    "ALLOWED_ACTIONS",
    "FORBIDDEN_ACTIONS",
    "SCHEMA_VERSION",
    "build_sheet_issue_review_queue",
    "build_sheet_issue_review_queue_view",
    "load_sheet_issue_review_queue_view",
    "write_sheet_issue_review_queue",
]
