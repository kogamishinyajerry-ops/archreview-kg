from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "reviewer_task_checklist.v1"
MUTATION_POLICY = "checklist_seed_only_no_issue_state_mutation"
BOUNDARY_WARNING = (
    "Reviewer task checklist is a fillable human work aid derived from "
    "reviewer_task_sequence.json; it does not confirm issues, mutate "
    "issues.json or review_state.json, promote preview issues, or certify "
    "drawing compliance."
)

ALLOWED_REVIEWER_STATUSES = (
    "todo",
    "done",
    "blocked",
    "needs_info",
    "skipped_preview",
)


def build_reviewer_task_checklist(
    *,
    run_dir: Path,
    source_pdf: Path,
    reviewer_task_sequence: Mapping[str, Any],
) -> dict[str, Any]:
    """Build a static, fillable checklist seed from the ordered task sequence."""

    tasks = _list_of_mappings(reviewer_task_sequence.get("tasks"))
    items = [_checklist_item(task) for task in tasks]
    summary = _summary(items)
    return {
        "schema_version": SCHEMA_VERSION,
        "audience": "novice_review_engineer",
        "source_pdf": str(source_pdf),
        "run_dir": str(run_dir),
        "source_task_sequence_schema": _str(
            reviewer_task_sequence.get("schema_version")
        ),
        "source_task_sequence_status": _str(reviewer_task_sequence.get("status")),
        "mutation_policy": MUTATION_POLICY,
        "status": _checklist_status(summary),
        "allowed_reviewer_statuses": list(ALLOWED_REVIEWER_STATUSES),
        "reviewer_fields": [
            "reviewer",
            "reviewer_status",
            "completed_at",
            "reviewer_note",
            "evidence_checked",
        ],
        "summary": summary,
        "items": items,
        "do_not_use_as": [
            "drawing_compliance_certificate",
            "issue_confirmation",
            "preview_issue_promotion",
        ],
        "boundary_warning": BOUNDARY_WARNING,
        "source_artifacts": ["reviewer_task_sequence.json"],
    }


def write_reviewer_task_checklist_json(
    payload: Mapping[str, Any],
    path: Path,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_reviewer_task_checklist_markdown(
    payload: Mapping[str, Any],
    path: Path,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_reviewer_task_checklist_markdown(payload), encoding="utf-8")
    return path


def load_reviewer_task_checklist_view(
    out_dir: Path,
    *,
    limit: int = 12,
) -> dict[str, Any]:
    path = out_dir / "reviewer_task_checklist.json"
    if not path.exists():
        return _missing_view("reviewer_task_checklist.json missing")
    try:
        raw = json.loads(path.read_text("utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return _missing_view(f"could not read reviewer_task_checklist.json: {exc}")
    if not isinstance(raw, Mapping):
        return _missing_view("reviewer_task_checklist.json is not an object")
    items = _list_of_mappings(raw.get("items"))
    return {
        "available": True,
        "artifact_name": "reviewer_task_checklist.json",
        "schema_version": _str(raw.get("schema_version")) or "unknown",
        "status": _str(raw.get("status")),
        "summary": _mapping(raw.get("summary")),
        "allowed_reviewer_statuses": _str_list(raw.get("allowed_reviewer_statuses")),
        "items": [dict(item) for item in items[: max(0, limit)]],
        "omitted_item_count": max(0, len(items) - max(0, limit)),
        "boundary_warning": _str(raw.get("boundary_warning")) or BOUNDARY_WARNING,
        "mutation_policy": _str(raw.get("mutation_policy")) or MUTATION_POLICY,
        "unavailable_reason": "",
    }


def render_reviewer_task_checklist_markdown(payload: Mapping[str, Any]) -> str:
    summary = _mapping(payload.get("summary"))
    allowed_statuses = ", ".join(_str_list(payload.get("allowed_reviewer_statuses")))
    lines = [
        "# Reviewer Task Checklist",
        "",
        f"Status: `{_str(payload.get('status'))}`",
        f"Source sequence: `{_str(payload.get('source_task_sequence_status'))}`",
        f"Mutation policy: `{_str(payload.get('mutation_policy'))}`",
        "",
        _str(payload.get("boundary_warning")),
        "",
        "## How To Use",
        "",
        "- Work from top to bottom; each row is derived from reviewer_task_sequence.json.",
        f"- Allowed reviewer_status values: `{allowed_statuses}`.",
        "- Fill reviewer_note with the evidence checked and unresolved risk.",
        "- Use archkg review-state only for primary issue ids, never for preview_id.",
        "",
        "## Summary",
        "",
        f"- Checklist items: `{_int(summary.get('item_count'))}`",
        f"- Readiness items: `{_int(summary.get('readiness_item_count'))}`",
        f"- Primary issue items: `{_int(summary.get('primary_issue_item_count'))}`",
        f"- Preview items: `{_int(summary.get('preview_item_count'))}`",
        f"- Handoff items: `{_int(summary.get('handoff_item_count'))}`",
        "",
        "## Fillable Checklist",
        "",
        "| Done | # | Stage | Task | Reviewer Status | Required Evidence | Completion Prompt | Evidence Checked | Reviewer Note |",
        "|---|---:|---|---|---|---|---|---|---|",
    ]
    for item in _list_of_mappings(payload.get("items")):
        evidence = "<br>".join(_str_list(item.get("required_evidence"))) or "-"
        checked_evidence = "<br>".join(_str_list(item.get("evidence_checked"))) or "-"
        reviewer_status = _str(item.get("reviewer_status")) or "todo"
        checked = "[x]" if reviewer_status in {"done", "skipped_preview"} else "[ ]"
        reviewer_note = _str(item.get("reviewer_note")) or "-"
        lines.append(
            f"| {checked} | "
            f"{_int(item.get('ordinal'))} | "
            f"`{_str(item.get('stage'))}` | "
            f"{_str(item.get('title'))} | "
            f"`{reviewer_status}` | "
            f"{evidence} | "
            f"{_str(item.get('completion_prompt'))} | "
            f"{checked_evidence} | "
            f"{reviewer_note} |"
        )
    lines.append("")
    return "\n".join(lines)


def _checklist_item(task: Mapping[str, Any]) -> dict[str, Any]:
    stage = _str(task.get("stage"))
    task_id = _str(task.get("task_id"))
    item: dict[str, Any] = {
        "check_id": f"check-{_int(task.get('ordinal')):03d}-{task_id or stage}",
        "ordinal": _int(task.get("ordinal")),
        "task_id": task_id,
        "stage": stage,
        "priority": _int(task.get("priority")),
        "title": _str(task.get("title")),
        "action": _str(task.get("action")),
        "artifact": _str(task.get("artifact")),
        "target": _str(task.get("target")),
        "reason": _str(task.get("reason")),
        "issue_id": _str(task.get("issue_id")),
        "rule_card_id": _str(task.get("rule_card_id")),
        "standard_clause_id": _str(task.get("standard_clause_id")),
        "task_status": _str(task.get("status")) or "todo",
        "reviewer_status": "todo",
        "reviewer": "",
        "completed_at": "",
        "reviewer_note": "",
        "evidence_checked": [],
        "required_evidence": _required_evidence(stage),
        "completion_prompt": _completion_prompt(stage),
        "handoff_risk_if_open": _handoff_risk(stage),
        "mutation_warning": _mutation_warning(stage),
    }
    if "page_index" in task:
        item["page_index"] = _int(task.get("page_index"))
    return item


def _required_evidence(stage: str) -> list[str]:
    if stage == "intake":
        return ["index.html boundary badge", "report.md summary"]
    if stage == "recognition":
        return ["run_meta.json quality_flags", "drawing_understanding.json"]
    if stage == "sheet_scope":
        return ["sheet_classification.json", "sheet_graphs.json"]
    if stage == "readiness":
        return ["rule_input_readiness.json row", "source metadata or drawing evidence"]
    if stage == "primary_issue_review":
        return ["issues.json primary issue row", "review_state.json row", "drawing preview"]
    if stage == "per_sheet_preview":
        return ["sheet_issue_review_queue.json sheet row", "source or overlay preview page"]
    if stage == "full_review_gate":
        return ["inspect_only run_meta.json", "rerun full review command output"]
    if stage == "handoff":
        return ["handoff_manifest.json", "handoff_quality.json or handoff_quality.md"]
    return ["referenced artifact"]


def _completion_prompt(stage: str) -> str:
    if stage == "readiness":
        return "记录缺失输入是否已补齐; 未补齐时保留为交接风险。"
    if stage == "primary_issue_review":
        return "核对图面和条文后, 用 primary issue_id 更新 review_state。"
    if stage == "per_sheet_preview":
        return "只记录 preview 观察结论; 不要把 preview_id 写入 review_state。"
    if stage == "handoff":
        return "确认交接包可打开且 handoff-check 没有 blocker。"
    if stage == "full_review_gate":
        return "识图合理后重跑完整审图; 仅识图 run 不能签出合规结论。"
    return "记录已查看的 artifact、判断依据和剩余风险。"


def _handoff_risk(stage: str) -> str:
    if stage == "readiness":
        return "规则输入不完整, 相关规则结论不能作为完整审图结论。"
    if stage == "primary_issue_review":
        return "候选 issue 未经人工确认, 不能直接作为最终违规结论。"
    if stage == "per_sheet_preview":
        return "sheet preview 只作提示, 不能替代主 issue 复核。"
    if stage == "handoff":
        return "交接包未验收会让下一位 reviewer 缺关键证据。"
    return "该项未完成时, 需要在 reviewer note 中说明影响。"


def _mutation_warning(stage: str) -> str:
    if stage == "primary_issue_review":
        return "Only archkg review-state may update primary issue review_state."
    if stage == "per_sheet_preview":
        return "Preview ids must not be passed to archkg review-state."
    return "Checklist notes do not mutate source run artifacts."


def _summary(items: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    return {
        "item_count": len(items),
        "readiness_item_count": _count_stage(items, "readiness"),
        "primary_issue_item_count": _count_stage(items, "primary_issue_review"),
        "preview_item_count": _count_stage(items, "per_sheet_preview"),
        "handoff_item_count": _count_stage(items, "handoff"),
    }


def _checklist_status(summary: Mapping[str, int]) -> str:
    if _int(summary.get("readiness_item_count")):
        return "needs_input_review"
    if _int(summary.get("primary_issue_item_count")):
        return "needs_issue_review"
    if _int(summary.get("preview_item_count")):
        return "needs_preview_review"
    if _int(summary.get("item_count")):
        return "ready_for_handoff_review"
    return "no_tasks_available"


def _count_stage(items: Sequence[Mapping[str, Any]], stage: str) -> int:
    return sum(1 for item in items if _str(item.get("stage")) == stage)


def _missing_view(reason: str) -> dict[str, Any]:
    return {
        "available": False,
        "artifact_name": "reviewer_task_checklist.json",
        "schema_version": "missing",
        "status": "missing",
        "summary": {},
        "allowed_reviewer_statuses": list(ALLOWED_REVIEWER_STATUSES),
        "items": [],
        "omitted_item_count": 0,
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
    "ALLOWED_REVIEWER_STATUSES",
    "BOUNDARY_WARNING",
    "MUTATION_POLICY",
    "SCHEMA_VERSION",
    "build_reviewer_task_checklist",
    "load_reviewer_task_checklist_view",
    "render_reviewer_task_checklist_markdown",
    "write_reviewer_task_checklist_json",
    "write_reviewer_task_checklist_markdown",
]
