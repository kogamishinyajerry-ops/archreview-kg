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
    write_handoff_reviewer_signoff,
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
    assert (package_dir / "artifacts" / "sheet_issue_review_queue.json").exists()
    assert (package_dir / "artifacts" / "review_diff.json").exists()

    summary = (package_dir / "handoff_summary.md").read_text("utf-8")
    assert "# ArchReview-KG Handoff Package" in summary
    assert "Missing Required Artifacts" in summary
    assert "None" in summary
    assert "sheet_issue_review_queue.json" in summary
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
    assert item_statuses["required_artifacts_present"] == "pass"

    markdown = (package_dir / "handoff_manager_checklist.md").read_text("utf-8")
    assert "# Handoff Manager Checklist" in markdown
    assert "manager_ready" in markdown
    assert "handoff_quality_ready" in markdown

    html = (package_dir / "index.html").read_text("utf-8")
    assert "handoff_manager_checklist.v1" in html
    assert "manager_ready" in html
    assert "manager-a" in html


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
    html = (package_dir / "index.html").read_text("utf-8")
    assert "manager_needs_info" in html
    assert "manager-b" in html


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
    packages = {row["package_name"]: row for row in payload["packages"]}
    assert packages["pkg-ready"]["package_status"] == "package_ready"
    assert packages["pkg-ready"]["archive_verification_status"] == "archive_verified"
    assert packages["pkg-ready"]["index_path"] == "pkg-ready/index.html"
    assert packages["pkg-blocked"]["package_status"] == "package_blocked"
    assert packages["pkg-blocked"]["missing_required_artifacts"] == [
        "rule_input_readiness.json"
    ]
    assert "required artifact missing" in " ".join(packages["pkg-blocked"]["open_items"])
    assert not (package_ready / "handoff_bundle_index.json").exists()
    assert not (package_blocked / "handoff_bundle_index.json").exists()


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
    assert payload["packages"][0]["quality_status"] == "not_run"
    markdown = (packages_root / "handoff_bundle_index.md").read_text("utf-8")
    assert "ArchReview-KG Handoff Bundle Index" in markdown
    assert "run handoff-check" in markdown
    html = (packages_root / "handoff_bundle_index.html").read_text("utf-8")
    assert "ArchReview-KG Handoff Bundle" in html
    assert "pkg-a/index.html" in html
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
