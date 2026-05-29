from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from archkg.schemas.issue import Issue
from archkg.schemas.review_diff import (
    ReviewDiffIssueRef,
    ReviewDiffItem,
    ReviewDiffReport,
    ReviewDiffStatus,
)

ISSUES_FILENAME = "issues.json"
REVIEW_DIFF_FILENAME = "review_diff.json"

STATUS_ORDER: tuple[ReviewDiffStatus, ...] = (
    "unchanged",
    "changed",
    "new",
    "resolved",
)


class ReviewDiffError(RuntimeError):
    pass


@dataclass(frozen=True)
class _TrackedIssue:
    issue: Issue
    group_key: str
    occurrence_index: int
    fingerprint: str
    fingerprint_payload: dict[str, Any]


def build_review_diff(before_run: Path, after_run: Path) -> ReviewDiffReport:
    """Compare primary issues.json candidates from two review run directories.

    The matcher intentionally ignores ``issue_id`` and graph entity IDs because
    both are generated per run. It compares only the primary ``issues.json``
    artifact; per-sheet preview issues stay advisory until explicitly promoted.
    """

    before = _index_issues(_load_issues(before_run))
    after = _index_issues(_load_issues(after_run))

    items: list[ReviewDiffItem] = []
    all_keys = sorted(set(before) | set(after))
    for key in all_keys:
        before_issue = before.get(key)
        after_issue = after.get(key)
        if before_issue is not None and after_issue is not None:
            status: ReviewDiffStatus = (
                "unchanged"
                if before_issue.fingerprint == after_issue.fingerprint
                else "changed"
            )
        elif before_issue is None:
            status = "new"
        else:
            status = "resolved"
        items.append(_build_item(status, before_issue, after_issue))

    counts: Counter[ReviewDiffStatus] = Counter(item.status for item in items)
    summary = {status: counts[status] for status in STATUS_ORDER if counts[status]}
    return ReviewDiffReport(
        before_run_id=before_run.name,
        after_run_id=after_run.name,
        before_run=str(before_run),
        after_run=str(after_run),
        summary=summary,
        items=items,
        notes=[
            (
                "issue_id and entity_ids are not used for matching because they are "
                "generated per run."
            ),
            "Only primary issues.json is compared; sheet_issues.json remains a preview artifact.",
        ],
    )


def write_review_diff(report: ReviewDiffReport, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def issue_group_key(issue: Issue) -> str:
    payload = {
        "rule_card_id": issue.rule_card_id,
        "standard_clause_id": issue.standard_clause_id,
        "page_index": issue.page_index,
    }
    return _canonical_json(payload)


def issue_fingerprint(issue: Issue) -> str:
    encoded = _canonical_json(_fingerprint_payload(issue)).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def _load_issues(run_dir: Path) -> list[Issue]:
    if not run_dir.is_dir():
        raise ReviewDiffError(f"not a directory: {run_dir}")
    path = run_dir / ISSUES_FILENAME
    if not path.exists():
        raise ReviewDiffError(f"missing {path}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ReviewDiffError(f"could not read {path}: {exc}") from exc
    if not isinstance(raw, list):
        raise ReviewDiffError(f"{path} must contain a JSON list")

    issues: list[Issue] = []
    for idx, item in enumerate(raw):
        try:
            issues.append(Issue.model_validate(item))
        except ValidationError as exc:
            raise ReviewDiffError(
                f"{path} item {idx} failed issue schema validation: {exc}"
            ) from exc
    return issues


def _index_issues(issues: Sequence[Issue]) -> dict[tuple[str, int], _TrackedIssue]:
    grouped: defaultdict[str, list[Issue]] = defaultdict(list)
    for issue in issues:
        grouped[issue_group_key(issue)].append(issue)

    indexed: dict[tuple[str, int], _TrackedIssue] = {}
    for group_key, group_issues in grouped.items():
        sorted_issues = sorted(group_issues, key=_issue_match_sort_key)
        for occurrence_index, issue in enumerate(sorted_issues):
            indexed[(group_key, occurrence_index)] = _TrackedIssue(
                issue=issue,
                group_key=group_key,
                occurrence_index=occurrence_index,
                fingerprint=issue_fingerprint(issue),
                fingerprint_payload=_fingerprint_payload(issue),
            )
    return indexed


def _build_item(
    status: ReviewDiffStatus,
    before: _TrackedIssue | None,
    after: _TrackedIssue | None,
) -> ReviewDiffItem:
    tracked = before if before is not None else after
    if tracked is None:
        raise ReviewDiffError("internal error: diff item without before or after issue")
    return ReviewDiffItem(
        status=status,
        group_key=tracked.group_key,
        occurrence_index=tracked.occurrence_index,
        fingerprint_before=before.fingerprint if before is not None else None,
        fingerprint_after=after.fingerprint if after is not None else None,
        before_issue=_issue_ref(before.issue) if before is not None else None,
        after_issue=_issue_ref(after.issue) if after is not None else None,
        changed_fields=_changed_fields(before, after) if status == "changed" else [],
    )


def _issue_ref(issue: Issue) -> ReviewDiffIssueRef:
    return ReviewDiffIssueRef(
        issue_id=issue.issue_id,
        rule_card_id=issue.rule_card_id,
        standard_clause_id=issue.standard_clause_id,
        entity_ids=list(issue.entity_ids),
        bbox=issue.bbox,
        page_index=issue.page_index,
        severity=issue.severity,
        message=issue.message,
        evidence=issue.evidence.model_dump(mode="json"),
    )


def _changed_fields(
    before: _TrackedIssue | None,
    after: _TrackedIssue | None,
) -> list[str]:
    if before is None or after is None:
        return []
    fields: list[str] = []
    if before.fingerprint_payload["bbox"] != after.fingerprint_payload["bbox"]:
        fields.append("bbox")
    for name in ("severity", "message"):
        if before.fingerprint_payload[name] != after.fingerprint_payload[name]:
            fields.append(name)
    before_evidence = before.fingerprint_payload["evidence"]
    after_evidence = after.fingerprint_payload["evidence"]
    if not isinstance(before_evidence, dict) or not isinstance(after_evidence, dict):
        if before_evidence != after_evidence:
            fields.append("evidence")
        return fields
    for name in ("snippet", "page_index", "measured_value", "threshold_value", "unit"):
        if before_evidence.get(name) != after_evidence.get(name):
            fields.append(f"evidence.{name}")
    return fields


def _fingerprint_payload(issue: Issue) -> dict[str, Any]:
    return {
        "rule_card_id": issue.rule_card_id,
        "standard_clause_id": issue.standard_clause_id,
        "page_index": issue.page_index,
        "bbox": _rounded_bbox(issue.bbox),
        "severity": issue.severity,
        "message": issue.message,
        "evidence": _normalized_evidence(issue.evidence.model_dump(mode="json")),
    }


def _issue_match_sort_key(issue: Issue) -> str:
    payload = {
        "bbox": _rounded_bbox(issue.bbox),
        "measured_value": _round_value(issue.evidence.measured_value),
        "threshold_value": _round_value(issue.evidence.threshold_value),
        "unit": issue.evidence.unit,
        "severity": issue.severity,
        "message": issue.message,
        "snippet": issue.evidence.snippet,
    }
    return _canonical_json(payload)


def _normalized_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in evidence.items():
        normalized[key] = _round_value(value)
    return normalized


def _rounded_bbox(
    bbox: tuple[float, float, float, float] | None,
) -> list[float] | None:
    if bbox is None:
        return None
    return [_round_float(value) for value in bbox]


def _round_value(value: Any) -> Any:
    if isinstance(value, float):
        return _round_float(value)
    return value


def _round_float(value: float) -> float:
    return round(value, 4)


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


__all__ = [
    "REVIEW_DIFF_FILENAME",
    "ReviewDiffError",
    "build_review_diff",
    "issue_fingerprint",
    "issue_group_key",
    "write_review_diff",
]
