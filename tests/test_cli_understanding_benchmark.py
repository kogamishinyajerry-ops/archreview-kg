import json
from pathlib import Path

from typer.testing import CliRunner

from archkg.cli.main import app


def test_understanding_benchmark_cli_writes_json_and_markdown(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    understanding = {
        "schema_version": "drawing_understanding.v2",
        "drawing_type": "建筑平面图",
        "likely_design": "住宅平面图",
        "component_counts": {"rooms": 1, "doors": 1, "dimensions": 1},
        "component_inventory": [
            {"semantic_kind": "residential_room"},
            {"semantic_kind": "door_opening"},
            {"semantic_kind": "dimension_annotation"},
        ],
        "drawing_profile": {
            "understanding_level": "layout_with_dimensions",
            "evidence_signals": ["spatial_layout", "openings", "dimension_evidence"],
        },
        "benchmark_signals": {
            "has_spatial_layout": True,
            "has_openings": True,
            "has_dimension_evidence": True,
        },
    }
    expected = {
        "benchmark_id": "cli-pass",
        "min_score": 1.0,
        "drawing_type": "建筑平面图",
        "component_counts": {"rooms": {"exact": 1}},
        "required_semantic_kinds": ["residential_room", "door_opening"],
        "required_evidence_signals": ["spatial_layout", "openings"],
        "required_benchmark_signals": {"has_spatial_layout": True},
    }
    (run_dir / "drawing_understanding.json").write_text(json.dumps(understanding), "utf-8")
    expected_path = tmp_path / "expected.json"
    expected_path.write_text(json.dumps(expected), "utf-8")
    out_json = tmp_path / "score.json"
    out_md = tmp_path / "score.md"

    result = CliRunner().invoke(
        app,
        [
            "understanding-benchmark",
            str(run_dir),
            "--expect",
            str(expected_path),
            "--out",
            str(out_json),
            "--markdown",
            str(out_md),
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 0
    assert "cli-pass PASS score=1.00" in result.output
    assert json.loads(out_json.read_text("utf-8"))["passed"] is True
    assert "Status: PASS" in out_md.read_text("utf-8")


def test_understanding_benchmark_cli_exits_nonzero_on_fail(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "drawing_understanding.json").write_text(
        json.dumps(
            {
                "schema_version": "drawing_understanding.v2",
                "drawing_type": "未知图纸",
                "component_counts": {},
                "component_inventory": [],
                "drawing_profile": {"evidence_signals": []},
                "benchmark_signals": {},
            }
        ),
        "utf-8",
    )
    expected_path = tmp_path / "expected.json"
    expected_path.write_text(
        json.dumps({"benchmark_id": "cli-fail", "required_semantic_kinds": ["stair"]}),
        "utf-8",
    )

    result = CliRunner().invoke(
        app,
        ["understanding-benchmark", str(run_dir), "--expect", str(expected_path)],
        catch_exceptions=False,
    )

    assert result.exit_code == 1
    assert "cli-fail FAIL" in result.output
