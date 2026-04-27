"""Benchmark harness for drawing-understanding payloads.

This evaluates what the recognizer says it found: component counts,
semantic kinds, evidence signals, and benchmark booleans. It does not
evaluate building-code compliance.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from archkg.viewer.drawing_understanding import load_or_build_drawing_understanding
from archkg.viewer.ocr_diagnostics import build_ocr_diagnostics

DRAFT_COMPONENT_COUNT_KEYS = (
    "rooms",
    "doors",
    "corridors",
    "stairs",
    "dimensions",
    "ocr_texts",
)
KNOWN_GAP_STATUS = "known_gap"


def run_understanding_benchmark(
    run_dir: Path,
    expected: Mapping[str, Any],
) -> dict[str, Any]:
    payload = _load_understanding_payload(run_dir)
    checks = _checks(payload, expected)
    passed_count = sum(1 for check in checks if check["passed"])
    score = passed_count / len(checks) if checks else 1.0
    min_score = _float(expected.get("min_score"), default=1.0)
    passed = score >= min_score and all(check["passed"] for check in checks)
    return {
        "benchmark_id": _str(expected.get("benchmark_id")) or run_dir.name,
        "passed": passed,
        "score": round(score, 4),
        "min_score": min_score,
        "checks": checks,
    }


def run_understanding_benchmark_suite(manifest_path: Path) -> dict[str, Any]:
    manifest = load_suite_manifest(manifest_path)
    base_dir = manifest_path.parent
    suite_cases = [
        _run_suite_case(base_dir, index=index, raw_case=raw_case)
        for index, raw_case in enumerate(_list(manifest.get("cases")), start=1)
    ]
    known_gap_count = sum(1 for case in suite_cases if case.get("status") == KNOWN_GAP_STATUS)
    pending_count = sum(
        1
        for case in suite_cases
        if case.get("passed") is None and case.get("status") != KNOWN_GAP_STATUS
    )
    failed_count = sum(1 for case in suite_cases if case.get("passed") is False)
    active_count = len(suite_cases) - pending_count - known_gap_count
    return {
        "schema_version": "understanding_benchmark_suite_result.v1",
        "suite_id": _str(manifest.get("suite_id")) or manifest_path.stem,
        "passed": failed_count == 0,
        "active_count": active_count,
        "pending_count": pending_count,
        "known_gap_count": known_gap_count,
        "failed_count": failed_count,
        "cases": suite_cases,
    }


def author_expected_benchmark_spec(
    run_dir: Path,
    *,
    benchmark_id: str | None = None,
    min_score: float = 1.0,
) -> dict[str, Any]:
    payload = _load_understanding_payload(run_dir)
    spec = {
        "schema_version": "understanding_benchmark_expected.v1",
        "benchmark_id": benchmark_id or run_dir.name,
        "min_score": min_score,
        "review_required": True,
        "source_schema_version": _str(payload.get("schema_version")),
        "drawing_type": _str(payload.get("drawing_type")),
        "likely_design_contains": _str(payload.get("likely_design")),
        "component_counts": _draft_component_counts(payload),
        "required_semantic_kinds": _draft_semantic_kinds(payload),
        "required_evidence_signals": _draft_evidence_signals(payload),
        "required_benchmark_signals": _draft_benchmark_signals(payload),
        "authoring_note": (
            "Draft generated from current recognition output; review and adjust "
            "before promoting a real drawing case to active benchmark status."
        ),
    }
    text_inventory = _draft_text_inventory(payload)
    if text_inventory:
        spec["text_inventory"] = text_inventory
    return spec


def load_expected(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text("utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"expected benchmark spec must be a JSON object: {path}")
    return {str(key): value for key, value in raw.items()}


def load_suite_manifest(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text("utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"benchmark suite manifest must be a JSON object: {path}")
    return {str(key): value for key, value in raw.items()}


def write_json_report(result: Mapping[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), "utf-8")
    return path


def write_expected_benchmark_spec(result: Mapping[str, Any], path: Path) -> Path:
    return write_json_report(result, path)


def write_suite_json_report(result: Mapping[str, Any], path: Path) -> Path:
    return write_json_report(result, path)


def write_markdown_report(result: Mapping[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_markdown_report(result), "utf-8")
    return path


def write_suite_markdown_report(result: Mapping[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_suite_markdown_report(result), "utf-8")
    return path


def render_markdown_report(result: Mapping[str, Any]) -> str:
    status = "PASS" if result.get("passed") else "FAIL"
    lines = [
        f"# Drawing Understanding Benchmark: {_str(result.get('benchmark_id'))}",
        "",
        f"Status: {status}",
        f"Score: {_float(result.get('score'), default=0.0):.2f}",
        "",
        "| Check | Status | Expected | Actual |",
        "|---|---:|---|---|",
    ]
    for raw_check in _list(result.get("checks")):
        if not isinstance(raw_check, Mapping):
            continue
        check_status = "PASS" if raw_check.get("passed") else "FAIL"
        lines.append(
            "| "
            f"{_str(raw_check.get('name'))} | "
            f"{check_status} | "
            f"{_format_cell(raw_check.get('expected'))} | "
            f"{_format_cell(raw_check.get('actual'))} |"
        )
    lines.append("")
    return "\n".join(lines)


def render_suite_markdown_report(result: Mapping[str, Any]) -> str:
    status = "PASS" if result.get("passed") else "FAIL"
    lines = [
        f"# Drawing Understanding Benchmark Suite: {_str(result.get('suite_id'))}",
        "",
        f"Status: {status}",
        (
            "Cases: "
            f"active={_int(result.get('active_count'))}, "
            f"pending={_int(result.get('pending_count'))}, "
            f"known_gap={_int(result.get('known_gap_count'))}, "
            f"failed={_int(result.get('failed_count'))}"
        ),
        "",
        "| Case | Fixture | Status | Score |",
        "|---|---|---:|---:|",
    ]
    for raw_case in _list(result.get("cases")):
        if not isinstance(raw_case, Mapping):
            continue
        score = raw_case.get("score")
        score_text = f"{_float(score, default=0.0):.2f}" if score is not None else "-"
        lines.append(
            "| "
            f"{_str(raw_case.get('case_id'))} | "
            f"{_str(raw_case.get('fixture_kind'))} | "
            f"{_str(raw_case.get('status'))} | "
            f"{score_text} |"
        )
    lines.append("")
    return "\n".join(lines)


def _run_suite_case(base_dir: Path, *, index: int, raw_case: object) -> dict[str, Any]:
    if not isinstance(raw_case, Mapping):
        return _suite_error_case(
            case_id=f"case-{index}",
            fixture_kind="unknown",
            error="case must be a JSON object",
        )

    case_id = _str(raw_case.get("case_id")) or f"case-{index}"
    fixture_kind = _str(raw_case.get("fixture_kind")) or "unknown"
    manifest_status = _str(raw_case.get("status")) or "active"
    if manifest_status not in {"active", KNOWN_GAP_STATUS}:
        return _pending_suite_case(case_id, fixture_kind, manifest_status, raw_case)

    run_dir_raw = _str(raw_case.get("run_dir"))
    if not run_dir_raw:
        return _suite_error_case(
            case_id=case_id,
            fixture_kind=fixture_kind,
            error="run_dir missing",
        )
    run_dir = _resolve_suite_path(base_dir, run_dir_raw)
    if not run_dir.exists():
        return _suite_error_case(
            case_id=case_id,
            fixture_kind=fixture_kind,
            error=f"run_dir not found: {run_dir}",
        )
    if not run_dir.is_dir():
        return _suite_error_case(
            case_id=case_id,
            fixture_kind=fixture_kind,
            error=f"run_dir is not a directory: {run_dir}",
        )

    expect_raw = _str(raw_case.get("expect"))
    if not expect_raw:
        return _suite_error_case(
            case_id=case_id,
            fixture_kind=fixture_kind,
            error="expect missing",
        )
    expect_path = _resolve_suite_path(base_dir, expect_raw)
    if not expect_path.exists():
        return _suite_error_case(
            case_id=case_id,
            fixture_kind=fixture_kind,
            error=f"expect not found: {expect_path}",
        )

    try:
        result = run_understanding_benchmark(run_dir, load_expected(expect_path))
    except Exception as exc:
        return _suite_error_case(
            case_id=case_id,
            fixture_kind=fixture_kind,
            error=f"{type(exc).__name__}: {exc}",
        )

    if manifest_status == KNOWN_GAP_STATUS:
        return _known_gap_suite_case(case_id, fixture_kind, result, raw_case)

    return {
        "case_id": case_id,
        "fixture_kind": fixture_kind,
        "status": "pass" if result["passed"] else "fail",
        "passed": result["passed"],
        "score": result["score"],
        "benchmark_id": result["benchmark_id"],
        "min_score": result["min_score"],
        "checks": result["checks"],
    }


def _known_gap_suite_case(
    case_id: str,
    fixture_kind: str,
    result: Mapping[str, Any],
    raw_case: Mapping[str, Any],
) -> dict[str, Any]:
    benchmark_passed = bool(result.get("passed"))
    if benchmark_passed:
        return {
            "case_id": case_id,
            "fixture_kind": fixture_kind,
            "status": "unexpected_pass",
            "passed": False,
            "benchmark_passed": True,
            "score": result.get("score"),
            "benchmark_id": result.get("benchmark_id"),
            "checks": result.get("checks"),
            "notes": _str(raw_case.get("notes")),
            "detail": "known_gap case now passes; promote it to active or review the expected inventory",
        }
    return {
        "case_id": case_id,
        "fixture_kind": fixture_kind,
        "status": KNOWN_GAP_STATUS,
        "passed": None,
        "benchmark_passed": False,
        "score": result.get("score"),
        "benchmark_id": result.get("benchmark_id"),
        "checks": result.get("checks"),
        "notes": _str(raw_case.get("notes")),
    }


def _pending_suite_case(
    case_id: str,
    fixture_kind: str,
    status: str,
    raw_case: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "fixture_kind": fixture_kind,
        "status": status,
        "passed": None,
        "source_url": _str(raw_case.get("source_url")),
        "notes": _str(raw_case.get("notes")),
    }


def _suite_error_case(case_id: str, fixture_kind: str, error: str) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "fixture_kind": fixture_kind,
        "status": "failed",
        "passed": False,
        "error": error,
    }


def _resolve_suite_path(base_dir: Path, raw: str) -> Path:
    path = Path(raw).expanduser()
    if path.is_absolute():
        return path
    return base_dir / path


def _draft_component_counts(payload: Mapping[str, Any]) -> dict[str, dict[str, int]]:
    raw_counts = payload.get("component_counts")
    if not isinstance(raw_counts, Mapping):
        return {}
    counts: dict[str, dict[str, int]] = {}
    for key in DRAFT_COMPONENT_COUNT_KEYS:
        value = raw_counts.get(key)
        if type(value) is int and value > 0:
            counts[key] = {"exact": value}
    return counts


def _draft_semantic_kinds(payload: Mapping[str, Any]) -> list[str]:
    kinds: list[str] = []
    for row in _list(payload.get("component_inventory")):
        if isinstance(row, Mapping):
            kinds.append(_str(row.get("semantic_kind")))
    return _unique_nonempty(kinds)


def _draft_evidence_signals(payload: Mapping[str, Any]) -> list[str]:
    profile = payload.get("drawing_profile")
    if not isinstance(profile, Mapping):
        return []
    return _unique_nonempty(_str_list(profile.get("evidence_signals")))


def _draft_benchmark_signals(payload: Mapping[str, Any]) -> dict[str, bool]:
    raw_signals = payload.get("benchmark_signals")
    if not isinstance(raw_signals, Mapping):
        return {}
    return {key: True for key, value in raw_signals.items() if isinstance(key, str) and value is True}


def _draft_text_inventory(payload: Mapping[str, Any]) -> dict[str, Any]:
    raw = payload.get("text_inventory")
    if not isinstance(raw, Mapping):
        return {}
    out: dict[str, Any] = {}
    for section in ("room_label_counts", "door_or_opening_size_label_counts"):
        raw_counts = raw.get(section)
        if isinstance(raw_counts, Mapping):
            counts = {
                str(key): value
                for key, value in raw_counts.items()
                if isinstance(key, str) and isinstance(value, int) and value > 0
            }
            if counts:
                out[section] = counts
    dimensions = _str_list(raw.get("major_dimension_texts"))
    if dimensions:
        out["major_dimension_texts"] = dimensions
    return out


def _load_understanding_payload(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "drawing_understanding.json"
    if path.exists():
        raw = json.loads(path.read_text("utf-8"))
        if isinstance(raw, dict) and _is_current_payload(raw):
            return {str(key): value for key, value in raw.items()}

    primitives_path = run_dir / "primitives.json"
    graph_path = run_dir / "entity_graph.json"
    if not primitives_path.exists() or not graph_path.exists():
        raise FileNotFoundError(
            "benchmark needs drawing_understanding.json or primitives.json + entity_graph.json"
        )
    primitives = _json_object(primitives_path)
    graph = _json_object(graph_path)
    ocr_diagnostics = build_ocr_diagnostics(primitives, graph)
    return load_or_build_drawing_understanding(run_dir, primitives, graph, ocr_diagnostics)


def _checks(payload: Mapping[str, Any], expected: Mapping[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    if "drawing_type" in expected:
        actual = payload.get("drawing_type")
        wanted = expected.get("drawing_type")
        checks.append(_check("drawing_type", actual == wanted, wanted, actual))
    if "likely_design_contains" in expected:
        actual = _str(payload.get("likely_design"))
        wanted = _str(expected.get("likely_design_contains"))
        checks.append(_check("likely_design_contains", wanted in actual, wanted, actual))

    text_inventory = expected.get("text_inventory")
    if isinstance(text_inventory, Mapping):
        checks.extend(_text_inventory_checks(payload, text_inventory))

    count_specs = expected.get("component_counts")
    if isinstance(count_specs, Mapping):
        actual_counts = payload.get("component_counts")
        if not isinstance(actual_counts, Mapping):
            actual_counts = {}
        for key, spec in count_specs.items():
            actual = _int(actual_counts.get(key))
            ok = _count_matches(actual, spec)
            checks.append(_check(f"component_counts:{key}", ok, spec, actual))

    actual_kinds = sorted(
        {
            kind
            for row in _list(payload.get("component_inventory"))
            if isinstance(row, Mapping) and isinstance((kind := row.get("semantic_kind")), str)
        }
    )
    for kind in _str_list(expected.get("required_semantic_kinds")):
        checks.append(
            _check(
                f"required_semantic_kind:{kind}",
                kind in actual_kinds,
                kind,
                actual_kinds,
                "missing semantic kind in component_inventory",
            )
        )

    profile = payload.get("drawing_profile")
    signals = []
    if isinstance(profile, Mapping):
        signals = _str_list(profile.get("evidence_signals"))
    for signal in _str_list(expected.get("required_evidence_signals")):
        checks.append(
            _check(
                f"required_evidence_signal:{signal}",
                signal in signals,
                signal,
                signals,
                "missing evidence signal in drawing_profile",
            )
        )

    benchmark_signals = payload.get("benchmark_signals")
    if not isinstance(benchmark_signals, Mapping):
        benchmark_signals = {}
    required_benchmark_signals = expected.get("required_benchmark_signals")
    if isinstance(required_benchmark_signals, Mapping):
        for key, wanted in required_benchmark_signals.items():
            actual = benchmark_signals.get(key)
            checks.append(
                _check(
                    f"benchmark_signal:{key}",
                    actual is wanted,
                    wanted,
                    actual,
                    "benchmark signal mismatch",
                )
            )
    return checks


def _text_inventory_checks(
    payload: Mapping[str, Any],
    expected_inventory: Mapping[str, Any],
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    actual_inventory = payload.get("text_inventory")
    if not isinstance(actual_inventory, Mapping):
        actual_inventory = {}
    for section in ("room_label_counts", "door_or_opening_size_label_counts"):
        expected_counts = expected_inventory.get(section)
        actual_counts = actual_inventory.get(section)
        if not isinstance(expected_counts, Mapping):
            continue
        if not isinstance(actual_counts, Mapping):
            actual_counts = {}
        for key, wanted in expected_counts.items():
            actual = _int(actual_counts.get(key))
            checks.append(
                _check(
                    f"text_inventory:{section}:{key}",
                    actual == wanted,
                    wanted,
                    actual,
                    "text inventory count mismatch",
                )
            )

    actual_dimensions = _str_list(actual_inventory.get("major_dimension_texts"))
    for text in _str_list(expected_inventory.get("major_dimension_texts")):
        checks.append(
            _check(
                f"text_inventory:major_dimension_text:{text}",
                text in actual_dimensions,
                text,
                actual_dimensions,
                "missing major dimension text",
            )
        )
    return checks


def _check(
    name: str,
    passed: bool,
    expected: object,
    actual: object,
    detail: str = "",
) -> dict[str, Any]:
    out = {
        "name": name,
        "passed": passed,
        "expected": expected,
        "actual": actual,
    }
    if detail and not passed:
        out["detail"] = detail
    return out


def _count_matches(actual: int, spec: object) -> bool:
    if isinstance(spec, int):
        return actual == spec
    if not isinstance(spec, Mapping):
        return False
    exact = spec.get("exact")
    if isinstance(exact, int) and actual != exact:
        return False
    min_value = spec.get("min")
    if isinstance(min_value, int) and actual < min_value:
        return False
    max_value = spec.get("max")
    if isinstance(max_value, int) and actual > max_value:
        return False
    return True


def _is_current_payload(raw: Mapping[str, Any]) -> bool:
    return (
        raw.get("schema_version") == "drawing_understanding.v2"
        and isinstance(raw.get("component_inventory"), list)
        and isinstance(raw.get("drawing_profile"), Mapping)
        and isinstance(raw.get("benchmark_signals"), Mapping)
    )


def _json_object(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text("utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"expected JSON object: {path}")
    return {str(key): value for key, value in raw.items()}


def _format_cell(value: object) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def _str_list(raw: object) -> list[str]:
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, str)]


def _unique_nonempty(raw: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in raw:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _list(raw: object) -> list[Any]:
    return raw if isinstance(raw, list) else []


def _str(raw: object) -> str:
    return raw if isinstance(raw, str) else ""


def _int(raw: object) -> int:
    return raw if isinstance(raw, int) else 0


def _float(raw: object, *, default: float) -> float:
    if isinstance(raw, (int, float, str)):
        try:
            return float(raw)
        except ValueError:
            return default
    return default


__all__ = [
    "author_expected_benchmark_spec",
    "load_expected",
    "load_suite_manifest",
    "render_markdown_report",
    "render_suite_markdown_report",
    "run_understanding_benchmark",
    "run_understanding_benchmark_suite",
    "write_expected_benchmark_spec",
    "write_json_report",
    "write_markdown_report",
    "write_suite_json_report",
    "write_suite_markdown_report",
]
