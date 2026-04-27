from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any

STATUS_ORDER = (
    "ready",
    "missing_input",
    "low_confidence",
    "manual_only",
    "not_applicable",
    "unsupported_entity",
)

BLOCKED_STATUSES = {"missing_input", "low_confidence", "unsupported_entity"}

STATUS_META = {
    "ready": {"label": "可运行", "tone": "ok"},
    "missing_input": {"label": "缺输入", "tone": "warn"},
    "low_confidence": {"label": "低置信", "tone": "warn"},
    "manual_only": {"label": "人工核对", "tone": ""},
    "not_applicable": {"label": "不适用", "tone": ""},
    "unsupported_entity": {"label": "无实体", "tone": "warn"},
}


def load_rule_readiness_view(out_dir: Path, *, limit: int = 12) -> dict[str, Any]:
    path = out_dir / "rule_input_readiness.json"
    if not path.exists():
        return _missing_view("rule_input_readiness.json missing")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return _missing_view(f"could not read rule_input_readiness.json: {exc}")
    if not isinstance(raw, dict):
        return _missing_view("rule_input_readiness.json is not an object")
    return build_rule_readiness_view(raw, limit=limit)


def build_rule_readiness_view(
    payload: Mapping[str, Any],
    *,
    limit: int = 12,
) -> dict[str, Any]:
    rules = _rule_rows(payload.get("rules"))
    summary = _summary(payload.get("summary"), rules)
    summary_rows = [
        {
            "status": status,
            "label": STATUS_META[status]["label"],
            "count": summary[status],
            "tone": STATUS_META[status]["tone"],
            "class_name": f"status-{status.replace('_', '-')}",
        }
        for status in STATUS_ORDER
    ]

    non_ready_rules = [
        _display_rule(row)
        for row in rules
        if _string(row.get("status")) != "ready"
    ][:limit]
    source_rows = _source_rows(rules)
    blocked_count = sum(summary[status] for status in BLOCKED_STATUSES)
    total = sum(summary.values())
    return {
        "available": True,
        "schema_version": _string(payload.get("schema_version")) or "unknown",
        "total": total,
        "summary_rows": summary_rows,
        "source_rows": source_rows,
        "non_ready_rules": non_ready_rules,
        "non_ready_total": len([row for row in rules if _string(row.get("status")) != "ready"]),
        "blocked_count": blocked_count,
        "omitted_non_ready_count": max(
            0,
            len([row for row in rules if _string(row.get("status")) != "ready"]) - limit,
        ),
        "warning_text": "缺输入不等于通过; readiness 只解释本次 run 的证据输入状态, 不改变 issues.json.",
        "artifact_name": "rule_input_readiness.json",
        "unavailable_reason": "",
    }


def _missing_view(reason: str) -> dict[str, Any]:
    return {
        "available": False,
        "schema_version": "missing",
        "total": 0,
        "summary_rows": [],
        "source_rows": [],
        "non_ready_rules": [],
        "non_ready_total": 0,
        "blocked_count": 0,
        "omitted_non_ready_count": 0,
        "warning_text": "规则输入就绪度暂无数据; 缺失 readiness 不代表通过.",
        "artifact_name": "rule_input_readiness.json",
        "unavailable_reason": reason,
    }


def _rule_rows(raw: object) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    return [dict(row) for row in raw if isinstance(row, dict)]


def _summary(raw: object, rules: list[dict[str, Any]]) -> dict[str, int]:
    if isinstance(raw, dict):
        return {
            status: _int(raw.get(status))
            for status in STATUS_ORDER
        }
    counts: Counter[str] = Counter(
        _string(row.get("status")) for row in rules
    )
    return {status: int(counts.get(status, 0)) for status in STATUS_ORDER}


def _display_rule(row: Mapping[str, Any]) -> dict[str, Any]:
    status = _string(row.get("status")) or "unknown"
    meta = STATUS_META.get(status, {"label": status, "tone": ""})
    missing_inputs = _strings(row.get("missing_inputs"))
    required_inputs = _strings(row.get("required_inputs"))
    available_inputs = _strings(row.get("available_inputs"))
    source = _string(row.get("source")) or "unknown"
    return {
        "rule_id": _string(row.get("rule_id")) or "unknown",
        "status": status,
        "status_label": meta["label"],
        "status_class": f"status-{status.replace('_', '-')}",
        "source": source,
        "source_label": _source_label(source),
        "severity": _string(row.get("severity")) or "unknown",
        "missing_inputs": ", ".join(missing_inputs) if missing_inputs else "—",
        "required_inputs": ", ".join(required_inputs) if required_inputs else "—",
        "available_inputs": ", ".join(available_inputs) if available_inputs else "—",
        "reason": _string(row.get("reason")) or "—",
    }


def _source_rows(rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    for row in rules:
        status = _string(row.get("status"))
        if status not in BLOCKED_STATUSES:
            continue
        source = _string(row.get("source")) or "unknown"
        counts.update([source])
    return [
        {
            "source": source,
            "source_label": _source_label(source),
            "count": count,
        }
        for source, count in counts.most_common()
    ]


def _source_label(source: str) -> str:
    labels: list[str] = []
    if "project_meta" in source:
        labels.append("ProjectMeta")
    if "entity_graph" in source:
        labels.append("实体图谱")
    if "room_schedule" in source:
        labels.append("房间排表")
    if "stair_schedule" in source:
        labels.append("楼梯排表")
    if "ocr" in source:
        labels.append("OCR/text")
    if "applicability" in source:
        labels.append("适用性过滤")
    if "knowledge" in source:
        labels.append("知识库")
    if not labels:
        labels.append(source)
    return " + ".join(labels)


def _strings(raw: object) -> list[str]:
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, str)]


def _string(raw: object) -> str:
    return raw if isinstance(raw, str) else ""


def _int(raw: object) -> int:
    if isinstance(raw, bool):
        return int(raw)
    if isinstance(raw, int):
        return raw
    return 0
