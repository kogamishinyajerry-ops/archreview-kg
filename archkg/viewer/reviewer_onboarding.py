"""Reviewer onboarding artifacts for first-time plan reviewers.

The onboarding payload is guidance-only. It turns the existing workbench
surfaces into a practical first-hour review path without changing issues,
review state, rule output, or benchmark scoring.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "reviewer_onboarding.v1"


def build_reviewer_onboarding(
    *,
    run_dir: Path,
    source_pdf: Path,
    review_workbench: Mapping[str, Any],
    mode: str = "full",
) -> dict[str, Any]:
    summary = _mapping(review_workbench.get("summary"))
    first_hour_steps = _first_hour_steps(summary, mode=mode)
    return {
        "schema_version": SCHEMA_VERSION,
        "audience": "novice_review_engineer",
        "mode": mode,
        "source_pdf": str(source_pdf),
        "run_dir": str(run_dir),
        "artifact_policy": "guidance_only",
        "first_hour_steps": first_hour_steps,
        "artifact_map": _artifact_map(review_workbench),
        "commands": _commands(run_dir, source_pdf, mode=mode),
        "do_not_claim": _do_not_claim(),
        "handoff_checklist": _handoff_checklist(),
        "note": (
            "This onboarding pack helps a reviewer inspect evidence in a stable order. "
            "It does not confirm any issue, mutate issues.json, or certify compliance."
        ),
    }


def write_reviewer_onboarding_json(payload: Mapping[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_reviewer_quickstart_markdown(payload: Mapping[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_reviewer_quickstart_markdown(payload), encoding="utf-8")
    return path


def load_reviewer_onboarding_view(out_dir: Path) -> dict[str, Any]:
    path = out_dir / "reviewer_onboarding.json"
    if not path.exists():
        return {
            "available": False,
            "artifact_name": "reviewer_onboarding.json",
            "first_hour_steps": [],
            "commands": [],
            "do_not_claim": ["reviewer_onboarding.json 暂无数据; 请先查看 review_workbench.json。"],
            "handoff_checklist": [],
            "note": "",
        }
    try:
        raw = json.loads(path.read_text("utf-8"))
    except Exception as exc:
        return {
            "available": False,
            "artifact_name": "reviewer_onboarding.json",
            "first_hour_steps": [],
            "commands": [],
            "do_not_claim": [f"could not read reviewer_onboarding.json: {exc}"],
            "handoff_checklist": [],
            "note": "",
        }
    if not isinstance(raw, Mapping):
        return {
            "available": False,
            "artifact_name": "reviewer_onboarding.json",
            "first_hour_steps": [],
            "commands": [],
            "do_not_claim": ["reviewer_onboarding.json is not an object"],
            "handoff_checklist": [],
            "note": "",
        }
    return {
        "available": True,
        "artifact_name": "reviewer_onboarding.json",
        "first_hour_steps": [
            row for row in _list(raw.get("first_hour_steps")) if isinstance(row, Mapping)
        ],
        "commands": [
            row for row in _list(raw.get("commands")) if isinstance(row, Mapping)
        ],
        "do_not_claim": [
            item for item in _list(raw.get("do_not_claim")) if isinstance(item, str)
        ],
        "handoff_checklist": [
            item for item in _list(raw.get("handoff_checklist")) if isinstance(item, str)
        ],
        "note": _str(raw.get("note")),
    }


def render_reviewer_quickstart_markdown(payload: Mapping[str, Any]) -> str:
    lines = [
        "# 新手审图工程师上手包",
        "",
        _str(payload.get("note")),
        "",
        "## 第一小时流程",
        "",
        "| # | 步骤 | 入口 | 完成标准 |",
        "|---:|---|---|---|",
    ]
    for index, step in enumerate(_list_of_mappings(payload.get("first_hour_steps")), start=1):
        lines.append(
            "| "
            f"{index} | "
            f"{_str(step.get('title'))} | "
            f"`{_str(step.get('artifact'))}` / {_str(step.get('target'))} | "
            f"{_str(step.get('done_when'))} |"
        )
    lines.extend(["", "## 常用命令", "", "| 用途 | 命令 |", "|---|---|"])
    for command in _list_of_mappings(payload.get("commands")):
        lines.append(
            "| "
            f"{_str(command.get('label'))} | "
            f"`{_str(command.get('command'))}` |"
        )
    lines.extend(["", "## 不要这样宣称", ""])
    for item in _list(payload.get("do_not_claim")):
        if isinstance(item, str):
            lines.append(f"- {item}")
    lines.extend(["", "## 交接前检查", ""])
    for item in _list(payload.get("handoff_checklist")):
        if isinstance(item, str):
            lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def _first_hour_steps(summary: Mapping[str, Any], *, mode: str) -> list[dict[str, str]]:
    steps = [
        _step(
            "open_workbench",
            "打开工作台结果页",
            "index.html",
            "#panel-workbench",
            "能看到审图工作台总览、Action Surface 和 artifact 状态。",
        ),
        _step(
            "verify_source_overlay",
            "核对原图、实体叠加和标注图",
            "source_preview.png / entity_overlay.png / annotated.pdf",
            "#panel-layer",
            "确认识别框、房间/门/走廊数量没有明显错位或大面积噪声。",
        ),
        _step(
            "check_component_inventory",
            "核对图纸理解与 component inventory",
            "drawing_understanding.json",
            "#panel-understanding",
            "确认 drawing_type、rooms、doors、corridors、stairs、dimensions 与图面大体一致。",
        ),
        _step(
            "resolve_readiness_blockers",
            "处理规则输入就绪度",
            "rule_input_readiness.json",
            "#panel-readiness",
            "列出 missing_input / low_confidence; 缺输入不等于通过。",
        ),
        _step(
            "confirm_sheet_scope",
            "确认 sheet 分类、路由和候选区域",
            "sheet_classification.json / sheet_region_candidates.json",
            "#panel-sheet-classification",
            "确认本次 graph 读的是正确设计区; 候选裁剪区未经确认不得当作事实。",
        ),
    ]
    if mode != "inspect_only":
        steps.extend(
            [
                _step(
                    "review_candidate_issues",
                    "逐条复核 candidate issues",
                    "issues.json / annotated.pdf",
                    "#panel-issues",
                    "每条 issue 至少核对规则、条文、实体、bbox、测量值和图面位置。",
                ),
                _step(
                    "update_review_state",
                    "写入人工复核状态",
                    "review_state.json",
                    "#panel-issues",
                    "只对主 issues.json 的 issue 使用 archkg review-state 标记 confirmed / rejected / needs_info。",
                ),
            ]
        )
    else:
        steps.append(
            _step(
                "rerun_full_review",
                "识图合理后重跑完整审图",
                "archkg review",
                "#panel-report",
                "仅识图模式没有规则结论; 需要 full review 才能进入 issue 复核。",
            )
        )
    if _int(summary.get("sheet_graph_count")) > 1:
        steps.append(
            _step(
                "inspect_per_sheet_preview",
                "逐页核对 per-sheet issue preview",
                "sheet_issues.json",
                "#panel-sheet-issues",
                "只作为多页提示; 不得直接并入主复核状态。",
            )
        )
    steps.append(
        _step(
            "handoff_run",
            "交接 run 结论",
            "reviewer_quickstart.md / report.md",
            "#panel-report",
            "交接时说明 confirmed / rejected / needs_info、缺失输入、低置信证据和未处理页面。",
        )
    )
    return steps


def _artifact_map(review_workbench: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = [
        row
        for row in _list(review_workbench.get("artifact_statuses"))
        if isinstance(row, Mapping)
    ]
    out = [
        {
            "label": _str(row.get("label")),
            "artifact": _str(row.get("artifact")),
            "status": _str(row.get("status")),
            "detail": _str(row.get("detail")),
        }
        for row in rows
    ]
    out.extend(
        [
            {
                "label": "新手上手包",
                "artifact": "reviewer_onboarding.json",
                "status": "available",
                "detail": "machine-readable first-hour review path",
            },
            {
                "label": "新手 Markdown 指引",
                "artifact": "reviewer_quickstart.md",
                "status": "available",
                "detail": "human-readable first-hour review path",
            },
        ]
    )
    return out


def _commands(run_dir: Path, source_pdf: Path, *, mode: str) -> list[dict[str, str]]:
    commands = [
        {
            "label": "打开本地结果页",
            "command": f"archkg viewer -o {run_dir} --source {source_pdf}",
        },
        {
            "label": "跑发布/演示证据门禁",
            "command": (
                "archkg release-readiness "
                "--manifest samples/understanding_benchmarks/suite_manifest.json "
                f"--run-dir {run_dir}"
            ),
        },
    ]
    if mode == "inspect_only":
        commands.append(
            {
                "label": "重新执行完整审图",
                "command": f"archkg review {source_pdf} -o {run_dir}",
            }
        )
    else:
        commands.append(
            {
                "label": "更新单条复核状态",
                "command": (
                    f"archkg review-state {run_dir} <issue_id> --status "
                    'confirmed --reviewer <name> --note "<note>"'
                ),
            }
        )
    return commands


def _do_not_claim() -> list[str]:
    return [
        "缺输入不等于通过; missing_input / low_confidence 必须列为待补证据。",
        "issues.json 是规则引擎 candidate 输出; 未经人工复核不得宣称 confirmed defect。",
        "sheet_issues.json 是 per-sheet preview, 不会自动进入主 issues.json 或 review_state.json。",
        "evidence_ready 只适用于已 benchmark 的图纸类别, 不是任意复杂真实图纸自动审批证明。",
        "OCR、VLM 或 text_hint 证据只能辅助复核, 不能替代条文和实体证据链。",
    ]


def _handoff_checklist() -> list[str]:
    return [
        "已打开 source / overlay / annotated 图层并记录明显识别偏差。",
        "已列出 rule_input_readiness 中的 missing_input / low_confidence。",
        "已逐条处理高风险 candidate issue, 或标记 needs_info。",
        "已说明哪些 sheet/page 只作为 preview, 还没有进入主生命周期。",
        "已附上 run_dir、commit、验证命令和未解决问题。",
    ]


def _step(
    step_id: str,
    title: str,
    artifact: str,
    target: str,
    done_when: str,
) -> dict[str, str]:
    return {
        "step_id": step_id,
        "title": title,
        "artifact": artifact,
        "target": target,
        "done_when": done_when,
    }


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
    "build_reviewer_onboarding",
    "load_reviewer_onboarding_view",
    "render_reviewer_quickstart_markdown",
    "write_reviewer_onboarding_json",
    "write_reviewer_quickstart_markdown",
]
