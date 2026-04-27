from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from archkg.schemas.review_state import (
    IssueReviewState,
    IssueReviewStateItem,
    IssueReviewStatus,
)

REVIEW_STATE_FILENAME = "review_state.json"

REVIEW_STATUS_ORDER: tuple[IssueReviewStatus, ...] = (
    "candidate",
    "confirmed",
    "rejected",
    "needs_info",
    "resolved",
    "superseded",
)


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def build_review_state(
    issues: Sequence[Any],
    *,
    run_id: str | None = None,
    existing: IssueReviewState | None = None,
    now: str | None = None,
) -> IssueReviewState:
    """Build the per-run human-review state layer for rule candidate issues.

    Existing state wins by ``issue_id`` so re-rendering a run does not lose
    resolved/superseded/confirmed human decisions.
    """

    timestamp = now or utc_now_iso()
    existing_by_id = review_state_by_issue_id(existing)
    items: list[IssueReviewStateItem] = []
    for issue in issues:
        issue_id = _issue_string(issue, "issue_id")
        rule_card_id = _issue_string(issue, "rule_card_id")
        preserved = existing_by_id.get(issue_id)
        if preserved is not None:
            update: dict[str, Any] = {"rule_card_id": rule_card_id}
            if preserved.updated_at is None:
                update["updated_at"] = timestamp
            items.append(preserved.model_copy(update=update))
            continue
        items.append(
            IssueReviewStateItem(
                issue_id=issue_id,
                rule_card_id=rule_card_id,
                status="candidate",
                source_run_id=run_id,
                created_at=timestamp,
                updated_at=timestamp,
            )
        )

    return IssueReviewState(
        run_id=run_id if run_id is not None else (existing.run_id if existing else None),
        generated_at=existing.generated_at if existing and existing.generated_at else timestamp,
        summary=summarize_review_state_items(items),
        items=items,
    )


def load_review_state(path: Path) -> IssueReviewState:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return IssueReviewState.model_validate(raw)


def load_review_state_optional(path: Path) -> IssueReviewState | None:
    if not path.exists():
        return None
    return load_review_state(path)


def write_review_state(state: IssueReviewState, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(state.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def review_state_by_issue_id(
    state: IssueReviewState | None,
) -> dict[str, IssueReviewStateItem]:
    if state is None:
        return {}
    return {item.issue_id: item for item in state.items}


def summarize_review_state_items(
    items: Iterable[IssueReviewStateItem],
) -> dict[IssueReviewStatus, int]:
    counts: Counter[IssueReviewStatus] = Counter(item.status for item in items)
    return {
        status: counts[status]
        for status in REVIEW_STATUS_ORDER
        if counts[status]
    }


def with_updated_summary(state: IssueReviewState) -> IssueReviewState:
    return state.model_copy(update={"summary": summarize_review_state_items(state.items)})


def _issue_string(issue: Any, key: str) -> str:
    if isinstance(issue, Mapping):
        value = issue.get(key)
    else:
        value = getattr(issue, key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"issue missing string field '{key}'")
    return value
