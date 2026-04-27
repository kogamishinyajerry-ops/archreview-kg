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


def test_understanding_benchmark_author_cli_writes_expected_draft(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "drawing_understanding.json").write_text(
        json.dumps(
            {
                "schema_version": "drawing_understanding.v2",
                "drawing_type": "建筑平面图",
                "likely_design": "住宅平面图",
                "component_counts": {"rooms": 1, "doors": 1, "dimensions": 1},
                "component_inventory": [
                    {"semantic_kind": "residential_room"},
                    {"semantic_kind": "door_opening"},
                    {"semantic_kind": "dimension_annotation"},
                ],
                "drawing_profile": {"evidence_signals": ["spatial_layout", "openings"]},
                "benchmark_signals": {
                    "has_spatial_layout": True,
                    "has_openings": True,
                },
            }
        ),
        "utf-8",
    )
    out_json = tmp_path / "expected-draft.json"

    result = CliRunner().invoke(
        app,
        [
            "understanding-benchmark-author",
            str(run_dir),
            "--benchmark-id",
            "cli-authored",
            "--out",
            str(out_json),
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 0
    assert "cli-authored draft written" in result.output
    draft = json.loads(out_json.read_text("utf-8"))
    assert draft["review_required"] is True
    assert draft["component_counts"]["rooms"] == {"exact": 1}
    assert draft["required_semantic_kinds"] == [
        "residential_room",
        "door_opening",
        "dimension_annotation",
    ]


def test_understanding_benchmark_suite_cli_writes_reports(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "drawing_understanding.json").write_text(
        json.dumps(
            {
                "schema_version": "drawing_understanding.v2",
                "drawing_type": "建筑平面图",
                "likely_design": "住宅平面图",
                "component_counts": {"rooms": 1},
                "component_inventory": [{"semantic_kind": "residential_room"}],
                "drawing_profile": {"evidence_signals": ["spatial_layout"]},
                "benchmark_signals": {"has_spatial_layout": True},
            }
        ),
        "utf-8",
    )
    expected_path = tmp_path / "expected.json"
    expected_path.write_text(
        json.dumps(
            {
                "benchmark_id": "suite-cli-pass",
                "drawing_type": "建筑平面图",
                "required_semantic_kinds": ["residential_room"],
                "required_evidence_signals": ["spatial_layout"],
            }
        ),
        "utf-8",
    )
    manifest_path = tmp_path / "suite.json"
    manifest_path.write_text(
        json.dumps(
            {
                "suite_id": "cli-suite",
                "cases": [
                    {
                        "case_id": "active",
                        "fixture_kind": "toy_vector_pdf",
                        "run_dir": "run",
                        "expect": "expected.json",
                    },
                    {
                        "case_id": "real-pending",
                        "fixture_kind": "real_public_pdf",
                        "status": "pending_fixture",
                    },
                ],
            }
        ),
        "utf-8",
    )
    out_json = tmp_path / "suite-result.json"
    out_md = tmp_path / "suite-result.md"

    result = CliRunner().invoke(
        app,
        [
            "understanding-benchmark-suite",
            "--manifest",
            str(manifest_path),
            "--out",
            str(out_json),
            "--markdown",
            str(out_md),
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 0
    assert "cli-suite PASS active=1 pending=1 failed=0" in result.output
    assert json.loads(out_json.read_text("utf-8"))["passed"] is True
    assert "Drawing Understanding Benchmark Suite: cli-suite" in out_md.read_text("utf-8")


def test_understanding_benchmark_suite_cli_exits_nonzero_on_failed_case(tmp_path: Path) -> None:
    expected_path = tmp_path / "expected.json"
    expected_path.write_text(json.dumps({"benchmark_id": "missing-run"}), "utf-8")
    manifest_path = tmp_path / "suite.json"
    manifest_path.write_text(
        json.dumps(
            {
                "suite_id": "cli-suite-fail",
                "cases": [
                    {
                        "case_id": "missing",
                        "fixture_kind": "real_public_pdf",
                        "run_dir": "missing",
                        "expect": "expected.json",
                    }
                ],
            }
        ),
        "utf-8",
    )

    result = CliRunner().invoke(
        app,
        ["understanding-benchmark-suite", "--manifest", str(manifest_path)],
        catch_exceptions=False,
    )

    assert result.exit_code == 1
    assert "cli-suite-fail FAIL active=1 pending=0 failed=1" in result.output
