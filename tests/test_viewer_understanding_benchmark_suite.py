import json
from pathlib import Path

from archkg.viewer.understanding_benchmark import (
    render_suite_markdown_report,
    run_understanding_benchmark_suite,
)


def _write_current_payload(run_dir: Path) -> None:
    run_dir.mkdir()
    payload = {
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
    (run_dir / "drawing_understanding.json").write_text(json.dumps(payload), "utf-8")


def _write_expected(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "benchmark_id": "suite-active-case",
                "drawing_type": "建筑平面图",
                "required_semantic_kinds": ["residential_room", "door_opening"],
                "required_evidence_signals": ["spatial_layout"],
            }
        ),
        "utf-8",
    )


def test_benchmark_suite_runs_active_cases_and_tracks_real_pending(tmp_path: Path) -> None:
    _write_current_payload(tmp_path / "run")
    _write_expected(tmp_path / "expected.json")
    manifest = {
        "schema_version": "understanding_benchmark_suite.v1",
        "suite_id": "intake-v1",
        "cases": [
            {
                "case_id": "toy-active",
                "fixture_kind": "toy_vector_pdf",
                "run_dir": "run",
                "expect": "expected.json",
            },
            {
                "case_id": "medfield-public-plans",
                "fixture_kind": "real_public_pdf",
                "status": "pending_fixture",
                "source_url": "https://www.town.medfield.net/DocumentCenter/View/1428/floorplans-and-elevations-04-10-18-PDF",
                "provenance": "real/medfield_public_plans_provenance.json",
                "required_artifacts": [
                    "drawing_understanding.json",
                    "sheet_graphs.json",
                    "expected_inventory.json",
                ],
                "promotion_rule": "promote only after human expected inventory review",
                "notes": "public real drawing intake placeholder; expected inventory not annotated yet",
            },
        ],
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), "utf-8")

    result = run_understanding_benchmark_suite(manifest_path)

    assert result["suite_id"] == "intake-v1"
    assert result["passed"] is True
    assert result["active_count"] == 1
    assert result["pending_count"] == 1
    assert result["failed_count"] == 0
    assert result["cases"][0]["status"] == "pass"
    assert result["cases"][0]["fixture_kind"] == "toy_vector_pdf"
    assert result["cases"][1] == {
        "case_id": "medfield-public-plans",
        "fixture_kind": "real_public_pdf",
        "status": "pending_fixture",
        "passed": None,
        "source_url": "https://www.town.medfield.net/DocumentCenter/View/1428/floorplans-and-elevations-04-10-18-PDF",
        "provenance": "real/medfield_public_plans_provenance.json",
        "required_artifacts": [
            "drawing_understanding.json",
            "sheet_graphs.json",
            "expected_inventory.json",
        ],
        "promotion_rule": "promote only after human expected inventory review",
        "notes": "public real drawing intake placeholder; expected inventory not annotated yet",
    }


def test_benchmark_suite_fails_active_case_with_missing_artifacts(tmp_path: Path) -> None:
    _write_expected(tmp_path / "expected.json")
    manifest = {
        "suite_id": "missing-run",
        "cases": [
            {
                "case_id": "missing-active",
                "fixture_kind": "real_public_pdf",
                "run_dir": "missing-run-dir",
                "expect": "expected.json",
            }
        ],
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), "utf-8")

    result = run_understanding_benchmark_suite(manifest_path)

    assert result["passed"] is False
    assert result["failed_count"] == 1
    assert result["cases"][0]["status"] == "failed"
    assert result["cases"][0]["error"].startswith("run_dir not found")


def test_benchmark_suite_records_known_gap_without_failing_suite(tmp_path: Path) -> None:
    _write_current_payload(tmp_path / "run")
    expected_path = tmp_path / "expected.json"
    expected_path.write_text(
        json.dumps(
            {
                "benchmark_id": "real-known-gap",
                "component_counts": {"rooms": {"exact": 2}},
                "required_semantic_kinds": ["residential_room"],
            }
        ),
        "utf-8",
    )
    manifest = {
        "suite_id": "known-gap-suite",
        "cases": [
            {
                "case_id": "real-a1",
                "fixture_kind": "real_public_pdf",
                "status": "known_gap",
                "run_dir": "run",
                "expect": "expected.json",
                "provenance": "real/real_a1_provenance.json",
                "promotion_rule": "promote only after expected inventory passes",
                "notes": "Current recognizer under-counts the manually annotated rooms.",
            }
        ],
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), "utf-8")

    result = run_understanding_benchmark_suite(manifest_path)

    assert result["passed"] is True
    assert result["active_count"] == 0
    assert result["pending_count"] == 0
    assert result["known_gap_count"] == 1
    assert result["failed_count"] == 0
    assert result["cases"][0]["status"] == "known_gap"
    assert result["cases"][0]["passed"] is None
    assert result["cases"][0]["benchmark_passed"] is False
    assert result["cases"][0]["provenance"] == "real/real_a1_provenance.json"
    assert result["cases"][0]["promotion_rule"] == "promote only after expected inventory passes"
    assert result["cases"][0]["score"] < 1.0


def test_benchmark_suite_fails_known_gap_that_unexpectedly_passes(tmp_path: Path) -> None:
    _write_current_payload(tmp_path / "run")
    _write_expected(tmp_path / "expected.json")
    manifest = {
        "suite_id": "known-gap-unexpected-pass",
        "cases": [
            {
                "case_id": "real-a1",
                "fixture_kind": "real_public_pdf",
                "status": "known_gap",
                "run_dir": "run",
                "expect": "expected.json",
            }
        ],
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), "utf-8")

    result = run_understanding_benchmark_suite(manifest_path)

    assert result["passed"] is False
    assert result["failed_count"] == 1
    assert result["known_gap_count"] == 0
    assert result["cases"][0]["status"] == "unexpected_pass"
    assert result["cases"][0]["benchmark_passed"] is True


def test_packaged_suite_manifest_tracks_medfield_active_real_case() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    manifest_path = repo_root / "samples/understanding_benchmarks/suite_manifest.json"

    result = run_understanding_benchmark_suite(manifest_path)

    assert result["passed"] is True
    assert result["pending_count"] == 1
    assert result["active_count"] == 3
    assert result["known_gap_count"] == 1
    assert result["failed_count"] == 0
    medfield = next(
        case for case in result["cases"] if case["case_id"] == "medfield-a1-first-floor"
    )
    assert medfield["status"] == "pass"
    assert medfield["passed"] is True
    assert medfield["score"] == 1.0
    generated = next(
        case for case in result["cases"] if case["case_id"] == "generated-complex-titleblock"
    )
    assert generated["fixture_kind"] == "generated_complex_pdf"
    assert generated["status"] == "pass"
    assert generated["score"] == 1.0
    multi_plan = next(
        case for case in result["cases"] if case["case_id"] == "generated-multi-plan-sheets"
    )
    assert multi_plan["fixture_kind"] == "generated_multi_plan_pdf"
    assert multi_plan["status"] == "pass"
    assert multi_plan["score"] == 1.0
    check_names = {check["name"] for check in multi_plan["checks"]}
    assert "sheet_graphs:graph_count" in check_names
    assert "sheet_issues:rule_ids:0" in check_names
    real_multi_plan = next(
        case
        for case in result["cases"]
        if case["case_id"] == "medfield-full-plan-set-multi-plan-intake"
    )
    assert real_multi_plan["fixture_kind"] == "real_public_multi_plan_pdf"
    assert real_multi_plan["status"] == "known_gap"
    assert real_multi_plan["passed"] is None
    assert real_multi_plan["benchmark_passed"] is False
    assert real_multi_plan["score"] < 1.0
    assert real_multi_plan["provenance"] == "real/medfield_full_plan_set_intake_provenance.json"
    assert real_multi_plan["required_artifacts"] == [
        "source_pdf_or_private_pointer",
        "full_review_run_dir",
        "drawing_understanding.json",
        "sheet_classification.json",
        "sheet_graphs.json",
        "sheet_issues.json",
        "human_expected_inventory.json",
    ]
    assert "do not promote to active" in real_multi_plan["promotion_rule"]
    failed_checks = {
        check["name"] for check in real_multi_plan["checks"] if check["passed"] is False
    }
    assert "component_counts:doors" in failed_checks
    assert "benchmark_signal:has_openings" in failed_checks


def test_benchmark_suite_markdown_report() -> None:
    result = {
        "suite_id": "suite-demo",
        "passed": True,
        "active_count": 1,
        "pending_count": 1,
        "failed_count": 0,
        "cases": [
            {"case_id": "active", "fixture_kind": "toy", "status": "pass", "score": 1.0},
            {
                "case_id": "real-pending",
                "fixture_kind": "real_public_pdf",
                "status": "pending_fixture",
                "passed": None,
            },
        ],
    }

    md = render_suite_markdown_report(result)

    assert "# Drawing Understanding Benchmark Suite: suite-demo" in md
    assert "Status: PASS" in md
    assert "| real-pending | real_public_pdf | pending_fixture | - |" in md
