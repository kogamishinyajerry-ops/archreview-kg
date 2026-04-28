from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from archkg.cli.main import app
from archkg.viewer.handoff_bundle import (
    build_handoff_bundle_index,
)
from archkg.viewer.handoff_package import (
    build_handoff_package_quality,
    write_handoff_archive_manifest,
    write_handoff_archive_verification,
    write_handoff_manager_checklist,
    write_handoff_package,
    write_handoff_package_quality_json,
    write_handoff_package_quality_markdown,
    write_handoff_ready_runbook,
    write_handoff_reviewer_signoff,
    write_handoff_reviewer_task_checklist_update,
)


def test_handoff_package_copies_review_artifacts_without_mutating_run(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run"
    package_dir = tmp_path / "handoff"
    _write_minimal_run(run_dir)
    original_issues = (run_dir / "issues.json").read_text("utf-8")

    manifest_path = write_handoff_package(run_dir, package_dir)

    assert manifest_path == package_dir / "handoff_manifest.json"
    assert not (run_dir / "handoff_manifest.json").exists()
    assert (run_dir / "issues.json").read_text("utf-8") == original_issues

    manifest = json.loads(manifest_path.read_text("utf-8"))
    assert manifest["schema_version"] == "handoff_package.v1"
    assert manifest["read_only"] is True
    assert manifest["mutation_policy"] == "copy_artifacts_only_no_source_run_mutation"
    assert manifest["missing_required_artifacts"] == []
    assert "preview_id" in " ".join(manifest["boundary_warnings"])
    assert "archkg review-state" in " ".join(manifest["boundary_warnings"])
    assert (package_dir / "handoff_summary.md").exists()
    assert (package_dir / "artifacts" / "reviewer_quickstart.md").exists()
    assert (package_dir / "artifacts" / "reviewer_task_sequence.json").exists()
    assert (package_dir / "artifacts" / "reviewer_task_sequence.md").exists()
    assert (package_dir / "artifacts" / "reviewer_task_checklist.json").exists()
    assert (package_dir / "artifacts" / "reviewer_task_checklist.md").exists()
    assert (package_dir / "artifacts" / "sheet_issue_review_queue.json").exists()
    assert (package_dir / "artifacts" / "review_diff.json").exists()
    assert (package_dir / "handoff_ready_runbook.json").exists()
    assert (package_dir / "handoff_ready_runbook.md").exists()

    summary = (package_dir / "handoff_summary.md").read_text("utf-8")
    assert "# ArchReview-KG Handoff Package" in summary
    assert "Missing Required Artifacts" in summary
    assert "None" in summary
    assert "sheet_issue_review_queue.json" in summary
    assert "reviewer_task_checklist.md" in summary
    assert "preview ids are not primary issue ids" in summary


def test_handoff_package_records_missing_required_artifacts(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    package_dir = tmp_path / "handoff"
    _write_minimal_run(run_dir)
    (run_dir / "rule_input_readiness.json").unlink()

    write_handoff_package(run_dir, package_dir)

    manifest = json.loads((package_dir / "handoff_manifest.json").read_text("utf-8"))
    assert manifest["missing_required_artifacts"] == ["rule_input_readiness.json"]
    statuses = {row["artifact"]: row for row in manifest["artifact_statuses"]}
    assert statuses["rule_input_readiness.json"]["status"] == "missing"
    assert statuses["rule_input_readiness.json"]["required"] is True


def test_handoff_package_cli_writes_package(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    package_dir = tmp_path / "handoff"
    _write_minimal_run(run_dir)

    result = CliRunner().invoke(
        app,
        ["handoff-package", str(run_dir), "-o", str(package_dir)],
    )

    assert result.exit_code == 0, result.output
    assert "handoff_package.v1" in result.output
    assert "missing_required=0" in result.output
    assert (package_dir / "handoff_manifest.json").exists()
    assert (package_dir / "handoff_summary.md").exists()


def test_handoff_package_writes_static_index_for_novice_review(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run"
    package_dir = tmp_path / "handoff"
    _write_minimal_run(run_dir)
    original_issues = (run_dir / "issues.json").read_text("utf-8")

    write_handoff_package(run_dir, package_dir)

    index_path = package_dir / "index.html"
    assert index_path.exists()
    assert not (run_dir / "index.html").exists()
    assert (run_dir / "issues.json").read_text("utf-8") == original_issues

    html = index_path.read_text("utf-8")
    assert "ArchReview-KG Handoff Review" in html
    assert "handoff_package.v1" in html
    assert "copy_artifacts_only_no_source_run_mutation" in html
    assert "href=\"handoff_summary.md\"" in html
    assert "href=\"handoff_ready_runbook.md\"" in html
    assert "href=\"artifacts/reviewer_quickstart.md\"" in html
    assert "href=\"artifacts/issues.json\"" in html
    assert "preview ids are not primary issue ids" in html


def test_handoff_package_copies_multi_page_preview_assets(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    package_dir = tmp_path / "handoff"
    _write_minimal_run(run_dir)
    preview_manifest = {
        "schema_version": "preview_pages.v1",
        "available": True,
        "page_count": 2,
        "layers": {
            "source": [
                {"page_index": 0, "src": "source_preview.png"},
                {"page_index": 1, "src": "source_preview_page_2.png"},
            ],
            "annotated": [
                {"page_index": 0, "src": "annotated_preview.png"},
                {"page_index": 1, "src": "annotated_preview_page_2.png"},
            ],
            "overlay": [
                {"page_index": 0, "src": "entity_overlay.png"},
                {"page_index": 1, "src": "entity_overlay_page_2.png"},
            ],
        },
    }
    (run_dir / "preview_pages.json").write_text(
        json.dumps(preview_manifest, ensure_ascii=False),
        encoding="utf-8",
    )
    (run_dir / "index.html").write_text(
        (
            '<a href="preview_pages.json">preview</a>'
            '<img src="source_preview_page_2.png">'
            '<img src="annotated_preview_page_2.png">'
            '<img src="entity_overlay_page_2.png">'
        ),
        encoding="utf-8",
    )
    for name in (
        "source.pdf",
        "source_preview.png",
        "source_preview_page_2.png",
        "annotated_preview.png",
        "annotated_preview_page_2.png",
        "entity_overlay.png",
        "entity_overlay_page_2.png",
    ):
        (run_dir / name).write_bytes(b"preview")

    write_handoff_package(run_dir, package_dir)

    artifacts_dir = package_dir / "artifacts"
    for name in (
        "source.pdf",
        "preview_pages.json",
        "source_preview.png",
        "source_preview_page_2.png",
        "annotated_preview.png",
        "annotated_preview_page_2.png",
        "entity_overlay.png",
        "entity_overlay_page_2.png",
    ):
        assert (artifacts_dir / name).exists(), f"missing copied visual asset: {name}"

    manifest = json.loads((package_dir / "handoff_manifest.json").read_text("utf-8"))
    statuses = {row["artifact"]: row for row in manifest["artifact_statuses"]}
    assert statuses["preview_pages.json"]["status"] == "available"
    assert statuses["source_preview_page_2.png"]["status"] == "available"
    assert statuses["annotated_preview_page_2.png"]["status"] == "available"
    assert statuses["entity_overlay_page_2.png"]["status"] == "available"
    assert "source_preview_page_2.png" in manifest["included_artifacts"]
    assert "entity_overlay_page_2.png" in manifest["included_artifacts"]

    quality = build_handoff_package_quality(package_dir)
    assert quality["status"] == "handoff_ready"
    assert quality["checks"]["copied_artifacts_exist"]["passed"] is True


def test_handoff_package_blocks_missing_manifest_preview_asset(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    package_dir = tmp_path / "handoff"
    _write_minimal_run(run_dir)
    preview_manifest = {
        "schema_version": "preview_pages.v1",
        "available": True,
        "page_count": 2,
        "layers": {
            "source": [
                {"page_index": 0, "src": "source_preview.png"},
                {"page_index": 1, "src": "source_preview_page_2.png"},
            ],
            "annotated": [],
            "overlay": [],
        },
    }
    (run_dir / "preview_pages.json").write_text(
        json.dumps(preview_manifest),
        encoding="utf-8",
    )
    (run_dir / "source_preview.png").write_bytes(b"preview")

    write_handoff_package(run_dir, package_dir)

    manifest = json.loads((package_dir / "handoff_manifest.json").read_text("utf-8"))
    assert "source_preview_page_2.png" in manifest["missing_required_artifacts"]
    quality = build_handoff_package_quality(package_dir)
    assert quality["status"] == "not_ready"
    assert "required artifact missing: source_preview_page_2.png" in quality["blockers"]


def test_handoff_package_quality_gate_accepts_complete_package(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    package_dir = tmp_path / "handoff"
    _write_minimal_run(run_dir)
    write_handoff_package(run_dir, package_dir)

    quality = build_handoff_package_quality(package_dir)

    assert quality["schema_version"] == "handoff_package_quality.v1"
    assert quality["status"] == "handoff_ready"
    assert quality["blockers"] == []
    assert quality["checks"]["manifest_schema"]["passed"] is True
    assert quality["checks"]["required_artifacts_present"]["passed"] is True
    assert quality["checks"]["copied_artifacts_exist"]["passed"] is True
    assert quality["checks"]["boundary_warnings_present"]["passed"] is True
    assert quality["checks"]["read_only_policy"]["passed"] is True

    out_json = write_handoff_package_quality_json(
        quality,
        package_dir / "handoff_quality.json",
    )
    out_md = write_handoff_package_quality_markdown(
        quality,
        package_dir / "handoff_quality.md",
    )
    assert out_json.exists()
    markdown = out_md.read_text("utf-8")
    assert "# ArchReview-KG Handoff Package Quality" in markdown
    assert "handoff_ready" in markdown
    assert "manifest_schema" in markdown


def test_handoff_package_quality_gate_blocks_missing_required_copy(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run"
    package_dir = tmp_path / "handoff"
    _write_minimal_run(run_dir)
    write_handoff_package(run_dir, package_dir)
    (package_dir / "artifacts" / "issues.json").unlink()

    quality = build_handoff_package_quality(package_dir)

    assert quality["status"] == "not_ready"
    assert "copied artifact missing: issues.json" in quality["blockers"]
    assert quality["checks"]["copied_artifacts_exist"]["passed"] is False


def test_handoff_package_quality_cli_writes_reports(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    package_dir = tmp_path / "handoff"
    _write_minimal_run(run_dir)
    write_handoff_package(run_dir, package_dir)
    out = tmp_path / "quality.json"
    markdown = tmp_path / "quality.md"

    result = CliRunner().invoke(
        app,
        [
            "handoff-check",
            str(package_dir),
            "--out",
            str(out),
            "--markdown",
            str(markdown),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "handoff-check status=handoff_ready" in result.output
    assert out.exists()
    assert markdown.exists()


def test_handoff_package_quality_cli_fails_not_ready(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    package_dir = tmp_path / "handoff"
    _write_minimal_run(run_dir)
    write_handoff_package(run_dir, package_dir)
    (package_dir / "artifacts" / "issues.json").unlink()

    result = CliRunner().invoke(app, ["handoff-check", str(package_dir)])

    assert result.exit_code == 1
    assert "handoff-check status=not_ready" in result.output


def test_handoff_reviewer_signoff_writes_package_only_notes(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    package_dir = tmp_path / "handoff"
    _write_minimal_run(run_dir)
    write_handoff_package(run_dir, package_dir)
    original_issues = (run_dir / "issues.json").read_text("utf-8")

    signoff_path = write_handoff_reviewer_signoff(
        package_dir,
        reviewer="reviewer-a",
        status="needs_info",
        note="Need section height evidence before confirmation.",
        blockers=["missing section height"],
        needs_info=["door type schedule"],
        next_actions=["request section sheet"],
    )

    assert signoff_path == package_dir / "reviewer_signoff.json"
    assert (package_dir / "reviewer_signoff.md").exists()
    assert (run_dir / "issues.json").read_text("utf-8") == original_issues
    assert not (run_dir / "reviewer_signoff.json").exists()

    payload = json.loads(signoff_path.read_text("utf-8"))
    assert payload["schema_version"] == "handoff_reviewer_signoff.v1"
    assert payload["mutation_policy"] == "package_note_only_no_source_run_mutation"
    assert payload["reviewer"] == "reviewer-a"
    assert payload["status"] == "needs_info"
    assert payload["blockers"] == ["missing section height"]
    assert payload["needs_info"] == ["door type schedule"]
    assert payload["next_actions"] == ["request section sheet"]
    assert "not a compliance certificate" in payload["boundary_warning"]

    markdown = (package_dir / "reviewer_signoff.md").read_text("utf-8")
    assert "# Handoff Reviewer Signoff" in markdown
    assert "reviewer-a" in markdown
    assert "needs_info" in markdown
    assert "missing section height" in markdown


def test_handoff_reviewer_signoff_cli_writes_notes(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    package_dir = tmp_path / "handoff"
    _write_minimal_run(run_dir)
    write_handoff_package(run_dir, package_dir)

    result = CliRunner().invoke(
        app,
        [
            "handoff-signoff",
            str(package_dir),
            "--reviewer",
            "reviewer-b",
            "--status",
            "ready",
            "--note",
            "Ready for manager review.",
            "--next-action",
            "archive package",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "handoff_reviewer_signoff.v1" in result.output
    assert "status=ready" in result.output
    assert (package_dir / "reviewer_signoff.json").exists()
    assert (package_dir / "reviewer_signoff.md").exists()


def test_handoff_reviewer_task_checklist_update_is_package_local(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run"
    package_dir = tmp_path / "handoff"
    _write_minimal_run(run_dir)
    write_handoff_package(run_dir, package_dir)
    original_run_checklist = (run_dir / "reviewer_task_checklist.json").read_text(
        "utf-8"
    )

    checklist_path = write_handoff_reviewer_task_checklist_update(
        package_dir,
        ordinal=1,
        reviewer="reviewer-check",
        status="done",
        note="Checked quickstart and package boundary.",
        evidence_checked=["handoff_manifest.json", "reviewer_quickstart.md"],
    )

    assert checklist_path == package_dir / "artifacts" / "reviewer_task_checklist.json"
    assert (run_dir / "reviewer_task_checklist.json").read_text("utf-8") == original_run_checklist
    payload = json.loads(checklist_path.read_text("utf-8"))
    item = payload["items"][0]
    assert payload["mutation_policy"] == "package_checklist_update_only_no_source_run_mutation"
    assert payload["last_update"]["ordinal"] == 1
    assert item["reviewer"] == "reviewer-check"
    assert item["reviewer_status"] == "done"
    assert item["reviewer_note"] == "Checked quickstart and package boundary."
    assert item["evidence_checked"] == [
        "handoff_manifest.json",
        "reviewer_quickstart.md",
    ]
    assert item["completed_at"]

    markdown = (package_dir / "artifacts" / "reviewer_task_checklist.md").read_text(
        "utf-8"
    )
    assert "[x]" in markdown
    assert "reviewer_quickstart.md" in markdown
    assert "Checked quickstart and package boundary." in markdown
    html = (package_dir / "index.html").read_text("utf-8")
    assert "Reviewer Task Checklist" in html
    assert "1/1 done" in html


def test_handoff_reviewer_task_checklist_update_cli_writes_item(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run"
    package_dir = tmp_path / "handoff"
    _write_minimal_run(run_dir)
    write_handoff_package(run_dir, package_dir)

    result = CliRunner().invoke(
        app,
        [
            "handoff-checklist-update",
            str(package_dir),
            "--ordinal",
            "1",
            "--reviewer",
            "reviewer-cli",
            "--status",
            "needs_info",
            "--note",
            "Need missing section evidence.",
            "--evidence-checked",
            "rule_input_readiness.json",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "reviewer_task_checklist.v1" in result.output
    assert "reviewer=reviewer-cli" in result.output
    assert "status=needs_info" in result.output
    payload = json.loads(
        (package_dir / "artifacts" / "reviewer_task_checklist.json").read_text(
            "utf-8"
        )
    )
    assert payload["items"][0]["reviewer_status"] == "needs_info"
    assert payload["items"][0]["completed_at"] == ""
    assert payload["items"][0]["evidence_checked"] == ["rule_input_readiness.json"]
    html = (package_dir / "index.html").read_text("utf-8")
    assert "checklist_needs_info" in html


def test_handoff_static_index_surfaces_quality_and_signoff(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    package_dir = tmp_path / "handoff"
    _write_minimal_run(run_dir)
    write_handoff_package(run_dir, package_dir)

    quality_result = CliRunner().invoke(
        app,
        [
            "handoff-check",
            str(package_dir),
            "--out",
            str(package_dir / "handoff_quality.json"),
            "--markdown",
            str(package_dir / "handoff_quality.md"),
        ],
    )
    assert quality_result.exit_code == 0, quality_result.output

    signoff_result = CliRunner().invoke(
        app,
        [
            "handoff-signoff",
            str(package_dir),
            "--reviewer",
            "reviewer-c",
            "--status",
            "needs_info",
            "--note",
            "Need section height evidence before confirmation.",
            "--blocker",
            "missing section height",
        ],
    )
    assert signoff_result.exit_code == 0, signoff_result.output

    html = (package_dir / "index.html").read_text("utf-8")
    assert "handoff_package_quality.v1" in html
    assert "handoff_ready" in html
    assert "handoff_reviewer_signoff.v1" in html
    assert "reviewer-c" in html
    assert "needs_info" in html
    assert "missing section height" in html
    assert "not a compliance certificate" in html


def test_handoff_manager_checklist_writes_package_only_export(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run"
    package_dir = tmp_path / "handoff"
    _write_minimal_run(run_dir)
    write_handoff_package(run_dir, package_dir)
    original_issues = (run_dir / "issues.json").read_text("utf-8")
    quality = build_handoff_package_quality(package_dir)
    write_handoff_package_quality_json(quality, package_dir / "handoff_quality.json")
    write_handoff_package_quality_markdown(quality, package_dir / "handoff_quality.md")
    write_handoff_reviewer_signoff(
        package_dir,
        reviewer="reviewer-d",
        status="ready",
        note="Ready for manager intake.",
    )
    write_handoff_reviewer_task_checklist_update(
        package_dir,
        ordinal=1,
        reviewer="reviewer-d",
        status="done",
        note="Checklist complete.",
        evidence_checked=["handoff_manifest.json"],
    )

    checklist_path = write_handoff_manager_checklist(
        package_dir,
        manager="manager-a",
        note="Accept package for review queue.",
    )

    assert checklist_path == package_dir / "handoff_manager_checklist.json"
    assert (package_dir / "handoff_manager_checklist.md").exists()
    assert (run_dir / "issues.json").read_text("utf-8") == original_issues
    assert not (run_dir / "handoff_manager_checklist.json").exists()

    payload = json.loads(checklist_path.read_text("utf-8"))
    assert payload["schema_version"] == "handoff_manager_checklist.v1"
    assert payload["mutation_policy"] == "package_checklist_only_no_source_run_mutation"
    assert payload["manager"] == "manager-a"
    assert payload["status"] == "manager_ready"
    assert payload["source_run_dir"] == str(run_dir.resolve())
    assert payload["summary"]["quality_status"] == "handoff_ready"
    assert payload["summary"]["signoff_status"] == "ready"
    assert "not a compliance certificate" in payload["boundary_warning"]
    item_statuses = {item["id"]: item["status"] for item in payload["checklist_items"]}
    assert item_statuses["handoff_quality_ready"] == "pass"
    assert item_statuses["reviewer_signoff_ready"] == "pass"
    assert item_statuses["reviewer_task_checklist_complete"] == "pass"
    assert item_statuses["required_artifacts_present"] == "pass"
    assert payload["summary"]["reviewer_checklist_status"] == "checklist_complete"
    assert payload["summary"]["reviewer_checklist_open_item_count"] == 0

    markdown = (package_dir / "handoff_manager_checklist.md").read_text("utf-8")
    assert "# Handoff Manager Checklist" in markdown
    assert "manager_ready" in markdown
    assert "handoff_quality_ready" in markdown
    assert "Reviewer checklist" in markdown

    html = (package_dir / "index.html").read_text("utf-8")
    assert "handoff_manager_checklist.v1" in html
    assert "manager_ready" in html
    assert "manager-a" in html


def test_handoff_manager_checklist_needs_info_for_open_reviewer_checklist(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run"
    package_dir = tmp_path / "handoff"
    _write_minimal_run(run_dir)
    write_handoff_package(run_dir, package_dir)
    quality = build_handoff_package_quality(package_dir)
    write_handoff_package_quality_json(quality, package_dir / "handoff_quality.json")
    write_handoff_package_quality_markdown(quality, package_dir / "handoff_quality.md")
    write_handoff_reviewer_signoff(
        package_dir,
        reviewer="reviewer-open",
        status="ready",
        note="Ready except checklist confirmation.",
    )

    checklist_path = write_handoff_manager_checklist(
        package_dir,
        manager="manager-open",
        note="Hold until reviewer checklist is closed.",
    )

    payload = json.loads(checklist_path.read_text("utf-8"))
    assert payload["status"] == "manager_needs_info"
    assert payload["summary"]["quality_status"] == "handoff_ready"
    assert payload["summary"]["signoff_status"] == "ready"
    assert payload["summary"]["reviewer_checklist_status"] == "checklist_open"
    assert payload["summary"]["reviewer_checklist_open_item_count"] == 1
    item_statuses = {item["id"]: item["status"] for item in payload["checklist_items"]}
    assert item_statuses["handoff_quality_ready"] == "pass"
    assert item_statuses["reviewer_signoff_ready"] == "pass"
    assert item_statuses["reviewer_task_checklist_complete"] == "needs_info"
    assert any("reviewer checklist checklist_open" in item for item in payload["open_items"])
    html = (package_dir / "index.html").read_text("utf-8")
    assert "manager_needs_info" in html
    assert "reviewer checklist checklist_open" in html


def test_handoff_manager_checklist_blocks_for_blocked_reviewer_checklist(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run"
    package_dir = tmp_path / "handoff"
    _write_minimal_run(run_dir)
    write_handoff_package(run_dir, package_dir)
    _write_package_checklist(
        package_dir,
        [
            {
                "stage": "evidence",
                "title": "Need source drawing sheet confirmation",
                "status": "blocked",
            }
        ],
    )
    quality = build_handoff_package_quality(package_dir)
    write_handoff_package_quality_json(quality, package_dir / "handoff_quality.json")
    write_handoff_package_quality_markdown(quality, package_dir / "handoff_quality.md")
    write_handoff_reviewer_signoff(
        package_dir,
        reviewer="reviewer-blocked",
        status="ready",
        note="Ready except blocked checklist row.",
    )

    checklist_path = write_handoff_manager_checklist(
        package_dir,
        manager="manager-blocked",
        note="Block until source sheet is attached.",
    )

    payload = json.loads(checklist_path.read_text("utf-8"))
    assert payload["status"] == "manager_blocked"
    assert payload["summary"]["reviewer_checklist_status"] == "checklist_blocked"
    assert payload["summary"]["reviewer_checklist_blocked_item_count"] == 1
    item_statuses = {item["id"]: item["status"] for item in payload["checklist_items"]}
    assert item_statuses["reviewer_task_checklist_complete"] == "fail"
    assert any("reviewer checklist checklist_blocked" in item for item in payload["open_items"])


def test_handoff_manager_checklist_cli_writes_needs_info(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    package_dir = tmp_path / "handoff"
    _write_minimal_run(run_dir)
    write_handoff_package(run_dir, package_dir)
    quality = build_handoff_package_quality(package_dir)
    write_handoff_package_quality_json(quality, package_dir / "handoff_quality.json")
    write_handoff_package_quality_markdown(quality, package_dir / "handoff_quality.md")
    write_handoff_reviewer_signoff(
        package_dir,
        reviewer="reviewer-e",
        status="needs_info",
        note="Need missing section.",
        blockers=["missing section"],
    )

    result = CliRunner().invoke(
        app,
        [
            "handoff-manager-checklist",
            str(package_dir),
            "--manager",
            "manager-b",
            "--note",
            "Hold until section is attached.",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "handoff_manager_checklist.v1" in result.output
    assert "status=manager_needs_info" in result.output
    assert (package_dir / "handoff_manager_checklist.json").exists()
    assert (package_dir / "handoff_manager_checklist.md").exists()

    payload = json.loads((package_dir / "handoff_manager_checklist.json").read_text("utf-8"))
    assert payload["status"] == "manager_needs_info"
    assert "reviewer signoff needs_info" in payload["open_items"]
    item_statuses = {item["id"]: item["status"] for item in payload["checklist_items"]}
    assert item_statuses["reviewer_task_checklist_complete"] == "needs_info"
    html = (package_dir / "index.html").read_text("utf-8")
    assert "manager_needs_info" in html
    assert "manager-b" in html


def test_handoff_ready_runbook_guides_open_reviewer_checklist(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run"
    package_dir = tmp_path / "handoff"
    _write_minimal_run(run_dir)
    write_handoff_package(run_dir, package_dir)
    original_issues = (run_dir / "issues.json").read_text("utf-8")

    runbook_path = write_handoff_ready_runbook(package_dir)

    assert runbook_path == package_dir / "handoff_ready_runbook.json"
    assert (package_dir / "handoff_ready_runbook.md").exists()
    assert (run_dir / "issues.json").read_text("utf-8") == original_issues
    payload = json.loads(runbook_path.read_text("utf-8"))
    assert payload["schema_version"] == "handoff_ready_runbook.v1"
    assert payload["mutation_policy"] == "package_runbook_only_no_source_run_mutation"
    assert payload["status"] == "reviewer_action_required"
    assert payload["summary"]["reviewer_checklist_status"] == "checklist_open"
    action_ids = {item["id"] for item in payload["next_actions"]}
    assert "run_handoff_quality" in action_ids
    assert "record_reviewer_signoff" in action_ids
    assert "close_checklist_1" in action_ids
    checklist_action = next(
        item for item in payload["next_actions"] if item["id"] == "close_checklist_1"
    )
    assert "archkg handoff-checklist-update" in checklist_action["command"]
    assert "--ordinal 1" in checklist_action["command"]

    markdown = (package_dir / "handoff_ready_runbook.md").read_text("utf-8")
    assert "# Handoff Ready-To-Review Runbook" in markdown
    assert "Run handoff package quality gate." in markdown
    html = (package_dir / "index.html").read_text("utf-8")
    assert "Ready-To-Review Runbook" in html
    assert "reviewer_action_required" in html


def test_handoff_ready_runbook_reports_ready_for_manager_intake(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run"
    package_dir = tmp_path / "handoff"
    _write_minimal_run(run_dir)
    write_handoff_package(run_dir, package_dir)
    quality = build_handoff_package_quality(package_dir)
    write_handoff_package_quality_json(quality, package_dir / "handoff_quality.json")
    write_handoff_package_quality_markdown(quality, package_dir / "handoff_quality.md")
    write_handoff_reviewer_signoff(
        package_dir,
        reviewer="reviewer-ready",
        status="ready",
        note="Ready for manager intake.",
    )
    write_handoff_reviewer_task_checklist_update(
        package_dir,
        ordinal=1,
        reviewer="reviewer-ready",
        status="done",
        note="Checklist complete.",
        evidence_checked=["handoff_manifest.json"],
    )
    write_handoff_manager_checklist(
        package_dir,
        manager="manager-ready",
        note="Intake ready.",
    )

    runbook_path = write_handoff_ready_runbook(package_dir)

    payload = json.loads(runbook_path.read_text("utf-8"))
    assert payload["status"] == "ready_for_manager_intake"
    assert payload["next_actions"] == []
    steps = {item["id"]: item["status"] for item in payload["required_before_manager_intake"]}
    assert steps["handoff_quality"] == "done"
    assert steps["reviewer_signoff"] == "done"
    assert steps["reviewer_task_checklist"] == "done"
    assert steps["manager_checklist"] == "done"
    html = (package_dir / "index.html").read_text("utf-8")
    assert "ready_for_manager_intake" in html


def test_handoff_ready_runbook_cli_writes_status(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    package_dir = tmp_path / "handoff"
    _write_minimal_run(run_dir)
    write_handoff_package(run_dir, package_dir)

    result = CliRunner().invoke(
        app,
        ["handoff-ready-runbook", str(package_dir)],
    )

    assert result.exit_code == 0, result.output
    assert "handoff_ready_runbook.v1" in result.output
    assert "status=reviewer_action_required" in result.output
    assert (package_dir / "handoff_ready_runbook.json").exists()
    assert (package_dir / "handoff_ready_runbook.md").exists()


def test_handoff_archive_manifest_writes_checksums_without_source_mutation(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run"
    package_dir = tmp_path / "handoff"
    _write_minimal_run(run_dir)
    write_handoff_package(run_dir, package_dir)
    original_issues = (run_dir / "issues.json").read_text("utf-8")
    quality = build_handoff_package_quality(package_dir)
    write_handoff_package_quality_json(quality, package_dir / "handoff_quality.json")
    write_handoff_package_quality_markdown(quality, package_dir / "handoff_quality.md")
    write_handoff_reviewer_signoff(
        package_dir,
        reviewer="reviewer-f",
        status="ready",
        note="Ready for manager intake.",
    )
    write_handoff_manager_checklist(
        package_dir,
        manager="manager-c",
        note="Queue it.",
    )

    archive_path = write_handoff_archive_manifest(
        package_dir,
        created_by="manager-c",
    )

    assert archive_path == package_dir / "handoff_archive_manifest.json"
    assert (package_dir / "handoff_archive_manifest.md").exists()
    assert (run_dir / "issues.json").read_text("utf-8") == original_issues
    assert not (run_dir / "handoff_archive_manifest.json").exists()

    payload = json.loads(archive_path.read_text("utf-8"))
    assert payload["schema_version"] == "handoff_archive_manifest.v1"
    assert (
        payload["mutation_policy"]
        == "package_integrity_manifest_only_no_source_run_mutation"
    )
    assert payload["created_by"] == "manager-c"
    assert payload["status"] == "archive_manifest_ready"
    assert payload["excluded_paths"] == [
        "handoff_archive_manifest.json",
        "handoff_archive_manifest.md",
        "handoff_ready_runbook.json",
        "handoff_ready_runbook.md",
        "index.html",
    ]
    paths = {entry["path"]: entry for entry in payload["files"]}
    assert "artifacts/issues.json" in paths
    assert "handoff_manifest.json" in paths
    assert "handoff_quality.json" in paths
    assert "reviewer_signoff.json" in paths
    assert "handoff_manager_checklist.json" in paths
    assert "index.html" not in paths
    assert "handoff_archive_manifest.json" not in paths
    assert "handoff_ready_runbook.json" not in paths
    assert len(paths["artifacts/issues.json"]["sha256"]) == 64
    assert paths["artifacts/issues.json"]["size_bytes"] >= 2
    assert len(payload["package_digest"]) == 64
    assert "not a compliance certificate" in payload["boundary_warning"]

    markdown = (package_dir / "handoff_archive_manifest.md").read_text("utf-8")
    assert "# Handoff Archive Manifest" in markdown
    assert "artifacts/issues.json" in markdown
    assert "package_digest" in markdown

    html = (package_dir / "index.html").read_text("utf-8")
    assert "handoff_archive_manifest.v1" in html
    assert "archive_manifest_ready" in html
    assert "handoff_archive_manifest.json" in html


def test_handoff_archive_manifest_cli_writes_manifest(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    package_dir = tmp_path / "handoff"
    _write_minimal_run(run_dir)
    write_handoff_package(run_dir, package_dir)
    quality = build_handoff_package_quality(package_dir)
    write_handoff_package_quality_json(quality, package_dir / "handoff_quality.json")
    write_handoff_package_quality_markdown(quality, package_dir / "handoff_quality.md")
    write_handoff_reviewer_signoff(
        package_dir,
        reviewer="reviewer-g",
        status="ready",
        note="Ready for transfer.",
    )
    write_handoff_manager_checklist(
        package_dir,
        manager="manager-d",
        note="Queue transfer.",
    )

    result = CliRunner().invoke(
        app,
        [
            "handoff-archive-manifest",
            str(package_dir),
            "--created-by",
            "manager-d",
            "--note",
            "Transfer package.",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "handoff_archive_manifest.v1" in result.output
    assert "files=" in result.output
    assert (package_dir / "handoff_archive_manifest.json").exists()
    assert (package_dir / "handoff_archive_manifest.md").exists()
    payload = json.loads((package_dir / "handoff_archive_manifest.json").read_text("utf-8"))
    assert payload["created_by"] == "manager-d"
    assert payload["note"] == "Transfer package."


def test_handoff_archive_verification_accepts_unchanged_package(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run"
    package_dir = tmp_path / "handoff"
    _write_minimal_run(run_dir)
    write_handoff_package(run_dir, package_dir)
    quality = build_handoff_package_quality(package_dir)
    write_handoff_package_quality_json(quality, package_dir / "handoff_quality.json")
    write_handoff_package_quality_markdown(quality, package_dir / "handoff_quality.md")
    write_handoff_reviewer_signoff(
        package_dir,
        reviewer="reviewer-h",
        status="ready",
        note="Ready.",
    )
    write_handoff_manager_checklist(
        package_dir,
        manager="manager-e",
        note="Queue transfer.",
    )
    write_handoff_archive_manifest(package_dir, created_by="manager-e")
    original_issues = (run_dir / "issues.json").read_text("utf-8")

    verification_path = write_handoff_archive_verification(package_dir)

    assert verification_path == package_dir / "handoff_archive_verification.json"
    assert (package_dir / "handoff_archive_verification.md").exists()
    assert (run_dir / "issues.json").read_text("utf-8") == original_issues
    assert not (run_dir / "handoff_archive_verification.json").exists()

    payload = json.loads(verification_path.read_text("utf-8"))
    assert payload["schema_version"] == "handoff_archive_verification.v1"
    assert payload["status"] == "archive_verified"
    assert payload["missing_files"] == []
    assert payload["changed_files"] == []
    assert payload["unexpected_files"] == []
    assert payload["checks"]["package_digest_match"]["passed"] is True
    assert payload["package_digest_expected"] == payload["package_digest_actual"]
    assert "not a compliance certificate" in payload["boundary_warning"]

    html = (package_dir / "index.html").read_text("utf-8")
    assert "handoff_archive_verification.v1" in html
    assert "archive_verified" in html
    assert "handoff_archive_verification.json" in html


def test_handoff_archive_verification_reports_checksum_drift(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    package_dir = tmp_path / "handoff"
    _write_minimal_run(run_dir)
    write_handoff_package(run_dir, package_dir)
    write_handoff_archive_manifest(package_dir, created_by="manager-f")
    (package_dir / "artifacts" / "issues.json").write_text(
        '[{"id":"mutated-after-archive"}]',
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        app,
        ["handoff-archive-verify", str(package_dir)],
    )

    assert result.exit_code == 1
    assert "archive_drift" in result.output
    payload = json.loads(
        (package_dir / "handoff_archive_verification.json").read_text("utf-8")
    )
    assert payload["status"] == "archive_drift"
    assert payload["missing_files"] == []
    changed = {item["path"]: item for item in payload["changed_files"]}
    assert "artifacts/issues.json" in changed
    assert changed["artifacts/issues.json"]["expected_sha256"] != changed[
        "artifacts/issues.json"
    ]["actual_sha256"]
    assert payload["checks"]["file_checksums_match"]["passed"] is False


def test_handoff_bundle_index_summarizes_multiple_packages_without_mutation(
    tmp_path: Path,
) -> None:
    runs_root = tmp_path / "runs"
    packages_root = tmp_path / "packages"
    runs_root.mkdir()
    packages_root.mkdir()

    run_ready = runs_root / "ready"
    package_ready = packages_root / "pkg-ready"
    _write_minimal_run(run_ready)
    write_handoff_package(run_ready, package_ready)
    _write_package_checklist(
        package_ready,
        [
            {"title": "ready evidence checked", "stage": "handoff", "status": "done"},
            {
                "title": "preview accepted as skipped",
                "stage": "per_sheet_preview",
                "status": "skipped_preview",
            },
        ],
    )
    quality = build_handoff_package_quality(package_ready)
    write_handoff_package_quality_json(
        quality,
        package_ready / "handoff_quality.json",
    )
    write_handoff_package_quality_markdown(
        quality,
        package_ready / "handoff_quality.md",
    )
    write_handoff_reviewer_signoff(
        package_ready,
        reviewer="reviewer-ready",
        status="ready",
        note="Ready for manager intake.",
    )
    write_handoff_manager_checklist(
        package_ready,
        manager="manager-ready",
        note="Ready.",
    )
    write_handoff_archive_manifest(package_ready, created_by="manager-ready")
    write_handoff_archive_verification(package_ready)

    run_blocked = runs_root / "blocked"
    package_blocked = packages_root / "pkg-blocked"
    _write_minimal_run(run_blocked)
    (run_blocked / "rule_input_readiness.json").unlink()
    write_handoff_package(run_blocked, package_blocked)
    _write_package_checklist(
        package_blocked,
        [
            {
                "title": "补齐规则输入: RC-PROJECT-META",
                "stage": "readiness",
                "status": "needs_info",
            },
            {
                "title": "复核主 issue: issue-open",
                "stage": "primary_issue_review",
                "status": "todo",
            },
        ],
    )
    blocked_quality = build_handoff_package_quality(package_blocked)
    write_handoff_package_quality_json(
        blocked_quality,
        package_blocked / "handoff_quality.json",
    )

    payload = build_handoff_bundle_index(packages_root)

    assert payload["schema_version"] == "handoff_bundle_index.v1"
    assert payload["mutation_policy"] == "bundle_index_only_no_package_mutation"
    assert payload["status"] == "bundle_blocked"
    assert payload["summary"]["package_count"] == 2
    assert payload["summary"]["ready_count"] == 1
    assert payload["summary"]["blocked_count"] == 1
    assert payload["summary"]["checklist_open_package_count"] == 1
    assert payload["summary"]["checklist_open_item_total"] == 2
    assert payload["summary"]["checklist_needs_info_item_total"] == 1
    assert payload["summary"]["next_actor_reviewer_count"] == 1
    assert payload["summary"]["next_actor_done_count"] == 1
    packages = {row["package_name"]: row for row in payload["packages"]}
    assert packages["pkg-ready"]["package_status"] == "package_ready"
    assert packages["pkg-ready"]["next_actor"] == "done"
    assert packages["pkg-ready"]["checklist_review_status"] == "checklist_complete"
    assert packages["pkg-ready"]["checklist_open_item_count"] == 0
    assert packages["pkg-ready"]["archive_verification_status"] == "archive_verified"
    assert packages["pkg-ready"]["index_path"] == "pkg-ready/index.html"
    assert packages["pkg-blocked"]["package_status"] == "package_blocked"
    assert packages["pkg-blocked"]["next_actor"] == "reviewer"
    assert packages["pkg-blocked"]["next_action_id"] == "restore_required_artifacts"
    assert packages["pkg-blocked"]["checklist_review_status"] == "checklist_needs_info"
    assert packages["pkg-blocked"]["checklist_open_item_count"] == 2
    assert "补齐规则输入" in packages["pkg-blocked"]["checklist_open_samples"][0]
    assert packages["pkg-blocked"]["missing_required_artifacts"] == [
        "rule_input_readiness.json"
    ]
    assert "required artifact missing" in " ".join(packages["pkg-blocked"]["open_items"])
    assert "complete 2 reviewer checklist items" in " ".join(payload["next_actions"])
    assert payload["next_action_queue"][0]["actor"] == "reviewer"
    assert payload["next_action_queue"][0]["action_id"] == "restore_required_artifacts"
    assert not (package_ready / "handoff_bundle_index.json").exists()
    assert not (package_blocked / "handoff_bundle_index.json").exists()


def test_handoff_bundle_index_routes_next_actor_to_manager_and_archive(
    tmp_path: Path,
) -> None:
    runs_root = tmp_path / "runs"
    packages_root = tmp_path / "packages"
    runs_root.mkdir()
    packages_root.mkdir()

    run_manager = runs_root / "manager"
    package_manager = packages_root / "pkg-manager"
    _write_minimal_run(run_manager)
    write_handoff_package(run_manager, package_manager)
    _write_package_checklist(
        package_manager,
        [{"title": "all reviewer checks closed", "stage": "handoff", "status": "done"}],
    )
    manager_quality = build_handoff_package_quality(package_manager)
    write_handoff_package_quality_json(
        manager_quality,
        package_manager / "handoff_quality.json",
    )
    write_handoff_package_quality_markdown(
        manager_quality,
        package_manager / "handoff_quality.md",
    )
    write_handoff_reviewer_signoff(
        package_manager,
        reviewer="reviewer-manager",
        status="ready",
        note="Ready for manager checklist.",
    )

    run_archive = runs_root / "archive"
    package_archive = packages_root / "pkg-archive"
    _write_minimal_run(run_archive)
    write_handoff_package(run_archive, package_archive)
    _write_package_checklist(
        package_archive,
        [{"title": "all reviewer checks closed", "stage": "handoff", "status": "done"}],
    )
    archive_quality = build_handoff_package_quality(package_archive)
    write_handoff_package_quality_json(
        archive_quality,
        package_archive / "handoff_quality.json",
    )
    write_handoff_package_quality_markdown(
        archive_quality,
        package_archive / "handoff_quality.md",
    )
    write_handoff_reviewer_signoff(
        package_archive,
        reviewer="reviewer-archive",
        status="ready",
        note="Ready for archive.",
    )
    write_handoff_manager_checklist(
        package_archive,
        manager="manager-archive",
        note="Ready for transfer.",
    )

    payload = build_handoff_bundle_index(packages_root)

    assert payload["summary"]["next_actor_manager_count"] == 1
    assert payload["summary"]["next_actor_archive_count"] == 1
    packages = {row["package_name"]: row for row in payload["packages"]}
    assert packages["pkg-manager"]["next_actor"] == "manager"
    assert packages["pkg-manager"]["next_action_id"] == "run_manager_checklist"
    assert "handoff-manager-checklist" in packages["pkg-manager"]["next_action_command"]
    assert packages["pkg-archive"]["next_actor"] == "archive"
    assert packages["pkg-archive"]["next_action_id"] == "write_archive_manifest"
    assert "handoff-archive-manifest" in packages["pkg-archive"]["next_action_command"]
    queue = {(item["package_name"], item["actor"]) for item in payload["next_action_queue"]}
    assert ("pkg-manager", "manager") in queue
    assert ("pkg-archive", "archive") in queue


def test_handoff_bundle_index_cli_writes_json_markdown_and_html(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run"
    packages_root = tmp_path / "packages"
    package_dir = packages_root / "pkg-a"
    _write_minimal_run(run_dir)
    write_handoff_package(run_dir, package_dir)

    result = CliRunner().invoke(app, ["handoff-bundle-index", str(packages_root)])

    assert result.exit_code == 0, result.output
    assert "handoff_bundle_index.v1" in result.output
    assert "status=bundle_needs_info" in result.output
    assert (packages_root / "handoff_bundle_index.json").exists()
    assert (packages_root / "handoff_bundle_index.md").exists()
    assert (packages_root / "handoff_bundle_index.html").exists()
    payload = json.loads((packages_root / "handoff_bundle_index.json").read_text("utf-8"))
    assert payload["summary"]["package_count"] == 1
    assert payload["packages"][0]["checklist_review_status"] == "checklist_open"
    assert payload["packages"][0]["next_actor"] == "reviewer"
    assert payload["packages"][0]["next_action_id"] == "run_handoff_quality"
    assert payload["packages"][0]["quality_status"] == "not_run"
    assert payload["summary"]["next_actor_reviewer_count"] == 1
    markdown = (packages_root / "handoff_bundle_index.md").read_text("utf-8")
    assert "ArchReview-KG Handoff Bundle Index" in markdown
    assert "Next Actor" in markdown
    assert "Checklist open items" in markdown
    assert "run handoff-check" in markdown
    html = (packages_root / "handoff_bundle_index.html").read_text("utf-8")
    assert "ArchReview-KG Handoff Bundle" in html
    assert "pkg-a/index.html" in html
    assert "Next Actor" in html
    assert "Checklist Open" in html
    assert "not a drawing-compliance certificate" in html


def test_handoff_bundle_index_rejects_single_package_root(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    package_dir = tmp_path / "package"
    _write_minimal_run(run_dir)
    write_handoff_package(run_dir, package_dir)

    result = CliRunner().invoke(app, ["handoff-bundle-index", str(package_dir)])

    assert result.exit_code == 2
    assert "single handoff package directory" in result.output


def _write_minimal_run(run_dir: Path) -> None:
    run_dir.mkdir()
    files = {
        "reviewer_quickstart.md": "# Quickstart\n",
        "reviewer_task_sequence.json": '{"schema_version":"reviewer_task_sequence.v1"}',
        "reviewer_task_sequence.md": "# Reviewer Task Sequence\n",
        "reviewer_task_checklist.json": (
            '{"schema_version":"reviewer_task_checklist.v1",'
            '"mutation_policy":"checklist_seed_only_no_issue_state_mutation",'
            '"items":[{"check_id":"check-001","ordinal":1,"stage":"intake",'
            '"title":"打开工作台并确认运行边界","reviewer_status":"todo",'
            '"required_evidence":["index.html"],"evidence_checked":[],'
            '"reviewer":"","completed_at":"","reviewer_note":""}]}'
        ),
        "reviewer_task_checklist.md": "# Reviewer Task Checklist\n",
        "report.md": "# Report\n",
        "review_workbench.json": '{"schema_version":"review_workbench.v1"}',
        "drawing_understanding.json": '{"schema_version":"drawing_understanding.v2"}',
        "rule_input_readiness.json": '{"schema_version":"rule_input_readiness.v1"}',
        "issues.json": "[]",
        "review_state.json": '{"schema_version":"issue_review_state.v1"}',
        "sheet_issue_review_queue.json": (
            '{"schema_version":"sheet_issue_review_queue.v1",'
            '"mutation_policy":"preview_only_no_primary_write"}'
        ),
        "review_diff.json": '{"schema_version":"review_diff.v1"}',
        "release_readiness.json": '{"schema_version":"release_readiness.v1"}',
        "release_readiness.md": "# Release Readiness\n",
    }
    for name, content in files.items():
        (run_dir / name).write_text(content, encoding="utf-8")
    (run_dir / "annotated.pdf").write_bytes(b"%PDF-1.7\n")


def _write_package_checklist(
    package_dir: Path,
    rows: list[dict[str, str]],
) -> None:
    items = [
        {
            "check_id": f"check-{index:03d}",
            "ordinal": index,
            "stage": row["stage"],
            "title": row["title"],
            "reviewer_status": row["status"],
        }
        for index, row in enumerate(rows, start=1)
    ]
    payload = {
        "schema_version": "reviewer_task_checklist.v1",
        "status": "needs_input_review",
        "items": items,
    }
    (package_dir / "artifacts" / "reviewer_task_checklist.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
