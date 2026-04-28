from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "reviewer_task_sequence.v1"
MUTATION_POLICY = "sequencing_only_no_issue_state_mutation"
BOUNDARY_WARNING = (
    "Reviewer task sequence orders existing evidence for human review only; it "
    "does not confirm issues, mutate issues.json or review_state.json, promote "
    "sheet preview issues, or certify drawing compliance."
)

BLOCKING_READINESS_STATUSES = {
    "missing_input",
    "low_confidence",
    "unsupported_entity",
}
OPEN_REVIEW_STATUSES = {"candidate", "needs_info"}
SEVERITY_PRIORITY = {"error": 40, "warning": 50, "info": 60}


def build_reviewer_task_sequence(
    *,
    run_dir: Path,
    source_pdf: Path,
    mode: str,
    review_workbench: Mapping[str, Any] | None = None,
    rule_readiness: Mapping[str, Any] | None = None,
    issues: Sequence[Mapping[str, Any]] = (),
    review_state: Mapping[str, Any] | None = None,
    sheet_issue_review_queue: Mapping[str, Any] | None = None,
    quality_flags: Sequence[str] = (),
    max_readiness_tasks: int = 8,
    max_primary_issue_tasks: int = 12,
    max_preview_sheet_tasks: int = 8,
) -> dict[str, Any]:
    review_workbench = review_workbench or {}
    rule_readiness = rule_readiness or {}
    review_state = review_state or {}
    sheet_issue_review_queue = sheet_issue_review_queue or {}
    tasks: list[dict[str, Any]] = []

    tasks.append(
        _task(
            task_id="task-001-open-workbench",
            stage="intake",
            priority=10,
            title="打开工作台并确认运行边界",
            action="open_index_and_read_boundary",
            artifact="index.html",
            target="#panel-workbench",
            reason="先确认本 run 是 full review 还是 inspect_only, 并读取证据边界。",
        )
    )
    if quality_flags:
        tasks.append(
            _task(
                task_id="task-010-recognition-quality",
                stage="recognition",
                priority=15,
                title="先处理识图质量提示",
                action="inspect_quality_flags",
                artifact="run_meta.json",
                target="#panel-layer",
                reason="识图噪声会影响后续 issue 解读, 必须先记录明显偏差。",
                evidence={"quality_flags": list(quality_flags)},
            )
        )
    tasks.extend(_sheet_scope_tasks(review_workbench))
    tasks.extend(
        _readiness_tasks(rule_readiness, limit=max(0, max_readiness_tasks))
    )
    if mode == "inspect_only":
        tasks.append(
            _task(
                task_id="task-080-rerun-full-review",
                stage="full_review_gate",
                priority=80,
                title="识图合理后重跑完整审图",
                action="rerun_full_review",
                artifact="archkg review",
                target="archkg review <source.pdf> -o <run_dir>",
                reason="仅识图模式没有规则结论, 不能进入 issue 确认。",
            )
        )
    else:
        tasks.extend(
            _primary_issue_tasks(
                issues,
                review_state,
                limit=max(0, max_primary_issue_tasks),
            )
        )
        tasks.extend(
            _preview_sheet_tasks(
                sheet_issue_review_queue,
                limit=max(0, max_preview_sheet_tasks),
            )
        )
    tasks.extend(_handoff_tasks(run_dir))
    tasks = sorted(tasks, key=lambda item: (_int(item.get("priority")), _str(item.get("task_id"))))
    tasks = [
        {
            **task,
            "ordinal": index,
        }
        for index, task in enumerate(tasks, start=1)
    ]
    summary = _summary(tasks)
    return {
        "schema_version": SCHEMA_VERSION,
        "audience": "novice_review_engineer",
        "mode": mode,
        "source_pdf": str(source_pdf),
        "run_dir": str(run_dir),
        "mutation_policy": MUTATION_POLICY,
        "status": _sequence_status(summary),
        "summary": summary,
        "tasks": tasks,
        "do_not_use_as": [
            "drawing_compliance_certificate",
            "issue_confirmation",
            "preview_issue_promotion",
        ],
        "boundary_warning": BOUNDARY_WARNING,
        "source_artifacts": [
            "review_workbench.json",
            "rule_input_readiness.json",
            "issues.json",
            "review_state.json",
            "sheet_issue_review_queue.json",
        ],
    }


def write_reviewer_task_sequence_json(
    payload: Mapping[str, Any],
    path: Path,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_reviewer_task_sequence_markdown(
    payload: Mapping[str, Any],
    path: Path,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_reviewer_task_sequence_markdown(payload), encoding="utf-8")
    return path


def load_reviewer_task_sequence_view(
    out_dir: Path,
    *,
    limit: int = 12,
) -> dict[str, Any]:
    path = out_dir / "reviewer_task_sequence.json"
    if not path.exists():
        return _missing_view("reviewer_task_sequence.json missing")
    try:
        raw = json.loads(path.read_text("utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return _missing_view(f"could not read reviewer_task_sequence.json: {exc}")
    if not isinstance(raw, Mapping):
        return _missing_view("reviewer_task_sequence.json is not an object")
    tasks = _list_of_mappings(raw.get("tasks"))
    return {
        "available": True,
        "artifact_name": "reviewer_task_sequence.json",
        "schema_version": _str(raw.get("schema_version")) or "unknown",
        "status": _str(raw.get("status")),
        "summary": _mapping(raw.get("summary")),
        "tasks": [dict(task) for task in tasks[: max(0, limit)]],
        "omitted_task_count": max(0, len(tasks) - max(0, limit)),
        "boundary_warning": _str(raw.get("boundary_warning")) or BOUNDARY_WARNING,
        "mutation_policy": _str(raw.get("mutation_policy")) or MUTATION_POLICY,
        "unavailable_reason": "",
    }


def render_reviewer_task_sequence_markdown(payload: Mapping[str, Any]) -> str:
    summary = _mapping(payload.get("summary"))
    lines = [
        "# Reviewer Task Sequence",
        "",
        f"Status: `{_str(payload.get('status'))}`",
        f"Mode: `{_str(payload.get('mode'))}`",
        f"Mutation policy: `{_str(payload.get('mutation_policy'))}`",
        "",
        _str(payload.get("boundary_warning")),
        "",
        "## Summary",
        "",
        f"- Tasks: `{_int(summary.get('task_count'))}`",
        f"- Blocked input tasks: `{_int(summary.get('blocked_input_task_count'))}`",
        f"- Primary issue tasks: `{_int(summary.get('primary_issue_task_count'))}`",
        f"- Preview sheet tasks: `{_int(summary.get('preview_sheet_task_count'))}`",
        "",
        "## Ordered Tasks",
        "",
        "| # | Stage | Priority | Task | Artifact | Target | Reason |",
        "|---:|---|---:|---|---|---|---|",
    ]
    for task in _list_of_mappings(payload.get("tasks")):
        lines.append(
            "| "
            f"{_int(task.get('ordinal'))} | "
            f"`{_str(task.get('stage'))}` | "
            f"{_int(task.get('priority'))} | "
            f"{_str(task.get('title'))} | "
            f"`{_str(task.get('artifact'))}` | "
            f"{_str(task.get('target'))} | "
            f"{_str(task.get('reason'))} |"
        )
    lines.append("")
    return "\n".join(lines)


def _sheet_scope_tasks(review_workbench: Mapping[str, Any]) -> list[dict[str, Any]]:
    summary = _mapping(review_workbench.get("summary"))
    plan_sheet_count = _int(summary.get("plan_sheet_count"))
    sheet_graph_count = _int(summary.get("sheet_graph_count"))
    if max(plan_sheet_count, sheet_graph_count) <= 1:
        return []
    return [
        _task(
            task_id="task-020-sheet-scope",
            stage="sheet_scope",
            priority=20,
            title="确认多页 sheet 范围和 graph 路由",
            action="inspect_sheet_scope",
            artifact="sheet_classification.json / sheet_graphs.json",
            target="#panel-sheet-classification",
            reason=(
                f"本 run 有 {plan_sheet_count} 个 plan sheet / {sheet_graph_count} 个 graph; "
                "先确认哪些页进入 graph, 哪些页仍只是 source/annotated 复核。"
            ),
            evidence={
                "plan_sheet_count": plan_sheet_count,
                "sheet_graph_count": sheet_graph_count,
            },
        )
    ]


def _readiness_tasks(
    rule_readiness: Mapping[str, Any],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    rows = [
        row
        for row in _list_of_mappings(rule_readiness.get("rules"))
        if _str(row.get("status")) in BLOCKING_READINESS_STATUSES
    ]
    for index, row in enumerate(rows[:limit], start=1):
        status = _str(row.get("status"))
        rule_id = _str(row.get("rule_id")) or f"rule-{index}"
        tasks.append(
            _task(
                task_id=f"task-030-readiness-{index:03d}",
                stage="readiness",
                priority=30,
                title=f"补齐规则输入: {rule_id}",
                action="resolve_rule_input_blocker",
                artifact="rule_input_readiness.json",
                target="#panel-readiness",
                reason=_str(row.get("reason")) or f"rule readiness status is {status}",
                rule_card_id=rule_id,
                status=status,
                evidence={
                    "missing_inputs": _str_list(row.get("missing_inputs")),
                    "source": _str(row.get("source")),
                    "severity": _str(row.get("severity")),
                },
            )
        )
    if len(rows) > limit:
        tasks.append(
            _task(
                task_id="task-039-readiness-remaining",
                stage="readiness",
                priority=39,
                title="继续处理剩余 readiness blockers",
                action="continue_rule_input_blockers",
                artifact="rule_input_readiness.json",
                target="#panel-readiness",
                reason=f"另有 {len(rows) - limit} 条 blocked readiness row 未展开。",
            )
        )
    return tasks


def _primary_issue_tasks(
    issues: Sequence[Mapping[str, Any]],
    review_state: Mapping[str, Any],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    state_by_issue = {
        _str(item.get("issue_id")): item
        for item in _list_of_mappings(review_state.get("items"))
    }
    open_issues: list[Mapping[str, Any]] = []
    for issue in issues:
        issue_id = _str(issue.get("issue_id"))
        state = state_by_issue.get(issue_id, {})
        status = _str(state.get("status")) or "candidate"
        if status in OPEN_REVIEW_STATUSES:
            open_issues.append(issue)
    open_issues = sorted(
        open_issues,
        key=lambda issue: (
            SEVERITY_PRIORITY.get(_str(issue.get("severity")), 70),
            _int(issue.get("page_index")),
            _str(issue.get("rule_card_id")),
            _str(issue.get("issue_id")),
        ),
    )
    tasks: list[dict[str, Any]] = []
    for index, issue in enumerate(open_issues[:limit], start=1):
        issue_id = _str(issue.get("issue_id"))
        severity = _str(issue.get("severity")) or "info"
        tasks.append(
            _task(
                task_id=f"task-{SEVERITY_PRIORITY.get(severity, 70):03d}-issue-{index:03d}",
                stage="primary_issue_review",
                priority=SEVERITY_PRIORITY.get(severity, 70),
                title=f"复核主 issue: {issue_id}",
                action="inspect_primary_issue_and_update_review_state",
                artifact="issues.json / review_state.json",
                target="#panel-issues",
                reason=_str(issue.get("message")),
                issue_id=issue_id,
                rule_card_id=_str(issue.get("rule_card_id")),
                standard_clause_id=_str(issue.get("standard_clause_id")),
                page_index=_int(issue.get("page_index")),
                status="candidate",
                evidence={
                    "severity": severity,
                    "entity_ids": _str_list(issue.get("entity_ids")),
                    "bbox": issue.get("bbox"),
                },
            )
        )
    if len(open_issues) > limit:
        tasks.append(
            _task(
                task_id="task-069-primary-issues-remaining",
                stage="primary_issue_review",
                priority=69,
                title="继续处理剩余主 issue",
                action="continue_primary_issue_review",
                artifact="issues.json / review_state.json",
                target="#panel-issues",
                reason=f"另有 {len(open_issues) - limit} 条 open primary issue 未展开。",
            )
        )
    return tasks


def _preview_sheet_tasks(
    sheet_issue_review_queue: Mapping[str, Any],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    sheets = [
        sheet
        for sheet in _list_of_mappings(sheet_issue_review_queue.get("sheets"))
        if _int(sheet.get("queued_issue_count")) > 0
    ]
    for sheet in sheets[:limit]:
        page_index = _int(sheet.get("page_index"))
        items = _list_of_mappings(sheet.get("items"))
        preview_ids = [_str(item.get("preview_id")) for item in items[:3]]
        tasks.append(
            _task(
                task_id=f"task-070-preview-sheet-{page_index:03d}",
                stage="per_sheet_preview",
                priority=70,
                title=f"核对第 {page_index + 1} 页 per-sheet preview",
                action="inspect_sheet_preview_without_review_state_write",
                artifact="sheet_issue_review_queue.json",
                target="#panel-sheet-issues",
                reason=(
                    f"该页有 {_int(sheet.get('queued_issue_count'))} 条 queued preview issue; "
                    "preview_id 不能用于 archkg review-state。"
                ),
                page_index=page_index,
                status="preview_only",
                evidence={"preview_id_samples": [item for item in preview_ids if item]},
            )
        )
    if len(sheets) > limit:
        tasks.append(
            _task(
                task_id="task-079-preview-sheets-remaining",
                stage="per_sheet_preview",
                priority=79,
                title="继续核对剩余 per-sheet preview 页",
                action="continue_sheet_preview_review",
                artifact="sheet_issue_review_queue.json",
                target="#panel-sheet-issues",
                reason=f"另有 {len(sheets) - limit} 个 preview sheet 未展开。",
            )
        )
    return tasks


def _handoff_tasks(run_dir: Path) -> list[dict[str, Any]]:
    return [
        _task(
            task_id="task-090-handoff-package",
            stage="handoff",
            priority=90,
            title="生成只读交接包",
            action="write_handoff_package",
            artifact="handoff_manifest.json",
            target="archkg handoff-package <run_dir> -o <package_dir>",
            reason="交接前把 quickstart、task sequence、report、workbench、readiness、issues 和 preview assets 固化为只读包。",
            evidence={"run_dir": str(run_dir)},
        ),
        _task(
            task_id="task-091-handoff-check",
            stage="handoff",
            priority=91,
            title="运行交接包质量门禁",
            action="run_handoff_check",
            artifact="handoff_quality.json / handoff_quality.md",
            target="archkg handoff-check <package_dir>",
            reason="缺关键 artifact 时不要交给下一位 reviewer。",
        ),
    ]


def _task(
    *,
    task_id: str,
    stage: str,
    priority: int,
    title: str,
    action: str,
    artifact: str,
    target: str,
    reason: str,
    issue_id: str = "",
    rule_card_id: str = "",
    standard_clause_id: str = "",
    page_index: int | None = None,
    status: str = "todo",
    evidence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "task_id": task_id,
        "stage": stage,
        "priority": priority,
        "title": title,
        "action": action,
        "artifact": artifact,
        "target": target,
        "reason": reason,
        "status": status,
        "issue_id": issue_id,
        "rule_card_id": rule_card_id,
        "standard_clause_id": standard_clause_id,
        "evidence": dict(evidence or {}),
    }
    if page_index is not None:
        payload["page_index"] = page_index
    return payload


def _summary(tasks: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    return {
        "task_count": len(tasks),
        "blocked_input_task_count": sum(
            1 for task in tasks if _str(task.get("stage")) == "readiness"
        ),
        "primary_issue_task_count": sum(
            1 for task in tasks if _str(task.get("stage")) == "primary_issue_review"
        ),
        "preview_sheet_task_count": sum(
            1 for task in tasks if _str(task.get("stage")) == "per_sheet_preview"
        ),
        "handoff_task_count": sum(
            1 for task in tasks if _str(task.get("stage")) == "handoff"
        ),
    }


def _sequence_status(summary: Mapping[str, int]) -> str:
    if _int(summary.get("blocked_input_task_count")):
        return "needs_input_review"
    if _int(summary.get("primary_issue_task_count")):
        return "needs_issue_review"
    if _int(summary.get("preview_sheet_task_count")):
        return "needs_preview_review"
    return "ready_for_handoff"


def _missing_view(reason: str) -> dict[str, Any]:
    return {
        "available": False,
        "artifact_name": "reviewer_task_sequence.json",
        "schema_version": "missing",
        "status": "missing",
        "summary": {},
        "tasks": [],
        "omitted_task_count": 0,
        "boundary_warning": BOUNDARY_WARNING,
        "mutation_policy": MUTATION_POLICY,
        "unavailable_reason": reason,
    }


def _list_of_mappings(raw: object) -> list[Mapping[str, Any]]:
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes, bytearray)):
        return []
    return [item for item in raw if isinstance(item, Mapping)]


def _str_list(raw: object) -> list[str]:
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes, bytearray)):
        return []
    return [item for item in raw if isinstance(item, str)]


def _mapping(raw: object) -> dict[str, Any]:
    return dict(raw) if isinstance(raw, Mapping) else {}


def _int(raw: object) -> int:
    if isinstance(raw, bool):
        return int(raw)
    if isinstance(raw, int):
        return raw
    if isinstance(raw, float):
        return int(raw)
    return 0


def _str(raw: object) -> str:
    return raw if isinstance(raw, str) else ""


__all__ = [
    "BOUNDARY_WARNING",
    "MUTATION_POLICY",
    "SCHEMA_VERSION",
    "build_reviewer_task_sequence",
    "load_reviewer_task_sequence_view",
    "render_reviewer_task_sequence_markdown",
    "write_reviewer_task_sequence_json",
    "write_reviewer_task_sequence_markdown",
]
