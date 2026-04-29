from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from archkg.cli.main import app
from archkg.viewer.handoff_bundle import (
    build_handoff_bundle_index,
    write_handoff_bundle_index,
)
from archkg.viewer.handoff_package import write_handoff_package


def test_handoff_bundle_index_aggregates_opening_provenance_counts(
    tmp_path: Path,
) -> None:
    runs_root = tmp_path / "runs"
    packages_root = tmp_path / "handoff-packages"
    runs_root.mkdir()
    packages_root.mkdir()

    run_with_opening = runs_root / "with_opening"
    run_without_opening = runs_root / "without_opening"
    package_with_opening = packages_root / "pkg-with"
    package_without_opening = packages_root / "pkg-without"
    _write_minimal_run(run_with_opening)
    _write_layout_ifc_with_opening_provenance(
        run_with_opening,
        {
            "semantic_count": 4,
            "measurement_count": 2,
            "host_count": 3,
            "all_three_count": 1,
        },
    )
    write_handoff_package(run_with_opening, package_with_opening)
    _write_minimal_run(run_without_opening)
    write_handoff_package(run_without_opening, package_without_opening)

    payload = build_handoff_bundle_index(packages_root)

    assert payload["summary"]["opening_provenance_semantic_count"] == 4
    assert payload["summary"]["opening_provenance_measurement_count"] == 2
    assert payload["summary"]["opening_provenance_host_count"] == 3
    assert payload["summary"]["opening_provenance_all_three_count"] == 1
    assert payload["summary"]["opening_provenance_weak_package_count"] == 1
    rows = {row["package_name"]: row for row in payload["packages"]}
    assert rows["pkg-with"]["opening_provenance_available"] is True
    assert rows["pkg-with"]["opening_provenance_source_artifact"] == "layout_ifc_export.json"
    assert rows["pkg-with"]["opening_provenance_weak"] is False
    assert rows["pkg-without"]["opening_provenance_available"] is False
    assert rows["pkg-without"]["opening_provenance_weak"] is True


def test_handoff_bundle_index_markdown_html_show_opening_provenance_weak_notice(
    tmp_path: Path,
) -> None:
    runs_root = tmp_path / "runs"
    packages_root = tmp_path / "handoff-packages"
    runs_root.mkdir()
    packages_root.mkdir()

    run_strong = runs_root / "strong"
    run_weak = runs_root / "weak"
    package_strong = packages_root / "pkg-strong"
    package_weak = packages_root / "pkg-weak"

    _write_minimal_run(run_strong)
    _write_layout_ifc_with_opening_provenance(
        run_strong,
        {
            "semantic_count": 2,
            "measurement_count": 1,
            "host_count": 2,
            "all_three_count": 1,
        },
    )
    write_handoff_package(run_strong, package_strong)

    _write_minimal_run(run_weak)
    _write_layout_ifc_with_opening_provenance(
        run_weak,
        {
            "semantic_count": 1,
            "measurement_count": 0,
            "host_count": 1,
            "all_three_count": 0,
        },
    )
    write_handoff_package(run_weak, package_weak)

    out_json = packages_root / "handoff_bundle_index.json"
    out_md = packages_root / "handoff_bundle_index.md"
    out_html = packages_root / "handoff_bundle_index.html"
    write_handoff_bundle_index(
        packages_root,
        out=out_json,
        markdown=out_md,
        html_path=out_html,
    )
    payload = json.loads(out_json.read_text("utf-8"))

    assert payload["summary"]["opening_provenance_weak_package_count"] == 1
    assert payload["summary"]["opening_provenance_semantic_count"] == 3
    assert payload["summary"]["opening_provenance_all_three_count"] == 1

    markdown = out_md.read_text("utf-8")
    assert "Opening provenance: semantic=`3`, measurement=`1`, host_wall=`3`, all_three=`1`" in markdown
    assert "Weak opening provenance packages: `1`" in markdown
    assert "| `pkg-strong` | package_needs_info | reviewer |" in markdown
    assert "| `pkg-weak` | package_needs_info | reviewer |" in markdown

    html = out_html.read_text("utf-8")
    assert "Opening Provenance Coverage" in html
    assert "Weak opening provenance packages: 1" in html
    assert "<td>yes</td>" in html
    assert "pkg-weak" in html


def test_handoff_bundle_index_cli_writes_opening_provenance_summary(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run"
    packages_root = tmp_path / "handoff-packages"
    package_dir = packages_root / "pkg-api"
    packages_root.mkdir()
    _write_minimal_run(run_dir)
    _write_layout_ifc_with_opening_provenance(
        run_dir,
        {
            "semantic_count": 2,
            "measurement_count": 2,
            "host_count": 1,
            "all_three_count": 1,
        },
    )
    write_handoff_package(run_dir, package_dir)

    result = CliRunner().invoke(
        app,
        ["handoff-bundle-index", str(packages_root)],
    )

    assert result.exit_code == 0, result.output
    assert "handoff_bundle_index.v1" in result.output
    assert "status=bundle_needs_info" in result.output

    markdown = (packages_root / "handoff_bundle_index.md").read_text("utf-8")
    html = (packages_root / "handoff_bundle_index.html").read_text("utf-8")
    assert "Opening provenance: semantic=`2`, measurement=`2`, host_wall=`1`, all_three=`1`" in markdown
    assert "Opening Provenance Coverage" in html


def test_handoff_bundle_index_emits_opening_provenance_triage_queue(
    tmp_path: Path,
) -> None:
    runs_root = tmp_path / "runs"
    packages_root = tmp_path / "handoff-packages"
    runs_root.mkdir()
    packages_root.mkdir()

    run_strong = runs_root / "strong"
    run_weak = runs_root / "weak"
    package_strong = packages_root / "pkg-strong"
    package_weak = packages_root / "pkg-weak"
    _write_minimal_run(run_strong)
    _write_layout_ifc_with_opening_provenance(
        run_strong,
        {
            "semantic_count": 2,
            "measurement_count": 1,
            "host_count": 2,
            "all_three_count": 1,
        },
    )
    write_handoff_package(run_strong, package_strong)
    _write_minimal_run(run_weak)
    _write_layout_ifc_with_opening_provenance(
        run_weak,
        {
            "semantic_count": 1,
            "measurement_count": 0,
            "host_count": 1,
            "all_three_count": 0,
        },
    )
    write_handoff_package(run_weak, package_weak)

    payload = build_handoff_bundle_index(packages_root)

    queue = payload["opening_provenance_triage_queue"]
    assert queue == [
        {
            "package_name": "pkg-weak",
            "relative_package_dir": "pkg-weak",
            "actor": "reviewer",
            "action_id": "review_opening_provenance_coverage",
            "title": "Review weak opening provenance coverage.",
            "reason": "Opening provenance coverage is weak: missing measurement.",
            "coverage": "semantic=1, measurement=0, host_wall=1, all_three=0",
            "source_artifact": "layout_ifc_export.json",
            "boundary_warning": (
                "Opening provenance coverage is preview-only handoff guidance; "
                "missing signals are review prompts, not compliance failures."
            ),
        }
    ]
    rows = {row["package_name"]: row for row in payload["packages"]}
    assert rows["pkg-weak"]["package_status"] == "package_needs_info"
    assert rows["pkg-weak"]["next_action_id"] == "run_handoff_quality"


def test_handoff_bundle_index_markdown_html_show_opening_provenance_triage_queue(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run"
    packages_root = tmp_path / "handoff-packages"
    package_dir = packages_root / "pkg-missing-host"
    packages_root.mkdir()
    _write_minimal_run(run_dir)
    _write_layout_ifc_with_opening_provenance(
        run_dir,
        {
            "semantic_count": 3,
            "measurement_count": 1,
            "host_count": 0,
            "all_three_count": 0,
        },
    )
    write_handoff_package(run_dir, package_dir)

    out_json = packages_root / "handoff_bundle_index.json"
    out_md = packages_root / "handoff_bundle_index.md"
    out_html = packages_root / "handoff_bundle_index.html"
    write_handoff_bundle_index(
        packages_root,
        out=out_json,
        markdown=out_md,
        html_path=out_html,
    )
    payload = json.loads(out_json.read_text("utf-8"))

    assert payload["opening_provenance_triage_queue"][0]["package_name"] == (
        "pkg-missing-host"
    )
    markdown = out_md.read_text("utf-8")
    assert "## Opening Provenance Triage Queue" in markdown
    assert "| `pkg-missing-host` | reviewer | review_opening_provenance_coverage | semantic=3, measurement=1, host_wall=0, all_three=0 | Opening provenance coverage is weak: missing host_wall. |" in markdown
    assert "preview-only handoff guidance" in markdown

    html = out_html.read_text("utf-8")
    assert "Opening Provenance Triage Queue" in html
    assert "pkg-missing-host" in html
    assert "missing host_wall" in html
    assert "preview-only handoff guidance" in html


def _write_layout_ifc_with_opening_provenance(
    run_dir: Path,
    counts: dict[str, int],
) -> None:
    run_dir.joinpath("layout_ifc_export.json").write_text(
        json.dumps(
            {
                "schema_version": "layout_ifc_export.v1",
                "status": "exported",
                "opening_provenance": {
                    "semantic_count": counts["semantic_count"],
                    "measurement_count": counts["measurement_count"],
                    "host_count": counts["host_count"],
                    "all_three_count": counts["all_three_count"],
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


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
        "layout_3d.json": '{"schema_version":"layout_3d.v1"}',
        "layout_3d_summary.md": "# 3D Layout Evidence\n",
        "layout_ifc_export.json": '{"schema_version":"layout_ifc_export.v1","status":"exported"}',
        "layout_ifc_export.md": "# Layout IFC Export\n",
    }
    for name, content in files.items():
        (run_dir / name).write_text(content, encoding="utf-8")
    (run_dir / "annotated.pdf").write_bytes(b"%PDF-1.7\n")
    (run_dir / "layout_3d.glb").write_bytes(b"glb bytes")
    (run_dir / "layout.ifc").write_text("IFC preview\n", encoding="utf-8")
