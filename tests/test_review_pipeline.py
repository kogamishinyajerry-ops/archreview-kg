from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from archkg.cli.main import app

REPO_ROOT = Path(__file__).resolve().parents[1]
GENERATED_COMPLEX_PDF = REPO_ROOT / "samples" / "generated_complex_titleblock.pdf"


def test_review_end_to_end_flags_corridor_and_doors(sample_pdf: Path, tmp_path: Path) -> None:
    runner = CliRunner()
    out_dir = tmp_path / "out"
    result = runner.invoke(app, ["review", str(sample_pdf), "-o", str(out_dir)])
    assert result.exit_code == 0, result.output

    expected = [
        "primitives.json",
        "entity_graph.json",
        "drawing_understanding.json",
        "rule_input_readiness.json",
        "sheet_region_candidates.json",
        "sheet_region_candidates_overlay.png",
        "issues.json",
        "review_state.json",
        "annotated.pdf",
        "report.md",
    ]
    for name in expected:
        assert (out_dir / name).exists(), f"missing {name}"

    readiness = json.loads(
        (out_dir / "rule_input_readiness.json").read_text(encoding="utf-8")
    )
    assert readiness["schema_version"] == "rule_input_readiness.v1"
    assert len(readiness["rules"]) == 32
    assert readiness["summary"]["missing_input"] >= 1

    issues = json.loads((out_dir / "issues.json").read_text(encoding="utf-8"))
    review_state = json.loads((out_dir / "review_state.json").read_text(encoding="utf-8"))
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
        assert "status" not in i
        assert "reviewer" not in i

    assert review_state["schema_version"] == "issue_review_state.v1"
    assert review_state["run_id"] == out_dir.name
    assert {item["issue_id"] for item in review_state["items"]} == {
        i["issue_id"] for i in issues
    }
    assert {item["status"] for item in review_state["items"]} == {"candidate"}


def test_report_md_contains_clause_text(sample_pdf: Path, tmp_path: Path) -> None:
    runner = CliRunner()
    out_dir = tmp_path / "out"
    result = runner.invoke(app, ["review", str(sample_pdf), "-o", str(out_dir)])
    assert result.exit_code == 0, result.output

    md = (out_dir / "report.md").read_text(encoding="utf-8")
    assert "审查报告" in md
    assert "GB50096" in md
    assert "规则输入就绪度" in md
    assert "缺输入不等于通过" in md
    assert "Issue 生命周期" in md
    # Should contain reviewer/status placeholder columns
    assert "reviewer" in md
    assert "status" in md
    assert "candidate" in md


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


def test_review_writes_sheet_region_candidates_without_autocropping(
    tmp_path: Path,
) -> None:
    runner = CliRunner()
    out_dir = tmp_path / "out"
    result = runner.invoke(app, ["review", str(GENERATED_COMPLEX_PDF), "-o", str(out_dir)])
    assert result.exit_code == 0, result.output

    candidates_path = out_dir / "sheet_region_candidates.json"
    assert candidates_path.exists()
    candidates = json.loads(candidates_path.read_text(encoding="utf-8"))
    page = candidates["pages"][0]
    by_kind = {candidate["kind"]: candidate for candidate in page["candidates"]}
    assert by_kind["design_region"]["region"][2] < by_kind["title_block"]["region"][0]
    assert by_kind["title_block"]["confidence"] >= 0.65
    assert any("TITLE BLOCK" in row["text"] for row in page["excluded_texts"])

    # Candidate suggestions are not an implicit crop. The full-sheet
    # primitives still retain title-block text unless --sheet-region is
    # explicitly supplied by the caller.
    primitives = json.loads((out_dir / "primitives.json").read_text(encoding="utf-8"))
    texts = {text["text"] for text in primitives["pages"][0]["texts"]}
    assert "TITLE BLOCK" in texts
