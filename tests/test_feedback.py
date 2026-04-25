from __future__ import annotations

import shutil
from pathlib import Path

import yaml
from typer.testing import CliRunner

from archkg.cli.main import app
from archkg.feedback.recorder import FeedbackError, record


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
        if "RC-CORRIDOR-WIDTH" in line and "| open |" in line and target_id is None:
            line = line.replace("| open |", "| confirmed |")
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
    # All other issues remain `open`.
    assert sum(1 for v in statuses.values() if v == "confirmed") == 1
    assert sum(1 for v in statuses.values() if v == "open") == len(statuses) - 1


def test_record_rejects_invalid_status(sample_pdf: Path, tmp_path: Path) -> None:
    run_dir = tmp_path / "run-bad"
    _seed_run(sample_pdf, run_dir)
    md = (run_dir / "report.md").read_text(encoding="utf-8")
    md = md.replace("| open |", "| weird |", 1)
    (run_dir / "report.md").write_text(md, encoding="utf-8")
    import pytest

    with pytest.raises(FeedbackError, match="invalid status"):
        record(run_dir)


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
