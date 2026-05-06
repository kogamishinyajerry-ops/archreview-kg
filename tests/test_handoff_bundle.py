from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from archkg.cli.main import app
from archkg.viewer.handoff_bundle import (
    build_handoff_bundle_index,
    write_handoff_bundle_index,
)
from archkg.viewer.handoff_package import (
    write_handoff_optional_guidance_note,
    write_handoff_package,
)


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


def test_handoff_bundle_index_surfaces_package_index_optional_guidance(
    tmp_path: Path,
) -> None:
    runs_root = tmp_path / "runs"
    packages_root = tmp_path / "handoff-packages"
    runs_root.mkdir()
    packages_root.mkdir()

    run_weak = runs_root / "weak"
    package_weak = packages_root / "pkg-weak"
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

    run_plain = runs_root / "plain"
    package_plain = packages_root / "pkg-plain"
    _write_minimal_run(run_plain)
    write_handoff_package(run_plain, package_plain)

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

    assert payload["summary"]["package_index_optional_guidance_package_count"] == 1
    assert payload["summary"]["package_index_optional_guidance_action_total"] == 1
    rows = {row["package_name"]: row for row in payload["packages"]}
    assert rows["pkg-weak"]["package_index_optional_guidance_available"] is True
    assert rows["pkg-weak"]["package_index_optional_guidance_count"] == 1
    assert rows["pkg-weak"]["package_index_optional_guidance_path"] == (
        "pkg-weak/index.html"
    )
    assert rows["pkg-weak"]["package_index_optional_guidance_runbook_path"] == (
        "pkg-weak/handoff_ready_runbook.md#optional-review-guidance"
    )
    assert rows["pkg-plain"]["package_index_optional_guidance_available"] is False
    assert payload["package_index_optional_guidance_queue"] == [
        {
            "package_name": "pkg-weak",
            "relative_package_dir": "pkg-weak",
            "index_path": "pkg-weak/index.html",
            "runbook_path": "pkg-weak/handoff_ready_runbook.md#optional-review-guidance",
            "action_count": 1,
            "reason": "Opening provenance coverage is weak: missing measurement.",
            "boundary_warning": (
                "Opening provenance coverage is preview-only handoff guidance; "
                "missing signals are review prompts, not compliance failures."
            ),
        }
    ]
    assert all(
        item["package_name"] != "pkg-weak" or item["action_id"] != "review_opening_provenance_guidance"
        for item in payload["next_action_queue"]
    )

    markdown = out_md.read_text("utf-8")
    assert "## Package Index Optional Guidance" in markdown
    assert "| `pkg-weak` | 1 | `pkg-weak/index.html` | `pkg-weak/handoff_ready_runbook.md#optional-review-guidance` | Opening provenance coverage is weak: missing measurement. |" in markdown

    html = out_html.read_text("utf-8")
    assert "Package Index Optional Guidance" in html
    assert "pkg-weak/index.html" in html
    assert "handoff_ready_runbook.md#optional-review-guidance" in html
    assert "missing measurement" in html


def test_handoff_bundle_index_summarizes_optional_guidance_note_closeout(
    tmp_path: Path,
) -> None:
    runs_root = tmp_path / "runs"
    packages_root = tmp_path / "handoff-packages"
    runs_root.mkdir()
    packages_root.mkdir()

    run_reviewed = runs_root / "run-reviewed"
    run_needs = runs_root / "run-needs"
    run_blocked = runs_root / "run-blocked"
    run_missing = runs_root / "run-missing"
    run_invalid = runs_root / "run-invalid"
    run_strong = runs_root / "run-strong"

    package_reviewed = packages_root / "pkg-reviewed"
    package_needs = packages_root / "pkg-needs"
    package_blocked = packages_root / "pkg-blocked"
    package_missing = packages_root / "pkg-missing"
    package_invalid = packages_root / "pkg-invalid"
    package_strong = packages_root / "pkg-strong"

    for run_dir in [
        run_reviewed,
        run_needs,
        run_blocked,
        run_missing,
        run_invalid,
    ]:
        _write_minimal_run(run_dir)
        _write_layout_ifc_with_opening_provenance(
            run_dir,
            {
                "semantic_count": 1,
                "measurement_count": 0,
                "host_count": 1,
                "all_three_count": 0,
            },
        )
    _write_minimal_run(run_strong)
    _write_layout_ifc_with_opening_provenance(
        run_strong,
        {
            "semantic_count": 2,
            "measurement_count": 2,
            "host_count": 1,
            "all_three_count": 1,
        },
    )

    write_handoff_package(run_reviewed, package_reviewed)
    write_handoff_optional_guidance_note(
        package_reviewed,
        reviewer="reviewer-reviewed",
        status="reviewed",
        note="Optional guidance reviewed.",
    )
    write_handoff_package(run_needs, package_needs)
    write_handoff_optional_guidance_note(
        package_needs,
        reviewer="reviewer-needs",
        status="needs_info",
        note="Needs further documentation.",
    )
    write_handoff_package(run_blocked, package_blocked)
    write_handoff_optional_guidance_note(
        package_blocked,
        reviewer="reviewer-blocked",
        status="blocked",
        note="Missing section labels.",
    )
    write_handoff_package(run_missing, package_missing)
    write_handoff_package(run_invalid, package_invalid)
    write_handoff_package(run_strong, package_strong)
    _write_invalid_optional_guidance_note(package_invalid)

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

    summary = payload["summary"]
    assert summary["optional_guidance_note_reviewed_count"] == 1
    assert summary["optional_guidance_note_needs_info_count"] == 1
    assert summary["optional_guidance_note_blocked_count"] == 1
    assert summary["optional_guidance_note_not_recorded_count"] == 1
    assert summary["optional_guidance_note_invalid_count"] == 1

    rows = {row["package_name"]: row for row in payload["packages"]}
    assert rows["pkg-reviewed"]["optional_guidance_note_available"] is True
    assert rows["pkg-reviewed"]["optional_guidance_note_status"] == "reviewed"
    assert rows["pkg-reviewed"]["optional_guidance_note_reviewer"] == "reviewer-reviewed"
    assert rows["pkg-reviewed"]["optional_guidance_note_action_count"] == 1
    assert rows["pkg-reviewed"]["optional_guidance_note_path"] == (
        "pkg-reviewed/handoff_optional_guidance_note.json"
    )

    assert rows["pkg-needs"]["optional_guidance_note_status"] == "needs_info"
    assert rows["pkg-needs"]["optional_guidance_note_reviewer"] == "reviewer-needs"
    assert rows["pkg-blocked"]["optional_guidance_note_status"] == "blocked"
    assert rows["pkg-blocked"]["optional_guidance_note_reviewer"] == "reviewer-blocked"
    assert rows["pkg-missing"]["optional_guidance_note_status"] == "not_recorded"
    assert rows["pkg-missing"]["optional_guidance_note_reviewer"] == ""
    assert rows["pkg-invalid"]["optional_guidance_note_status"] == "invalid"
    assert rows["pkg-strong"]["optional_guidance_note_available"] is False
    assert rows["pkg-strong"]["optional_guidance_note_status"] == "not_applicable"

    queue = payload["optional_guidance_note_closeout_queue"]
    assert queue == [
        {
            "package_name": "pkg-needs",
            "relative_package_dir": "pkg-needs",
            "status": "needs_info",
            "reviewer": "reviewer-needs",
            "action_count": 1,
            "note_path": "pkg-needs/handoff_optional_guidance_note.json",
            "reason": "Optional guidance note is needs_info.",
            "boundary_warning": (
                "Optional guidance closeout is manager triage visibility only; "
                "note states do not change package readiness."
            ),
        },
        {
            "package_name": "pkg-blocked",
            "relative_package_dir": "pkg-blocked",
            "status": "blocked",
            "reviewer": "reviewer-blocked",
            "action_count": 1,
            "note_path": "pkg-blocked/handoff_optional_guidance_note.json",
            "reason": "Optional guidance note is blocked.",
            "boundary_warning": (
                "Optional guidance closeout is manager triage visibility only; "
                "note states do not change package readiness."
            ),
        },
        {
            "package_name": "pkg-missing",
            "relative_package_dir": "pkg-missing",
            "status": "not_recorded",
            "reviewer": "",
            "action_count": 1,
            "note_path": "pkg-missing/handoff_optional_guidance_note.json",
            "reason": "Optional guidance note has not been recorded yet.",
            "boundary_warning": (
                "Optional guidance closeout is manager triage visibility only; "
                "note states do not change package readiness."
            ),
        },
        {
            "package_name": "pkg-invalid",
            "relative_package_dir": "pkg-invalid",
            "status": "invalid",
            "reviewer": "",
            "action_count": 1,
            "note_path": "pkg-invalid/handoff_optional_guidance_note.json",
            "reason": "Optional guidance note payload is invalid.",
            "boundary_warning": (
                "Optional guidance closeout is manager triage visibility only; "
                "note states do not change package readiness."
            ),
        },
    ]

    markdown = out_md.read_text("utf-8")
    assert (
        "Optional guidance note closeout: reviewed=`1`, needs_info=`1`, blocked=`1`, "
        "not_recorded=`1`, invalid=`1`"
    ) in markdown
    assert "## Optional Guidance Note Closeout Queue" in markdown
    assert (
        "| `pkg-needs` | needs_info | reviewer-needs | 1 | "
        "`pkg-needs/handoff_optional_guidance_note.json` |" in markdown
    )
    assert (
        "| `pkg-missing` | not_recorded |  | 1 | "
        "`pkg-missing/handoff_optional_guidance_note.json` |" in markdown
    )

    html = out_html.read_text("utf-8")
    assert "Optional Guidance Note Closeout Queue" in html
    assert "pkg-invalid" in html
    assert "note is invalid" in html


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


def _write_invalid_optional_guidance_note(package_dir: Path) -> None:
    (package_dir / "handoff_optional_guidance_note.json").write_text(
        json.dumps(
            {
                "schema_version": "handoff_optional_guidance_note.v1",
                "status": "not_reviewed",
                "reviewer": "reviewer-invalid",
                "note": "invalid status",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
