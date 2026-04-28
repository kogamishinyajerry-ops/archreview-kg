from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from typer.testing import CliRunner

from archkg.cli.main import app
from archkg.review_diff import ReviewDiffError, build_review_diff, write_review_diff


def _issue(
    issue_id: str,
    *,
    rule_card_id: str = "RC-CORRIDOR-WIDTH",
    clause_id: str = "GB50096-5.6.1",
    entity_ids: list[str] | None = None,
    bbox: list[float] | None = None,
    page_index: int = 0,
    severity: str = "error",
    message: str = "candidate finding",
    measured_value: float | None = 1.05,
    threshold_value: float | None = 1.1,
    snippet: str = "width",
) -> dict[str, Any]:
    return {
        "issue_id": issue_id,
        "rule_card_id": rule_card_id,
        "standard_clause_id": clause_id,
        "entity_ids": entity_ids or ["corridor-1"],
        "bbox": bbox if bbox is not None else [0.0, 0.0, 10.0, 10.0],
        "page_index": page_index,
        "severity": severity,
        "message": message,
        "evidence": {
            "snippet": snippet,
            "page_index": page_index,
            "measured_value": measured_value,
            "threshold_value": threshold_value,
            "unit": "m",
        },
    }


def _write_run(path: Path, issues: list[dict[str, Any]]) -> Path:
    path.mkdir()
    (path / "issues.json").write_text(
        json.dumps(issues, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def test_review_diff_matches_same_issue_with_different_runtime_ids(
    tmp_path: Path,
) -> None:
    before = _write_run(
        tmp_path / "run-before",
        [_issue("ISS-before", entity_ids=["corridor-before"])],
    )
    after = _write_run(
        tmp_path / "run-after",
        [_issue("ISS-after", entity_ids=["corridor-after"])],
    )

    report = build_review_diff(before, after)

    assert report.schema_version == "review_diff.v1"
    assert report.mutation_policy == "read_only_primary_issues_json"
    assert report.summary == {"unchanged": 1}
    assert len(report.items) == 1
    item = report.items[0]
    assert item.status == "unchanged"
    assert item.before_issue is not None
    assert item.after_issue is not None
    assert item.before_issue.issue_id == "ISS-before"
    assert item.after_issue.issue_id == "ISS-after"
    assert item.fingerprint_before == item.fingerprint_after


def test_review_diff_marks_changed_same_group_when_evidence_changes(
    tmp_path: Path,
) -> None:
    before = _write_run(tmp_path / "run-before", [_issue("ISS-before")])
    after = _write_run(
        tmp_path / "run-after",
        [
            _issue(
                "ISS-after",
                bbox=[0.0, 0.0, 12.0, 10.0],
                measured_value=0.98,
            )
        ],
    )

    report = build_review_diff(before, after)

    assert report.summary == {"changed": 1}
    item = report.items[0]
    assert item.status == "changed"
    assert item.fingerprint_before != item.fingerprint_after
    assert item.changed_fields == ["bbox", "evidence.measured_value"]


def test_review_diff_marks_new_and_resolved_candidates(tmp_path: Path) -> None:
    before = _write_run(
        tmp_path / "run-before",
        [
            _issue("ISS-stable", entity_ids=["corridor-1"]),
            _issue("ISS-resolved", rule_card_id="RC-DOOR-WIDTH", entity_ids=["door-1"]),
        ],
    )
    after = _write_run(
        tmp_path / "run-after",
        [
            _issue("ISS-stable-new-id", entity_ids=["corridor-1"]),
            _issue(
                "ISS-new",
                rule_card_id="RC-STAIR-TREAD",
                clause_id="GB50016-6.4.11",
                entity_ids=["stair-1"],
                measured_value=0.24,
                threshold_value=0.26,
            ),
        ],
    )

    report = build_review_diff(before, after)

    assert report.summary == {"unchanged": 1, "new": 1, "resolved": 1}
    statuses = {item.status for item in report.items}
    assert statuses == {"unchanged", "new", "resolved"}
    resolved = next(item for item in report.items if item.status == "resolved")
    new = next(item for item in report.items if item.status == "new")
    assert resolved.before_issue is not None
    assert resolved.after_issue is None
    assert resolved.before_issue.issue_id == "ISS-resolved"
    assert new.before_issue is None
    assert new.after_issue is not None
    assert new.after_issue.issue_id == "ISS-new"


def test_review_diff_handles_duplicate_group_keys_by_occurrence(
    tmp_path: Path,
) -> None:
    before = _write_run(
        tmp_path / "run-before",
        [
            _issue("ISS-before-1", bbox=[0.0, 0.0, 10.0, 10.0], measured_value=1.05),
            _issue("ISS-before-2", bbox=[20.0, 0.0, 30.0, 10.0], measured_value=1.0),
        ],
    )
    after = _write_run(
        tmp_path / "run-after",
        [
            _issue("ISS-after-1", bbox=[0.0, 0.0, 10.0, 10.0], measured_value=1.05),
            _issue("ISS-after-2", bbox=[20.0, 0.0, 30.0, 10.0], measured_value=0.99),
        ],
    )

    report = build_review_diff(before, after)

    assert report.summary == {"unchanged": 1, "changed": 1}
    assert [item.occurrence_index for item in report.items] == [0, 1]
    assert [item.status for item in report.items] == ["unchanged", "changed"]


def test_review_diff_writes_json_artifact(tmp_path: Path) -> None:
    before = _write_run(tmp_path / "run-before", [_issue("ISS-before")])
    after = _write_run(tmp_path / "run-after", [_issue("ISS-after")])
    report = build_review_diff(before, after)

    out = write_review_diff(report, tmp_path / "review_diff.json")

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "review_diff.v1"
    assert payload["summary"] == {"unchanged": 1}
    assert payload["items"][0]["before_issue"]["issue_id"] == "ISS-before"


def test_review_diff_cli_smoke(tmp_path: Path) -> None:
    before = _write_run(tmp_path / "run-before", [_issue("ISS-before")])
    after = _write_run(tmp_path / "run-after", [_issue("ISS-after")])
    out = tmp_path / "diff.json"

    result = CliRunner().invoke(
        app,
        [
            "review-diff",
            str(before),
            str(after),
            "-o",
            str(out),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "unchanged=1" in result.output
    assert out.exists()


def test_review_diff_rejects_missing_primary_issues(tmp_path: Path) -> None:
    before = tmp_path / "run-before"
    before.mkdir()
    after = _write_run(tmp_path / "run-after", [_issue("ISS-after")])

    import pytest

    with pytest.raises(ReviewDiffError, match="missing"):
        build_review_diff(before, after)
