from __future__ import annotations

from pathlib import Path

from archkg.viewer.reviewer_task_sequence import (
    build_reviewer_task_sequence,
    load_reviewer_task_sequence_view,
    render_reviewer_task_sequence_markdown,
    write_reviewer_task_sequence_json,
)


def test_reviewer_task_sequence_prioritizes_blockers_and_open_issues(
    tmp_path: Path,
) -> None:
    payload = build_reviewer_task_sequence(
        run_dir=tmp_path,
        source_pdf=Path("sample.pdf"),
        mode="full",
        review_workbench={
            "summary": {
                "plan_sheet_count": 2,
                "sheet_graph_count": 2,
            }
        },
        rule_readiness={
            "rules": [
                {
                    "rule_id": "RC-PROJECT-META",
                    "status": "missing_input",
                    "source": "project_meta",
                    "severity": "error",
                    "missing_inputs": ["height_class"],
                    "reason": "project_meta is absent",
                },
                {"rule_id": "RC-READY", "status": "ready"},
            ]
        },
        issues=[
            {
                "issue_id": "issue-confirmed",
                "rule_card_id": "RC-OK",
                "standard_clause_id": "GB-X",
                "entity_ids": ["room-1"],
                "page_index": 0,
                "severity": "error",
                "message": "already confirmed elsewhere",
            },
            {
                "issue_id": "issue-open",
                "rule_card_id": "RC-ERR",
                "standard_clause_id": "GB-Y",
                "entity_ids": ["door-1"],
                "page_index": 1,
                "severity": "error",
                "message": "door width below threshold",
                "bbox": [10.0, 10.0, 30.0, 30.0],
            },
        ],
        review_state={
            "items": [
                {"issue_id": "issue-confirmed", "status": "confirmed"},
                {"issue_id": "issue-open", "status": "candidate"},
            ]
        },
        sheet_issue_review_queue={
            "sheets": [
                {
                    "page_index": 1,
                    "queued_issue_count": 2,
                    "items": [
                        {"preview_id": "sheet-1-preview-001"},
                        {"preview_id": "sheet-1-preview-002"},
                    ],
                }
            ]
        },
    )

    stages = [task["stage"] for task in payload["tasks"]]
    assert stages.index("readiness") < stages.index("primary_issue_review")
    assert stages.index("primary_issue_review") < stages.index("per_sheet_preview")
    assert payload["status"] == "needs_input_review"
    assert payload["summary"]["blocked_input_task_count"] == 1
    assert payload["summary"]["primary_issue_task_count"] == 1
    assert payload["summary"]["preview_sheet_task_count"] == 1
    assert "issue-open" in {task["issue_id"] for task in payload["tasks"]}
    assert "issue-confirmed" not in {task["issue_id"] for task in payload["tasks"]}
    preview_task = next(
        task for task in payload["tasks"] if task["stage"] == "per_sheet_preview"
    )
    assert preview_task["status"] == "preview_only"
    assert "sheet-1-preview-001" in preview_task["evidence"]["preview_id_samples"]
    markdown = render_reviewer_task_sequence_markdown(payload)
    assert "Reviewer Task Sequence" in markdown
    assert "补齐规则输入" in markdown


def test_reviewer_task_sequence_load_view_degrades_when_missing(
    tmp_path: Path,
) -> None:
    missing = load_reviewer_task_sequence_view(tmp_path)

    assert missing["available"] is False
    assert "reviewer_task_sequence.json missing" in missing["unavailable_reason"]

    payload = build_reviewer_task_sequence(
        run_dir=tmp_path,
        source_pdf=Path("sample.pdf"),
        mode="inspect_only",
        review_workbench={},
        issues=[],
    )
    write_reviewer_task_sequence_json(payload, tmp_path / "reviewer_task_sequence.json")

    view = load_reviewer_task_sequence_view(tmp_path, limit=2)
    assert view["available"] is True
    assert view["tasks"][0]["stage"] == "intake"
    assert view["omitted_task_count"] == max(0, len(payload["tasks"]) - 2)
