from __future__ import annotations

from archkg.review_diff import build_review_diff
from archkg.schemas.issue import Issue
from archkg.viewer.review_diff import build_review_diff_view, load_review_diff_view


def _issue(issue_id: str, *, measured_value: float = 1.05) -> Issue:
    return Issue.model_validate(
        {
            "issue_id": issue_id,
            "rule_card_id": "RC-CORRIDOR-WIDTH",
            "standard_clause_id": "GB50096-5.7.2",
            "entity_ids": ["corridor-runtime"],
            "bbox": [0.0, 200.0, 500.0, 252.5],
            "page_index": 0,
            "severity": "error",
            "message": "走廊净宽不足",
            "evidence": {
                "snippet": "1.05m",
                "page_index": 0,
                "measured_value": measured_value,
                "threshold_value": 1.2,
                "unit": "m",
            },
        }
    )


def test_review_diff_view_maps_after_issue_status(tmp_path) -> None:
    before = tmp_path / "before"
    after = tmp_path / "after"
    before.mkdir()
    after.mkdir()
    (before / "issues.json").write_text(
        f"[{_issue('ISS-before').model_dump_json()}]",
        encoding="utf-8",
    )
    (after / "issues.json").write_text(
        f"[{_issue('ISS-after').model_dump_json()}]",
        encoding="utf-8",
    )

    report = build_review_diff(before, after)
    view = build_review_diff_view(report)

    assert view["available"] is True
    assert view["summary_rows"][0]["status"] == "unchanged"
    assert view["summary_rows"][0]["count"] == 1
    assert view["issue_statuses"]["ISS-after"]["status"] == "unchanged"
    assert view["issue_statuses"]["ISS-after"]["status_label"] == "未变化"


def test_review_diff_view_reports_missing_artifact(tmp_path) -> None:
    view = load_review_diff_view(tmp_path)

    assert view["available"] is False
    assert "review_diff.json 暂无数据" in view["warning_text"]
