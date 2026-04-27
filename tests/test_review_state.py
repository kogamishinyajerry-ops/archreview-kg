from __future__ import annotations

import json
from pathlib import Path

from archkg.review_state import (
    build_review_state,
    load_review_state,
    review_state_by_issue_id,
    write_review_state,
)
from archkg.schemas.review_state import IssueReviewState, IssueReviewStateItem


def _issue(issue_id: str, rule_card_id: str = "RC-CORRIDOR-WIDTH") -> dict[str, object]:
    return {
        "issue_id": issue_id,
        "rule_card_id": rule_card_id,
        "standard_clause_id": "GB50096-5.6.1",
        "entity_ids": ["corridor-1"],
        "bbox": [0.0, 0.0, 10.0, 10.0],
        "page_index": 0,
        "severity": "error",
        "message": "candidate finding",
        "evidence": {
            "snippet": "width",
            "page_index": 0,
            "measured_value": 1.05,
            "threshold_value": 1.1,
            "unit": "m",
        },
    }


def test_build_review_state_defaults_candidates_without_mutating_issues() -> None:
    issues = [_issue("ISS-1"), _issue("ISS-2", "RC-DOOR-WIDTH")]
    before = json.dumps(issues, sort_keys=True)

    state = build_review_state(issues, run_id="run-001", now="2026-04-28T10:00:00Z")

    assert state.schema_version == "issue_review_state.v1"
    assert state.run_id == "run-001"
    assert state.summary == {"candidate": 2}
    assert [item.status for item in state.items] == ["candidate", "candidate"]
    assert {item.source_run_id for item in state.items} == {"run-001"}
    assert json.dumps(issues, sort_keys=True) == before
    assert all("status" not in issue for issue in issues)


def test_review_state_round_trips_and_preserves_human_state(tmp_path: Path) -> None:
    existing = IssueReviewState(
        run_id="run-001",
        generated_at="2026-04-28T09:00:00Z",
        summary={"resolved": 1},
        items=[
            IssueReviewStateItem(
                issue_id="ISS-1",
                rule_card_id="RC-CORRIDOR-WIDTH",
                status="resolved",
                reviewer="Zhu",
                note="fixed in rev B",
                source_run_id="run-001",
                superseded_by_run_id="run-002",
                created_at="2026-04-28T09:00:00Z",
                updated_at="2026-04-28T09:30:00Z",
            )
        ],
    )

    rebuilt = build_review_state(
        [_issue("ISS-1"), _issue("ISS-2", "RC-DOOR-WIDTH")],
        run_id="run-002",
        existing=existing,
        now="2026-04-28T10:00:00Z",
    )
    by_id = review_state_by_issue_id(rebuilt)

    assert by_id["ISS-1"].status == "resolved"
    assert by_id["ISS-1"].superseded_by_run_id == "run-002"
    assert by_id["ISS-1"].note == "fixed in rev B"
    assert by_id["ISS-2"].status == "candidate"
    assert rebuilt.summary == {"candidate": 1, "resolved": 1}

    out = write_review_state(rebuilt, tmp_path / "review_state.json")
    loaded = load_review_state(out)
    assert loaded == rebuilt
