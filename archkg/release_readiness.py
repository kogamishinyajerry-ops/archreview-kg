from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal

ReleaseReadinessStatus = Literal[
    "not_ready",
    "demo_ready_with_known_gaps",
    "evidence_ready",
]

SCHEMA_VERSION = "release_readiness.v1"

CORE_RUN_ARTIFACTS: tuple[str, ...] = (
    "drawing_understanding.json",
    "rule_input_readiness.json",
    "review_workbench.json",
    "issues.json",
    "review_state.json",
)

EVIDENCE_RUN_ARTIFACTS: tuple[str, ...] = (
    "sheet_classification.json",
    "sheet_routing.json",
    "sheet_graphs.json",
    "sheet_issues.json",
    "sheet_issue_review_queue.json",
    "sheet_region_candidates.json",
    "reviewer_onboarding.json",
    "reviewer_quickstart.md",
    "review_diff.json",
)


class ReleaseReadinessError(RuntimeError):
    pass


def build_release_readiness(
    suite_result: Mapping[str, Any],
    *,
    run_dir: Path | None = None,
) -> dict[str, Any]:
    suite_summary = _suite_summary(suite_result)
    artifact_summary = _run_artifact_summary(run_dir)
    checks = _checks(suite_summary, artifact_summary)
    blockers = [
        check["detail"]
        for check in checks
        if check["severity"] == "blocker" and check["passed"] is False
    ]
    warnings = [
        check["detail"]
        for check in checks
        if check["severity"] == "warning" and check["passed"] is False
    ]
    status = _status(blockers, warnings)
    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "recommended_claim": _recommended_claim(status),
        "suite": suite_summary,
        "run_artifacts": artifact_summary,
        "checks": checks,
        "blockers": blockers,
        "warnings": warnings,
        "next_actions": _next_actions(status, blockers, warnings),
        "note": (
            "Release readiness is evidence-gated. Rule count alone is not a readiness metric."
        ),
    }


def build_release_readiness_from_suite_result(
    suite_result_path: Path,
    *,
    run_dir: Path | None = None,
) -> dict[str, Any]:
    return build_release_readiness(load_suite_result(suite_result_path), run_dir=run_dir)


def load_suite_result(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ReleaseReadinessError(f"suite result not found: {path}")
    try:
        raw = json.loads(path.read_text("utf-8"))
    except json.JSONDecodeError as exc:
        raise ReleaseReadinessError(f"could not read {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ReleaseReadinessError(f"suite result must be a JSON object: {path}")
    return {str(key): value for key, value in raw.items()}


def write_release_readiness_json(result: Mapping[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_release_readiness_markdown(result: Mapping[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_release_readiness_markdown(result), encoding="utf-8")
    return path


def render_release_readiness_markdown(result: Mapping[str, Any]) -> str:
    status = _str(result.get("status"))
    suite = _mapping(result.get("suite"))
    run_artifacts = _mapping(result.get("run_artifacts"))
    lines = [
        "# ArchReview-KG Release Readiness Gate",
        "",
        f"Status: `{status}`",
        "",
        _str(result.get("recommended_claim")),
        "",
        "## Suite Evidence",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| suite_passed | {suite.get('passed')} |",
        f"| active_count | {_int(suite.get('active_count'))} |",
        f"| real_active_count | {_int(suite.get('real_active_count'))} |",
        f"| generated_active_count | {_int(suite.get('generated_active_count'))} |",
        f"| known_gap_count | {_int(suite.get('known_gap_count'))} |",
        f"| pending_count | {_int(suite.get('pending_count'))} |",
        f"| failed_count | {_int(suite.get('failed_count'))} |",
        "",
        "## Representative Run Artifacts",
        "",
        f"Run dir: `{_str(run_artifacts.get('run_dir')) or 'not provided'}`",
        "",
        "| Artifact | Status | Tier |",
        "|---|---:|---|",
    ]
    for row in _list_of_mappings(run_artifacts.get("artifacts")):
        lines.append(
            "| "
            f"`{_str(row.get('artifact'))}` | "
            f"{'available' if row.get('available') else 'missing'} | "
            f"{_str(row.get('tier'))} |"
        )
    lines.extend(
        [
            "",
            "## Checks",
            "",
            "| Check | Severity | Status | Detail |",
            "|---|---|---:|---|",
        ]
    )
    for row in _list_of_mappings(result.get("checks")):
        lines.append(
            "| "
            f"{_str(row.get('id'))} | "
            f"{_str(row.get('severity'))} | "
            f"{'PASS' if row.get('passed') else 'FAIL'} | "
            f"{_str(row.get('detail'))} |"
        )
    next_actions = [item for item in _list(result.get("next_actions")) if isinstance(item, str)]
    if next_actions:
        lines.extend(["", "## Next Actions", ""])
        lines.extend(f"- {item}" for item in next_actions)
    lines.append("")
    return "\n".join(lines)


def _suite_summary(suite_result: Mapping[str, Any]) -> dict[str, Any]:
    cases = _list_of_mappings(suite_result.get("cases"))
    real_active_count = sum(
        1
        for case in cases
        if case.get("status") == "pass" and _str(case.get("fixture_kind")).startswith("real_")
    )
    generated_active_count = sum(
        1
        for case in cases
        if case.get("status") == "pass"
        and _str(case.get("fixture_kind")).startswith("generated_")
    )
    return {
        "suite_id": _str(suite_result.get("suite_id")),
        "passed": bool(suite_result.get("passed")),
        "active_count": _int(suite_result.get("active_count")),
        "pending_count": _int(suite_result.get("pending_count")),
        "known_gap_count": _int(suite_result.get("known_gap_count")),
        "failed_count": _int(suite_result.get("failed_count")),
        "real_active_count": real_active_count,
        "generated_active_count": generated_active_count,
        "case_statuses": [
            {
                "case_id": _str(case.get("case_id")),
                "fixture_kind": _str(case.get("fixture_kind")),
                "status": _str(case.get("status")),
                "score": case.get("score"),
            }
            for case in cases
        ],
    }


def _run_artifact_summary(run_dir: Path | None) -> dict[str, Any]:
    if run_dir is None:
        return {
            "run_dir": "",
            "provided": False,
            "core_missing": [],
            "evidence_missing": [],
            "artifacts": [],
        }
    artifacts = []
    for name in CORE_RUN_ARTIFACTS:
        artifacts.append(_artifact_row(run_dir, name, "core"))
    for name in EVIDENCE_RUN_ARTIFACTS:
        artifacts.append(_artifact_row(run_dir, name, "evidence"))
    return {
        "run_dir": str(run_dir),
        "provided": True,
        "core_missing": [
            row["artifact"]
            for row in artifacts
            if row["tier"] == "core" and row["available"] is False
        ],
        "evidence_missing": [
            row["artifact"]
            for row in artifacts
            if row["tier"] == "evidence" and row["available"] is False
        ],
        "artifacts": artifacts,
    }


def _artifact_row(run_dir: Path, name: str, tier: str) -> dict[str, Any]:
    return {
        "artifact": name,
        "tier": tier,
        "available": (run_dir / name).exists(),
    }


def _checks(
    suite_summary: Mapping[str, Any],
    artifact_summary: Mapping[str, Any],
) -> list[dict[str, Any]]:
    checks = [
        _check(
            "suite:active-pass",
            bool(suite_summary.get("passed")),
            "blocker",
            "active benchmark suite must pass",
        ),
        _check(
            "suite:active-count",
            _int(suite_summary.get("active_count")) >= 1,
            "blocker",
            "at least one active benchmark case is required",
        ),
        _check(
            "suite:real-active",
            _int(suite_summary.get("real_active_count")) >= 1,
            "blocker",
            "at least one active real drawing benchmark is required",
        ),
        _check(
            "suite:known-gaps",
            _int(suite_summary.get("known_gap_count")) == 0,
            "warning",
            "known_gap cases prevent evidence_ready claims",
        ),
        _check(
            "suite:pending",
            _int(suite_summary.get("pending_count")) == 0,
            "warning",
            "pending benchmark rows prevent evidence_ready claims",
        ),
        _check(
            "suite:generated-not-proxy",
            _int(suite_summary.get("generated_active_count"))
            <= _int(suite_summary.get("real_active_count")),
            "warning",
            "generated active fixtures outnumber active real drawing evidence",
        ),
    ]
    if bool(artifact_summary.get("provided")):
        core_missing = [item for item in _list(artifact_summary.get("core_missing")) if isinstance(item, str)]
        evidence_missing = [
            item
            for item in _list(artifact_summary.get("evidence_missing"))
            if isinstance(item, str)
        ]
        checks.append(
            _check(
                "run:core-artifacts",
                not core_missing,
                "blocker",
                (
                    f"representative run is missing core evidence artifacts: {', '.join(core_missing)}"
                    if core_missing
                    else "representative run includes all core evidence artifacts"
                ),
            )
        )
        checks.append(
            _check(
                "run:evidence-artifacts",
                not evidence_missing,
                "warning",
                (
                    "representative run is missing optional maturity evidence artifacts: "
                    f"{', '.join(evidence_missing)}"
                    if evidence_missing
                    else "representative run includes all optional maturity evidence artifacts"
                ),
            )
        )
    else:
        checks.append(
            _check(
                "run:representative-run",
                False,
                "warning",
                "no representative run_dir supplied; gate cannot verify per-run artifacts",
            )
        )
    return checks


def _check(check_id: str, passed: bool, severity: str, detail: str) -> dict[str, Any]:
    return {
        "id": check_id,
        "passed": passed,
        "severity": severity,
        "detail": detail,
    }


def _status(blockers: Sequence[str], warnings: Sequence[str]) -> ReleaseReadinessStatus:
    if blockers:
        return "not_ready"
    if warnings:
        return "demo_ready_with_known_gaps"
    return "evidence_ready"


def _recommended_claim(status: str) -> str:
    if status == "evidence_ready":
        return (
            "Evidence-ready for a constrained pilot on benchmarked drawing classes; "
            "human review and jurisdiction-specific checks still apply."
        )
    if status == "demo_ready_with_known_gaps":
        return (
            "Demo-ready for evidence-first drawing review workflows on selected "
            "benchmarked drawings, with explicit known gaps. Do not claim broad "
            "automatic compliance readiness."
        )
    return (
        "Not ready for external readiness claims; resolve blockers before using "
        "the workbench as a maturity signal."
    )


def _next_actions(
    status: str,
    blockers: Sequence[str],
    warnings: Sequence[str],
) -> list[str]:
    if status == "not_ready":
        return list(blockers)
    if status == "demo_ready_with_known_gaps":
        return [
            *warnings,
            "promote real known_gap/pending cases only after reviewed expected inventory passes",
            "keep per-sheet preview issues separate from primary lifecycle until aggregation semantics are explicit",
        ]
    return [
        "keep expanding active real drawing benchmarks before broadening readiness claims",
        "rerun this gate before release notes or demo handoff",
    ]


def _mapping(raw: object) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        return {}
    return {str(key): value for key, value in raw.items()}


def _list(raw: object) -> list[Any]:
    return raw if isinstance(raw, list) else []


def _list_of_mappings(raw: object) -> list[Mapping[str, Any]]:
    return [item for item in _list(raw) if isinstance(item, Mapping)]


def _str(raw: object) -> str:
    return raw if isinstance(raw, str) else ""


def _int(raw: object) -> int:
    return raw if isinstance(raw, int) else 0


__all__ = [
    "CORE_RUN_ARTIFACTS",
    "EVIDENCE_RUN_ARTIFACTS",
    "ReleaseReadinessError",
    "build_release_readiness",
    "build_release_readiness_from_suite_result",
    "load_suite_result",
    "render_release_readiness_markdown",
    "write_release_readiness_json",
    "write_release_readiness_markdown",
]
