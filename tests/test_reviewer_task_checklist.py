from __future__ import annotations

from pathlib import Path

from archkg.viewer.reviewer_task_checklist import (
    build_reviewer_task_checklist,
    load_reviewer_task_checklist_view,
    render_reviewer_task_checklist_markdown,
    write_reviewer_task_checklist_json,
)


def test_reviewer_task_checklist_derives_fillable_items_from_sequence(
    tmp_path: Path,
) -> None:
    sequence = {
        "schema_version": "reviewer_task_sequence.v1",
        "status": "needs_input_review",
        "tasks": [
            {
                "ordinal": 1,
                "task_id": "task-030-readiness-001",
                "stage": "readiness",
                "priority": 30,
                "title": "补齐规则输入: RC-PROJECT-META",
                "action": "resolve_rule_input_blocker",
                "artifact": "rule_input_readiness.json",
                "target": "#panel-readiness",
                "reason": "project_meta is absent",
                "rule_card_id": "RC-PROJECT-META",
                "status": "missing_input",
            },
            {
                "ordinal": 2,
                "task_id": "task-040-issue-001",
                "stage": "primary_issue_review",
                "priority": 40,
                "title": "复核主 issue: issue-open",
                "action": "inspect_primary_issue_and_update_review_state",
                "artifact": "issues.json / review_state.json",
                "target": "#panel-issues",
                "reason": "door width below threshold",
                "issue_id": "issue-open",
                "rule_card_id": "RC-ERR",
                "standard_clause_id": "GB-Y",
                "status": "candidate",
            },
            {
                "ordinal": 3,
                "task_id": "task-070-preview-sheet-001",
                "stage": "per_sheet_preview",
                "priority": 70,
                "title": "核对第 2 页 per-sheet preview",
                "action": "inspect_sheet_preview_without_review_state_write",
                "artifact": "sheet_issue_review_queue.json",
                "target": "#panel-sheet-issues",
                "reason": "preview_id 不能用于 archkg review-state",
                "page_index": 1,
                "status": "preview_only",
            },
        ],
    }

    payload = build_reviewer_task_checklist(
        run_dir=tmp_path,
        source_pdf=Path("sample.pdf"),
        reviewer_task_sequence=sequence,
    )

    assert payload["schema_version"] == "reviewer_task_checklist.v1"
    assert payload["status"] == "needs_input_review"
    assert payload["mutation_policy"] == "checklist_seed_only_no_issue_state_mutation"
    assert payload["summary"]["item_count"] == 3
    assert payload["summary"]["readiness_item_count"] == 1
    assert payload["summary"]["primary_issue_item_count"] == 1
    assert payload["summary"]["preview_item_count"] == 1
    readiness = payload["items"][0]
    assert readiness["reviewer_status"] == "todo"
    assert readiness["evidence_checked"] == []
    assert "rule_input_readiness.json row" in readiness["required_evidence"]
    primary = payload["items"][1]
    assert primary["issue_id"] == "issue-open"
    assert "Only archkg review-state" in primary["mutation_warning"]
    preview = payload["items"][2]
    assert preview["page_index"] == 1
    assert "Preview ids must not" in preview["mutation_warning"]

    markdown = render_reviewer_task_checklist_markdown(payload)
    assert "Reviewer Task Checklist" in markdown
    assert "Allowed reviewer_status values" in markdown
    assert "preview_id" in markdown


def test_reviewer_task_checklist_load_view_degrades_when_missing(
    tmp_path: Path,
) -> None:
    missing = load_reviewer_task_checklist_view(tmp_path)

    assert missing["available"] is False
    assert "reviewer_task_checklist.json missing" in missing["unavailable_reason"]

    payload = build_reviewer_task_checklist(
        run_dir=tmp_path,
        source_pdf=Path("sample.pdf"),
        reviewer_task_sequence={
            "schema_version": "reviewer_task_sequence.v1",
            "status": "ready_for_handoff",
            "tasks": [
                {
                    "ordinal": 1,
                    "task_id": "task-090-handoff-package",
                    "stage": "handoff",
                    "priority": 90,
                    "title": "生成只读交接包",
                    "action": "write_handoff_package",
                    "artifact": "handoff_manifest.json",
                    "target": "archkg handoff-package",
                    "reason": "copy artifacts",
                    "status": "todo",
                }
            ],
        },
    )
    write_reviewer_task_checklist_json(payload, tmp_path / "reviewer_task_checklist.json")

    view = load_reviewer_task_checklist_view(tmp_path, limit=0)
    assert view["available"] is True
    assert view["items"] == []
    assert view["omitted_item_count"] == 1
