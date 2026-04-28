from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from archkg.cli.main import app
from archkg.viewer.handoff_package import (
    build_handoff_package_quality,
    write_handoff_package,
    write_handoff_package_quality_json,
    write_handoff_package_quality_markdown,
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
