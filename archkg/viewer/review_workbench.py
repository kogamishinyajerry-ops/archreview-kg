"""Review workbench summary artifact.

The workbench artifact is a compact entry point for humans. It summarizes
which evidence surfaces exist in a run and what the reviewer should inspect
first. It does not change rule output, review state, or benchmark scoring.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "review_workbench.v1"


def build_review_workbench(
    *,
    source_pdf: Path,
    mode: str,
    drawing_understanding: Mapping[str, Any] | None = None,
    rule_readiness: Mapping[str, Any] | None = None,
    issues: Sequence[Mapping[str, Any]] = (),
    review_state: Mapping[str, Any] | None = None,
    sheet_classification: Mapping[str, Any] | None = None,
    sheet_routing: Mapping[str, Any] | None = None,
    sheet_graphs: Mapping[str, Any] | None = None,
    sheet_issues: Mapping[str, Any] | None = None,
    sheet_region_candidates: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a stable summary for the review workbench."""

    drawing_understanding = drawing_understanding or {}
    rule_readiness = rule_readiness or {}
    review_state = review_state or {}
    sheet_classification = sheet_classification or {}
    sheet_routing = sheet_routing or {}
    sheet_graphs = sheet_graphs or {}
    sheet_issues = sheet_issues or {}
    sheet_region_candidates = sheet_region_candidates or {}

    component_counts = _mapping(drawing_understanding.get("component_counts"))
    readiness_summary = _mapping(rule_readiness.get("summary"))
    review_summary = _mapping(review_state.get("summary"))
    issue_summary = _issue_summary(issues)
    classification_summary = _mapping(sheet_classification.get("summary"))

    summary = {
        "mode": mode,
        "drawing_type": _str(drawing_understanding.get("drawing_type")) or "unknown",
        "rooms": _int(component_counts.get("rooms")),
        "doors": _int(component_counts.get("doors")),
        "corridors": _int(component_counts.get("corridors")),
        "stairs": _int(component_counts.get("stairs")),
        "dimensions": _int(component_counts.get("dimensions")),
        "issue_count": issue_summary["total"],
        "issue_error_count": issue_summary["error"],
        "issue_warning_count": issue_summary["warning"],
        "issue_info_count": issue_summary["info"],
        "ready_rules": _int(readiness_summary.get("ready")),
        "blocked_rules": _int(readiness_summary.get("missing_input"))
        + _int(readiness_summary.get("low_confidence")),
        "candidate_review_states": _int(review_summary.get("candidate")),
        "plan_sheet_count": _int(classification_summary.get("plan")),
        "sheet_graph_count": _int(sheet_graphs.get("graph_count")),
        "sheet_issue_count": _int(sheet_issues.get("issue_count")),
    }

    artifact_statuses = [
        _artifact_status(
            "图纸理解",
            "drawing_understanding.json",
            bool(drawing_understanding),
            f"{summary['rooms']} rooms / {summary['doors']} doors / {summary['dimensions']} dimensions",
        ),
        _artifact_status(
            "规则输入就绪度",
            "rule_input_readiness.json",
            bool(rule_readiness),
            f"{summary['ready_rules']} ready / {summary['blocked_rules']} blocked",
        ),
        _artifact_status(
            "Sheet 分类",
            "sheet_classification.json",
            bool(sheet_classification),
            f"{summary['plan_sheet_count']} plan sheets",
        ),
        _artifact_status(
            "Sheet 路由",
            "sheet_routing.json",
            bool(sheet_routing),
            _str(sheet_routing.get("mode")) or "missing",
        ),
        _artifact_status(
            "Sheet Graphs",
            "sheet_graphs.json",
            bool(sheet_graphs),
            f"{summary['sheet_graph_count']} graph(s)",
        ),
        _artifact_status(
            "Sheet Issue Preview",
            "sheet_issues.json",
            bool(sheet_issues),
            f"{summary['sheet_issue_count']} candidate issue(s)",
        ),
        _artifact_status(
            "候选区域",
            "sheet_region_candidates.json",
            bool(sheet_region_candidates),
            f"{len(_list(sheet_region_candidates.get('candidates')))} candidate region(s)",
        ),
        _artifact_status(
            "Issue 生命周期",
            "review_state.json",
            bool(review_state),
            f"{summary['candidate_review_states']} candidate state(s)",
        ),
    ]

    warnings = _workbench_warnings(summary, artifact_statuses)
    action_links = _action_links(summary)

    return {
        "schema_version": SCHEMA_VERSION,
        "source_pdf": str(source_pdf),
        "mode": mode,
        "summary": summary,
        "artifact_statuses": artifact_statuses,
        "action_links": action_links,
        "warnings": warnings,
        "next_actions": _next_actions(warnings, summary),
        "note": (
            "Workbench summary aggregates existing review artifacts for navigation. "
            "It does not mutate issues.json, review_state.json, or rule results."
        ),
    }


def write_review_workbench(payload: Mapping[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), "utf-8")
    return path


def load_review_workbench_view(out_dir: Path) -> dict[str, Any]:
    path = out_dir / "review_workbench.json"
    if not path.exists():
        return {
            "available": False,
            "artifact_name": "review_workbench.json",
            "summary": {},
            "artifact_statuses": [],
            "action_links": [],
            "warnings": ["review_workbench.json 暂无数据; 请查看下方单项 evidence 面板。"],
            "next_actions": [],
        }
    try:
        raw = json.loads(path.read_text("utf-8"))
    except Exception as exc:
        return {
            "available": False,
            "artifact_name": "review_workbench.json",
            "summary": {},
            "artifact_statuses": [],
            "action_links": [],
            "warnings": [f"could not read review_workbench.json: {exc}"],
            "next_actions": [],
        }
    if not isinstance(raw, dict):
        return {
            "available": False,
            "artifact_name": "review_workbench.json",
            "summary": {},
            "artifact_statuses": [],
            "action_links": [],
            "warnings": ["review_workbench.json is not an object"],
            "next_actions": [],
        }
    return {
        "available": True,
        "artifact_name": "review_workbench.json",
        "summary": _mapping(raw.get("summary")),
        "artifact_statuses": [
            row for row in _list(raw.get("artifact_statuses")) if isinstance(row, dict)
        ],
        "action_links": [
            row for row in _list(raw.get("action_links")) if isinstance(row, dict)
        ],
        "warnings": [item for item in _list(raw.get("warnings")) if isinstance(item, str)],
        "next_actions": [
            item for item in _list(raw.get("next_actions")) if isinstance(item, str)
        ],
        "note": _str(raw.get("note")),
    }


def _artifact_status(label: str, artifact: str, available: bool, detail: str) -> dict[str, Any]:
    return {
        "label": label,
        "artifact": artifact,
        "available": available,
        "status": "available" if available else "missing",
        "detail": detail if available else "missing",
    }


def _workbench_warnings(
    summary: Mapping[str, Any],
    artifact_statuses: Sequence[Mapping[str, Any]],
) -> list[str]:
    warnings: list[str] = []
    missing = [row["artifact"] for row in artifact_statuses if row.get("available") is False]
    if missing:
        warnings.append("缺少 workbench evidence artifact: " + ", ".join(missing))
    if _int(summary.get("blocked_rules")) > 0:
        warnings.append("存在 missing_input 或 low_confidence 规则; 缺输入不等于通过。")
    if _int(summary.get("sheet_graph_count")) > 1:
        warnings.append("存在多个 plan sheet graph; per-sheet issue preview 尚未并入主复核生命周期。")
    if _int(summary.get("issue_count")) and _int(summary.get("candidate_review_states")):
        warnings.append("规则输出仍是 candidate; 需要人工确认或驳回。")
    return warnings


def _action_links(summary: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [
        _action_link(
            "check_layers",
            "核对 source / overlay",
            "#panel-layer",
            "source_preview.png",
            "ready",
            10,
            "先对照 source、entity overlay、annotated 图层。",
        ),
        _action_link(
            "component_inventory",
            "核对 component inventory",
            "#panel-understanding",
            "drawing_understanding.json",
            "review",
            20,
            "确认图纸类型、部件数量、尺寸证据和 uncertainty flags。",
        ),
        _action_link(
            "readiness_blockers",
            "处理 readiness blockers",
            "#panel-readiness",
            "rule_input_readiness.json",
            "attention" if _int(summary.get("blocked_rules")) > 0 else "ready",
            30,
            "先补 missing_input / low_confidence, 避免把缺输入当通过。",
        ),
        _action_link(
            "sheet_evidence",
            "核对 sheet evidence",
            "#panel-sheet-classification",
            "sheet_classification.json",
            "review" if _int(summary.get("sheet_graph_count")) > 1 else "ready",
            40,
            "检查 sheet 分类、路由、per-sheet graphs 和 issue preview。",
        ),
        _action_link(
            "region_candidates",
            "确认候选区域",
            "#panel-sheet-regions",
            "sheet_region_candidates.json",
            "review",
            50,
            "需要人工确认 design/title/schedule/legend 候选区, 不默认裁剪。",
        ),
        _action_link(
            "candidate_issues",
            "确认 candidate issues",
            "#panel-issues",
            "issues.json",
            "attention" if _int(summary.get("issue_count")) > 0 else "ready",
            60,
            "逐条确认、驳回或标记 needs_info。",
        ),
        _action_link(
            "review_state",
            "更新 review state",
            "#panel-issues",
            "review_state.json",
            "attention" if _int(summary.get("candidate_review_states")) > 0 else "ready",
            70,
            "复核状态写入 review_state.json, 不回写 issues.json。",
        ),
        _action_link(
            "open_report",
            "打开 report / clauses",
            "#panel-report",
            "report.md",
            "ready",
            80,
            "查看条文触达、报告正文和人工核对提醒。",
        ),
    ]


def _action_link(
    action_id: str,
    label: str,
    target: str,
    artifact: str,
    status: str,
    priority: int,
    reason: str,
) -> dict[str, Any]:
    return {
        "id": action_id,
        "label": label,
        "target": target,
        "artifact": artifact,
        "status": status,
        "priority": priority,
        "reason": reason,
    }


def _next_actions(warnings: Sequence[str], summary: Mapping[str, Any]) -> list[str]:
    actions: list[str] = []
    if _int(summary.get("blocked_rules")) > 0:
        actions.append("先补齐 rule_input_readiness.json 标出的缺失输入。")
    if _int(summary.get("sheet_graph_count")) > 1:
        actions.append("逐页核对 sheet_graphs.json 与 sheet_issues.json, 再决定是否进入聚合。")
    if _int(summary.get("issue_count")) > 0:
        actions.append("在 review_state.json 中确认、驳回或标记 needs_info。")
    if not actions and not warnings:
        actions.append("复核 source preview、entity overlay 与 report.md 后归档本次 run。")
    return actions


def _issue_summary(issues: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for issue in issues:
        counter.update([_str(issue.get("severity")) or "info"])
    total = sum(counter.values())
    return {
        "total": total,
        "error": int(counter.get("error", 0)),
        "warning": int(counter.get("warning", 0)),
        "info": int(counter.get("info", 0)),
    }


def _mapping(raw: object) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        return {}
    return {str(key): value for key, value in raw.items()}


def _list(raw: object) -> list[Any]:
    return raw if isinstance(raw, list) else []


def _str(raw: object) -> str:
    return raw if isinstance(raw, str) else ""


def _int(raw: object) -> int:
    return raw if isinstance(raw, int) else 0


__all__ = [
    "build_review_workbench",
    "load_review_workbench_view",
    "write_review_workbench",
]
