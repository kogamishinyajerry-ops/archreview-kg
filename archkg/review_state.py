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


class ReviewStateUpdateError(RuntimeError):
    pass


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


def normalize_review_status(raw: str | None) -> IssueReviewStatus:
    status = (raw or "candidate").strip().lower() or "candidate"
    if status == "open":
        return "candidate"
    if status not in REVIEW_STATUS_ORDER:
        raise ReviewStateUpdateError(f"invalid review status '{raw}'")
    return status


def update_review_state_issue(
    run_dir: Path,
    issue_id: str,
    *,
    status: str,
    reviewer: str | None = None,
    note: str | None = None,
    superseded_by_run_id: str | None = None,
    now: str | None = None,
) -> IssueReviewState:
    """Update one primary issue's human review state.

    The operation is intentionally bounded to issue IDs present in the run's
    primary ``issues.json``. Per-sheet preview issues remain advisory and are
    not eligible for this lifecycle update path.
    """

    if not run_dir.is_dir():
        raise ReviewStateUpdateError(f"not a directory: {run_dir}")
    issues_path = run_dir / "issues.json"
    if not issues_path.exists():
        raise ReviewStateUpdateError(f"missing {issues_path}")
    try:
        raw_issues = json.loads(issues_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ReviewStateUpdateError(f"could not read {issues_path}: {exc}") from exc
    if not isinstance(raw_issues, list):
        raise ReviewStateUpdateError(f"{issues_path} must contain a JSON list")

    issues = [item for item in raw_issues if isinstance(item, Mapping)]
    issue_ids = {_issue_string(item, "issue_id") for item in issues}
    if issue_id not in issue_ids:
        raise ReviewStateUpdateError(
            f"issue_id '{issue_id}' is not present in primary issues.json"
        )

    normalized_status = normalize_review_status(status)
    if normalized_status == "superseded" and not superseded_by_run_id:
        raise ReviewStateUpdateError(
            "superseded status requires --superseded-by-run-id"
        )
    if normalized_status != "superseded" and superseded_by_run_id:
        raise ReviewStateUpdateError(
            "--superseded-by-run-id may only be used when status=superseded"
        )

    timestamp = now or utc_now_iso()
    review_state_path = run_dir / REVIEW_STATE_FILENAME
    review_state = build_review_state(
        issues,
        run_id=run_dir.name,
        existing=load_review_state_optional(review_state_path),
        now=timestamp,
    )
    items_by_id = review_state_by_issue_id(review_state)
    item = items_by_id[issue_id]
    update: dict[str, Any] = {
        "status": normalized_status,
        "updated_at": timestamp,
        "superseded_by_run_id": superseded_by_run_id
        if normalized_status == "superseded"
        else None,
    }
    if reviewer is not None:
        update["reviewer"] = reviewer or None
    if note is not None:
        update["note"] = note or None
    items_by_id[issue_id] = item.model_copy(update=update)
    ordered_items = [items_by_id[item.issue_id] for item in review_state.items]
    updated_state = review_state.model_copy(update={"items": ordered_items})
    updated_state = with_updated_summary(updated_state)
    write_review_state(updated_state, review_state_path)
    return updated_state


def _issue_string(issue: Any, key: str) -> str:
    if isinstance(issue, Mapping):
        value = issue.get(key)
    else:
        value = getattr(issue, key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"issue missing string field '{key}'")
    return value
