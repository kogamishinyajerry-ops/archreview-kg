from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from archkg.cli.main import app
from archkg.release_readiness import (
    CORE_RUN_ARTIFACTS,
    EVIDENCE_RUN_ARTIFACTS,
    build_release_readiness,
    render_release_readiness_markdown,
)
from archkg.viewer.understanding_benchmark import run_understanding_benchmark_suite


def _suite_result(
    *,
    passed: bool = True,
    active_count: int = 3,
    pending_count: int = 1,
    known_gap_count: int = 1,
    failed_count: int = 0,
) -> dict[str, object]:
    return {
        "schema_version": "understanding_benchmark_suite_result.v1",
        "suite_id": "test-suite",
        "passed": passed,
        "active_count": active_count,
        "pending_count": pending_count,
        "known_gap_count": known_gap_count,
        "failed_count": failed_count,
        "cases": [
            {
                "case_id": "real-pass",
                "fixture_kind": "real_public_pdf",
                "status": "pass",
                "score": 1.0,
            },
            {
                "case_id": "generated-pass",
                "fixture_kind": "generated_complex_pdf",
                "status": "pass",
                "score": 1.0,
            },
            {
                "case_id": "known-gap",
                "fixture_kind": "real_public_multi_plan_pdf",
                "status": "known_gap",
                "score": 0.8,
            },
            {
                "case_id": "pending",
                "fixture_kind": "real_private_pdf",
                "status": "pending_fixture",
            },
        ],
    }


def _write_run_artifacts(run_dir: Path) -> None:
    run_dir.mkdir()
    for name in (*CORE_RUN_ARTIFACTS, *EVIDENCE_RUN_ARTIFACTS):
        (run_dir / name).write_text("{}", encoding="utf-8")


def test_release_readiness_is_demo_ready_with_known_gaps(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _write_run_artifacts(run_dir)

    result = build_release_readiness(_suite_result(), run_dir=run_dir)

    assert result["schema_version"] == "release_readiness.v1"
    assert result["status"] == "demo_ready_with_known_gaps"
    assert result["suite"]["real_active_count"] == 1
    assert result["suite"]["generated_active_count"] == 1
    assert not result["blockers"]
    assert any("known_gap" in warning for warning in result["warnings"])
    assert "broad automatic compliance" in result["recommended_claim"]


def test_release_readiness_blocks_failed_suite(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _write_run_artifacts(run_dir)

    result = build_release_readiness(
        _suite_result(passed=False, failed_count=1),
        run_dir=run_dir,
    )

    assert result["status"] == "not_ready"
    assert any("active benchmark suite must pass" in item for item in result["blockers"])


def test_release_readiness_blocks_missing_core_run_artifacts(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _write_run_artifacts(run_dir)
    (run_dir / "review_state.json").unlink()

    result = build_release_readiness(_suite_result(), run_dir=run_dir)

    assert result["status"] == "not_ready"
    assert any("review_state.json" in item for item in result["blockers"])


def test_release_readiness_can_be_evidence_ready(tmp_path: Path) -> None:
    suite = {
        "schema_version": "understanding_benchmark_suite_result.v1",
        "suite_id": "evidence-ready-suite",
        "passed": True,
        "active_count": 1,
        "pending_count": 0,
        "known_gap_count": 0,
        "failed_count": 0,
        "cases": [
            {
                "case_id": "real-pass",
                "fixture_kind": "real_public_pdf",
                "status": "pass",
                "score": 1.0,
            },
        ],
    }
    run_dir = tmp_path / "run"
    _write_run_artifacts(run_dir)

    result = build_release_readiness(suite, run_dir=run_dir)

    assert result["status"] == "evidence_ready"
    assert not result["blockers"]
    assert not result["warnings"]


def test_packaged_suite_can_be_evidence_ready_with_representative_run(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    suite = run_understanding_benchmark_suite(
        repo_root / "samples/understanding_benchmarks/suite_manifest.json"
    )
    run_dir = tmp_path / "run"
    _write_run_artifacts(run_dir)

    result = build_release_readiness(suite, run_dir=run_dir)

    # M5.Z-W2 split Medfield page 3/6/7/8/9 into 2 active + 3 known_gap.
    # M5.Z-W3 added 12 active + 7 known_gap from 4 Cambridge MA projects.
    # known_gap cases prevent evidence_ready (recognizer has documented
    # plan-only / label-pattern limitations).
    assert result["status"] == "demo_ready_with_known_gaps"
    assert result["suite"]["active_count"] == 21
    assert result["suite"]["pending_count"] == 0
    assert result["suite"]["known_gap_count"] == 10
    assert result["suite"]["real_active_count"] == 17
    assert result["suite"]["generated_active_count"] == 3
    # Warnings are plain strings, not dicts; the known_gap warning surfaces here
    assert any("known_gap" in str(w) for w in result["warnings"])


def test_release_readiness_markdown_includes_gate_tables(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _write_run_artifacts(run_dir)
    result = build_release_readiness(_suite_result(), run_dir=run_dir)

    md = render_release_readiness_markdown(result)

    assert "# ArchReview-KG Release Readiness Gate" in md
    assert "Status: `demo_ready_with_known_gaps`" in md
    assert "| suite_passed | True |" in md
    assert "`review_diff.json`" in md


def test_release_readiness_cli_writes_reports(tmp_path: Path) -> None:
    suite_path = tmp_path / "suite_result.json"
    suite_path.write_text(json.dumps(_suite_result(), ensure_ascii=False), encoding="utf-8")
    run_dir = tmp_path / "run"
    _write_run_artifacts(run_dir)
    out = tmp_path / "release_readiness.json"
    markdown = tmp_path / "release_readiness.md"

    result = CliRunner().invoke(
        app,
        [
            "release-readiness",
            "--suite-result",
            str(suite_path),
            "--run-dir",
            str(run_dir),
            "--out",
            str(out),
            "--markdown",
            str(markdown),
        ],
    )

    assert result.exit_code == 0, result.output
    assert "status=demo_ready_with_known_gaps" in result.output
    assert out.exists()
    assert markdown.exists()


def test_release_readiness_cli_exits_nonzero_when_not_ready(tmp_path: Path) -> None:
    suite_path = tmp_path / "suite_result.json"
    suite_path.write_text(
        json.dumps(_suite_result(passed=False, failed_count=1), ensure_ascii=False),
        encoding="utf-8",
    )
    run_dir = tmp_path / "run"
    _write_run_artifacts(run_dir)

    result = CliRunner().invoke(
        app,
        [
            "release-readiness",
            "--suite-result",
            str(suite_path),
            "--run-dir",
            str(run_dir),
        ],
    )

    assert result.exit_code == 1
    assert "status=not_ready" in result.output
