from __future__ import annotations

import json
import shutil
from pathlib import Path

import yaml
from typer.testing import CliRunner

from archkg.cli.main import app
from archkg.feedback.recorder import FeedbackError, _build_test_case, record


def _seed_run(sample_pdf: Path, run_dir: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["review", str(sample_pdf), "-o", str(run_dir)])
    assert result.exit_code == 0, result.output


def _mark_first_corridor_confirmed(run_dir: Path) -> str:
    """Edit report.md to set status='confirmed' on the corridor row. Returns the issue_id."""
    md = (run_dir / "report.md").read_text(encoding="utf-8")
    new_lines: list[str] = []
    target_id: str | None = None
    for line in md.splitlines():
        if "RC-CORRIDOR-WIDTH" in line and "| candidate |" in line and target_id is None:
            line = line.replace("| candidate |", "| confirmed |")
            # extract the issue_id from the first cell
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            target_id = cells[0].strip("`").strip()
        new_lines.append(line)
    (run_dir / "report.md").write_text("\n".join(new_lines), encoding="utf-8")
    assert target_id is not None
    return target_id


def test_record_writes_feedback_yaml_with_one_confirmed_row(
    sample_pdf: Path, tmp_path: Path
) -> None:
    run_dir = tmp_path / "run-001"
    _seed_run(sample_pdf, run_dir)
    target_id = _mark_first_corridor_confirmed(run_dir)

    out = record(run_dir)
    assert out.exists()
    payload = yaml.safe_load(out.read_text(encoding="utf-8"))
    assert payload["run_id"] == "run-001"

    statuses = {item["issue_id"]: item["status"] for item in payload["items"]}
    assert statuses[target_id] == "confirmed"
    # All other issues remain rule-engine candidates.
    assert sum(1 for v in statuses.values() if v == "confirmed") == 1
    assert sum(1 for v in statuses.values() if v == "candidate") == len(statuses) - 1

    review_state = json.loads((run_dir / "review_state.json").read_text(encoding="utf-8"))
    by_issue = {item["issue_id"]: item for item in review_state["items"]}
    assert by_issue[target_id]["status"] == "confirmed"
    assert sum(1 for item in by_issue.values() if item["status"] == "candidate") == len(statuses) - 1

    issues = json.loads((run_dir / "issues.json").read_text(encoding="utf-8"))
    assert all("status" not in issue for issue in issues)


def test_record_rejects_invalid_status(sample_pdf: Path, tmp_path: Path) -> None:
    run_dir = tmp_path / "run-bad"
    _seed_run(sample_pdf, run_dir)
    md = (run_dir / "report.md").read_text(encoding="utf-8")
    md = md.replace("| candidate |", "| weird |", 1)
    (run_dir / "report.md").write_text(md, encoding="utf-8")
    import pytest

    with pytest.raises(FeedbackError, match="invalid status"):
        record(run_dir)


def test_record_accepts_legacy_open_status_as_candidate(
    sample_pdf: Path, tmp_path: Path
) -> None:
    run_dir = tmp_path / "run-legacy"
    _seed_run(sample_pdf, run_dir)
    md = (run_dir / "report.md").read_text(encoding="utf-8")
    md = md.replace("| candidate |", "| open |", 1)
    (run_dir / "report.md").write_text(md, encoding="utf-8")

    out = record(run_dir)
    payload = yaml.safe_load(out.read_text(encoding="utf-8"))
    assert any(item["status"] == "candidate" for item in payload["items"])


def test_apply_promotes_confirmed_to_rule_cards(
    sample_pdf: Path, tmp_path: Path
) -> None:
    # work on a copy of rule_cards.yaml so we don't mutate the packaged file
    src = Path(__file__).parent.parent / "archkg/knowledge/data/rule_cards.yaml"
    rules_copy = tmp_path / "rule_cards.yaml"
    shutil.copy(src, rules_copy)

    run_dir = tmp_path / "run-apply"
    _seed_run(sample_pdf, run_dir)
    target_id = _mark_first_corridor_confirmed(run_dir)

    record(run_dir, rules_path=rules_copy, apply_to_rules=True)
    promoted = yaml.safe_load(rules_copy.read_text(encoding="utf-8"))

    corridor_rule = next(r for r in promoted if r["id"] == "RC-CORRIDOR-WIDTH")
    promoted_names = [tc["name"] for tc in corridor_rule["test_cases"]]
    assert any(name == f"confirmed-{target_id}" for name in promoted_names)


def test_cli_feedback_smoke(sample_pdf: Path, tmp_path: Path) -> None:
    runner = CliRunner()
    run_dir = tmp_path / "run-cli"
    _seed_run(sample_pdf, run_dir)
    _mark_first_corridor_confirmed(run_dir)

    result = runner.invoke(app, ["feedback", str(run_dir)])
    assert result.exit_code == 0, result.output
    assert (run_dir / "feedback.yaml").exists()


def test_cli_review_state_updates_single_issue_without_mutating_issues(
    sample_pdf: Path,
    tmp_path: Path,
) -> None:
    runner = CliRunner()
    run_dir = tmp_path / "run-review-state"
    _seed_run(sample_pdf, run_dir)
    issues_before = (run_dir / "issues.json").read_text(encoding="utf-8")
    issues = json.loads(issues_before)
    issue_id = issues[0]["issue_id"]

    result = runner.invoke(
        app,
        [
            "review-state",
            str(run_dir),
            issue_id,
            "--status",
            "rejected",
            "--reviewer",
            "Zhu",
            "--note",
            "not applicable after manual check",
        ],
    )

    assert result.exit_code == 0, result.output
    assert (run_dir / "issues.json").read_text(encoding="utf-8") == issues_before
    review_state = json.loads((run_dir / "review_state.json").read_text("utf-8"))
    by_issue = {item["issue_id"]: item for item in review_state["items"]}
    assert by_issue[issue_id]["status"] == "rejected"
    assert by_issue[issue_id]["reviewer"] == "Zhu"
    assert review_state["summary"]["rejected"] == 1
    workbench = json.loads((run_dir / "review_workbench.json").read_text("utf-8"))
    assert workbench["summary"]["candidate_review_states"] == len(issues) - 1


def test_build_test_case_for_project_issue_without_meta_returns_none() -> None:
    """Codex P11-B P1: project-level confirmed issues must NOT promote with
    all-None inputs when the run has no project_meta.yaml."""
    issue = {
        "issue_id": "ISS-test",
        "rule_card_id": "RC-ELEVATOR-REQUIRED",
        "entity_ids": ["project:DEMO-001"],
    }
    tc = _build_test_case(issue, graph={}, meta=None)
    assert tc is None, "no project_meta means we silently drop the promotion"


def test_build_test_case_for_project_issue_with_meta_uses_meta_values() -> None:
    """When project_meta.yaml is present, promotion env comes from it
    (not entity_graph.json which contains no 'project:' entries)."""
    issue = {
        "issue_id": "ISS-test",
        "rule_card_id": "RC-ELEVATOR-REQUIRED",
        "entity_ids": ["project:DEMO-001"],
    }
    meta = {
        "project_id": "DEMO-001",
        "building_type": "residential",
        "height_class": "多层",
        "floors": 8,
        "height_m": 22.0,
    }
    tc = _build_test_case(issue, graph={}, meta=meta)
    assert tc is not None
    # rule.inputs for RC-ELEVATOR-REQUIRED is [floors, height_m]
    assert tc["entity"] == {"floors": 8, "height_m": 22.0}
    assert tc["expect_pass"] is False
    assert tc["name"] == "confirmed-ISS-test"


def test_build_test_case_falls_back_to_properties_for_stair_rule() -> None:
    """Codex Phase 15 P1: stair rules read inputs (flight_width_m,
    well_width_m, handrail_height_m) from Stair.properties via the engine's
    fallback. Feedback promotion must mirror that fallback or it would write
    all-None test_cases that then break test_rule_test_cases_match_engine_decision.
    """
    issue = {
        "issue_id": "ISS-stair",
        "rule_card_id": "RC-STAIR-WELL-WIDTH-0.11",
        "entity_ids": ["stair-1"],
    }
    graph = {
        "stair-1": {
            "id": "stair-1",
            "type": "Stair",
            "tread_width_m": 0.28,
            "riser_height_m": 0.16,
            # well_width_m lives in properties (not a schema field).
            "properties": {"well_width_m": 0.15},
        },
    }
    tc = _build_test_case(issue, graph=graph, meta=None)
    assert tc is not None
    # rule.inputs for RC-STAIR-WELL-WIDTH-0.11 is [well_width_m]
    assert tc["entity"] == {"well_width_m": 0.15}, (
        "promotion must read from properties when input is not a top-level field"
    )
    assert tc["expect_pass"] is False
