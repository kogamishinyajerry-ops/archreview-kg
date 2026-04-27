from __future__ import annotations

from pathlib import Path
from typing import Any

from archkg.review_state import (
    REVIEW_STATE_FILENAME,
    REVIEW_STATUS_ORDER,
    build_review_state,
    load_review_state_optional,
    review_state_by_issue_id,
)
from archkg.schemas.review_state import IssueReviewState, IssueReviewStateItem

STATUS_META: dict[str, dict[str, str]] = {
    "candidate": {"label": "候选", "class": "review-candidate"},
    "confirmed": {"label": "已确认", "class": "review-confirmed"},
    "rejected": {"label": "已驳回", "class": "review-rejected"},
    "needs_info": {"label": "需补信息", "class": "review-needs-info"},
    "resolved": {"label": "已解决", "class": "review-resolved"},
    "superseded": {"label": "已被替代", "class": "review-superseded"},
}


def load_review_state_view(out_dir: Path, issues: list[dict[str, Any]]) -> dict[str, Any]:
    state_path = out_dir / REVIEW_STATE_FILENAME
    state = load_review_state_optional(state_path)
    if state is None:
        fallback = build_review_state(issues, run_id=out_dir.name)
        return _view_payload(
            fallback,
            available=False,
            warning_text="review_state.json 暂无数据; 缺失复核状态不代表已确认。",
        )
    merged = build_review_state(issues, run_id=out_dir.name, existing=state)
    return _view_payload(
        merged,
        available=True,
        warning_text="规则输出保持 candidate; 人工复核状态来自 review_state.json。",
    )


def _view_payload(
    state: IssueReviewState,
    *,
    available: bool,
    warning_text: str,
) -> dict[str, Any]:
    items_by_id = review_state_by_issue_id(state)
    return {
        "available": available,
        "schema_version": state.schema_version,
        "run_id": state.run_id,
        "generated_at": state.generated_at,
        "warning_text": warning_text,
        "summary_rows": [
            {
                "status": status,
                "label": STATUS_META[status]["label"],
                "count": int(state.summary.get(status, 0)),
                "status_class": STATUS_META[status]["class"],
            }
            for status in REVIEW_STATUS_ORDER
            if state.summary.get(status, 0)
        ],
        "issue_states": {
            issue_id: _item_view(item)
            for issue_id, item in items_by_id.items()
        },
        "default_state": _item_view(
            IssueReviewStateItem(
                issue_id="",
                rule_card_id="",
                status="candidate",
            )
        ),
    }


def _item_view(item: IssueReviewStateItem) -> dict[str, Any]:
    meta = STATUS_META[item.status]
    return {
        "issue_id": item.issue_id,
        "rule_card_id": item.rule_card_id,
        "status": item.status,
        "status_label": meta["label"],
        "status_class": meta["class"],
        "reviewer": item.reviewer or "",
        "note": item.note or "",
        "source_run_id": item.source_run_id or "",
        "superseded_by_run_id": item.superseded_by_run_id or "",
        "updated_at": item.updated_at or "",
    }
