from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from archkg.cli.main import app


def test_review_end_to_end_flags_corridor_and_doors(sample_pdf: Path, tmp_path: Path) -> None:
    runner = CliRunner()
    out_dir = tmp_path / "out"
    result = runner.invoke(app, ["review", str(sample_pdf), "-o", str(out_dir)])
    assert result.exit_code == 0, result.output

    expected = ["primitives.json", "entity_graph.json", "issues.json", "annotated.pdf", "report.md"]
    for name in expected:
        assert (out_dir / name).exists(), f"missing {name}"

    issues = json.loads((out_dir / "issues.json").read_text(encoding="utf-8"))
    rule_ids = {i["rule_card_id"] for i in issues}

    # The synthetic plan has a 1.05 m corridor and 0.85 m doors -> these two rules MUST fire.
    assert "RC-CORRIDOR-WIDTH" in rule_ids
    assert "RC-DOOR-WIDTH" in rule_ids

    # Each issue must be fully traceable.
    for i in issues:
        assert i["rule_card_id"]
        assert i["standard_clause_id"]
        assert i["entity_ids"]
        assert "bbox" in i and len(i["bbox"]) == 4
        assert "evidence" in i


def test_report_md_contains_clause_text(sample_pdf: Path, tmp_path: Path) -> None:
    runner = CliRunner()
    out_dir = tmp_path / "out"
    result = runner.invoke(app, ["review", str(sample_pdf), "-o", str(out_dir)])
    assert result.exit_code == 0, result.output

    md = (out_dir / "report.md").read_text(encoding="utf-8")
    assert "审查报告" in md
    assert "GB50096" in md
    # Should contain reviewer/status placeholder columns
    assert "reviewer" in md
    assert "status" in md
    assert "open" in md


def test_annotated_pdf_is_a_real_pdf(sample_pdf: Path, tmp_path: Path) -> None:
    runner = CliRunner()
    out_dir = tmp_path / "out"
    result = runner.invoke(app, ["review", str(sample_pdf), "-o", str(out_dir)])
    assert result.exit_code == 0, result.output

    annotated = out_dir / "annotated.pdf"
    head = annotated.read_bytes()[:5]
    assert head == b"%PDF-"


def test_review_cli_threads_min_room_area_into_understanding(
    sample_pdf: Path,
    tmp_path: Path,
) -> None:
    runner = CliRunner()
    out_default = tmp_path / "out-default"
    out_filtered = tmp_path / "out-filtered"

    result_default = runner.invoke(app, ["review", str(sample_pdf), "-o", str(out_default)])
    assert result_default.exit_code == 0, result_default.output

    result_filtered = runner.invoke(
        app,
        [
            "review",
            str(sample_pdf),
            "-o",
            str(out_filtered),
            "--min-room-area-m2",
            "100.0",
        ],
    )
    assert result_filtered.exit_code == 0, result_filtered.output

    default_payload = json.loads(
        (out_default / "drawing_understanding.json").read_text(encoding="utf-8")
    )
    filtered_payload = json.loads(
        (out_filtered / "drawing_understanding.json").read_text(encoding="utf-8")
    )
    assert default_payload["component_counts"]["rooms"] > 0
    assert filtered_payload["component_counts"]["rooms"] < default_payload[
        "component_counts"
    ]["rooms"]
