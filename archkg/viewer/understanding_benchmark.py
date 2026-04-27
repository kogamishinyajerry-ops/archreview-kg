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


def load_expected(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text("utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"expected benchmark spec must be a JSON object: {path}")
    return {str(key): value for key, value in raw.items()}


def write_json_report(result: Mapping[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), "utf-8")
    return path


def write_markdown_report(result: Mapping[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_markdown_report(result), "utf-8")
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
    "load_expected",
    "render_markdown_report",
    "run_understanding_benchmark",
    "write_json_report",
    "write_markdown_report",
]
