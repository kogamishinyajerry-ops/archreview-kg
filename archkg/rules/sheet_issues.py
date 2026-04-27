"""Per-sheet issue preview built from multi-plan sheet graphs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from archkg.graph.sheet_graphs import SheetGraphsReport
from archkg.rules.engine import SkippedRule, evaluate
from archkg.schemas import Issue, ProjectMeta, RuleCard, StandardClause


class SheetSkippedRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_id: str
    reason: str


class SheetIssueGroup(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_index: int = Field(..., ge=0)
    issue_count: int = Field(..., ge=0)
    skipped_rule_count: int = Field(..., ge=0)
    issues: list[Issue] = Field(default_factory=list)
    skipped_rules: list[SheetSkippedRule] = Field(default_factory=list)


class SheetIssuesReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["sheet_issues.v1"] = "sheet_issues.v1"
    source_pdf: str
    sheet_count: int = Field(..., ge=0)
    issue_count: int = Field(..., ge=0)
    preview_only: bool = True
    review_state_linked: bool = False
    sheets: list[SheetIssueGroup] = Field(default_factory=list)


def build_sheet_issues(
    sheet_graphs: SheetGraphsReport,
    rules: list[RuleCard],
    standards: list[StandardClause],
    *,
    project_meta: ProjectMeta | None = None,
) -> SheetIssuesReport:
    groups: list[SheetIssueGroup] = []
    for entry in sheet_graphs.graphs:
        result = evaluate(entry.graph, rules, standards, project_meta=project_meta)
        groups.append(
            SheetIssueGroup(
                page_index=entry.page_index,
                issue_count=len(result.issues),
                skipped_rule_count=len(result.skipped),
                issues=result.issues,
                skipped_rules=[_skipped_rule(rule) for rule in result.skipped],
            )
        )
    return SheetIssuesReport(
        source_pdf=sheet_graphs.source_pdf,
        sheet_count=len(groups),
        issue_count=sum(group.issue_count for group in groups),
        sheets=groups,
    )


def write_sheet_issues(report: SheetIssuesReport, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return out_path


def _skipped_rule(rule: SkippedRule) -> SheetSkippedRule:
    return SheetSkippedRule(rule_id=rule.rule_id, reason=rule.reason)


__all__ = [
    "SheetIssueGroup",
    "SheetIssuesReport",
    "SheetSkippedRule",
    "build_sheet_issues",
    "write_sheet_issues",
]
