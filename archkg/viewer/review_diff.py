from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from archkg.schemas.review_diff import ReviewDiffItem, ReviewDiffReport, ReviewDiffStatus

STATUS_ORDER: tuple[ReviewDiffStatus, ...] = (
    "unchanged",
    "changed",
    "new",
    "resolved",
)

STATUS_LABELS: dict[ReviewDiffStatus, str] = {
    "unchanged": "未变化",
    "changed": "证据变化",
    "new": "新增",
    "resolved": "已消失",
}

STATUS_CLASSES: dict[ReviewDiffStatus, str] = {
    "unchanged": "diff-unchanged",
    "changed": "diff-changed",
    "new": "diff-new",
    "resolved": "diff-resolved",
}


def load_review_diff_view(out_dir: Path, *, limit: int = 12) -> dict[str, Any]:
    path = out_dir / "review_diff.json"
    if not path.exists():
        return _missing_view(
            "review_diff.json 暂无数据; 仅表示尚未执行 archkg review-diff, 不代表没有变化。"
        )
    try:
        raw = json.loads(path.read_text("utf-8"))
        report = ReviewDiffReport.model_validate(raw)
    except (json.JSONDecodeError, ValidationError) as exc:
        return _missing_view(f"could not read review_diff.json: {exc}")
    return build_review_diff_view(report, limit=limit)


def build_review_diff_view(
    report: ReviewDiffReport,
    *,
    limit: int = 12,
) -> dict[str, Any]:
    summary_rows = [
        {
            "status": status,
            "status_label": STATUS_LABELS[status],
            "status_class": STATUS_CLASSES[status],
            "count": int(report.summary.get(status, 0)),
        }
        for status in STATUS_ORDER
    ]

    issue_statuses: dict[str, dict[str, Any]] = {}
    item_rows: list[dict[str, Any]] = []
    resolved_items: list[dict[str, Any]] = []
    for item in report.items:
        row = _item_row(item)
        if item.after_issue is not None:
            issue_statuses[item.after_issue.issue_id] = row
        if item.status == "resolved":
            resolved_items.append(row)
        item_rows.append(row)

    return {
        "available": True,
        "artifact_name": "review_diff.json",
        "before_run_id": report.before_run_id,
        "after_run_id": report.after_run_id,
        "summary": dict(report.summary),
        "summary_rows": summary_rows,
        "issue_statuses": issue_statuses,
        "items": item_rows[:limit],
        "resolved_items": resolved_items[:limit],
        "omitted_count": max(len(item_rows) - limit, 0),
        "warning_text": (
            "review_diff.json 是只读 revision tracking; "
            "不会自动更新 review_state.json 或确认 resolved。"
        ),
        "note": (
            f"{report.before_run_id} → {report.after_run_id}; "
            "status is derived from primary issues.json only."
        ),
    }


def _item_row(item: ReviewDiffItem) -> dict[str, Any]:
    before_issue = item.before_issue
    after_issue = item.after_issue
    status = item.status
    return {
        "status": status,
        "status_label": STATUS_LABELS[status],
        "status_class": STATUS_CLASSES[status],
        "before_issue_id": before_issue.issue_id if before_issue is not None else "",
        "after_issue_id": after_issue.issue_id if after_issue is not None else "",
        "rule_card_id": _rule_card_id(item),
        "standard_clause_id": _standard_clause_id(item),
        "changed_fields": list(item.changed_fields),
    }


def _rule_card_id(item: ReviewDiffItem) -> str:
    if item.after_issue is not None:
        return item.after_issue.rule_card_id
    if item.before_issue is not None:
        return item.before_issue.rule_card_id
    return ""


def _standard_clause_id(item: ReviewDiffItem) -> str:
    if item.after_issue is not None:
        return item.after_issue.standard_clause_id
    if item.before_issue is not None:
        return item.before_issue.standard_clause_id
    return ""


def _missing_view(warning_text: str) -> dict[str, Any]:
    return {
        "available": False,
        "artifact_name": "review_diff.json",
        "before_run_id": "",
        "after_run_id": "",
        "summary": {},
        "summary_rows": [],
        "issue_statuses": {},
        "items": [],
        "resolved_items": [],
        "omitted_count": 0,
        "warning_text": warning_text,
        "note": "",
    }


__all__ = ["build_review_diff_view", "load_review_diff_view"]
