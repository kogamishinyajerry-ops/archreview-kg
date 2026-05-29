"""Per-sheet issue preview built from multi-plan sheet graphs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from archkg.graph.builder import EntityGraph
from archkg.graph.sheet_graphs import SheetGraphsReport
from archkg.rules.engine import EvalResult, SkippedRule, evaluate
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


def merge_sheet_issues(
    sheet_graphs: SheetGraphsReport,
    project_graph: EntityGraph,
    rules: list[RuleCard],
    standards: list[StandardClause],
    *,
    project_meta: ProjectMeta | None = None,
) -> EvalResult:
    """Build the CANONICAL multi-page issue list (round-7 R6/R7-BUG-001/002/003).

    The legacy main path evaluated rules on ``build_graph(primitives)`` which
    only ever reads ``primitives.pages[0]`` (builder.py), so every issue got
    ``page_index=0`` and any defect on a non-primary plan page was never
    extracted at all. Per-page extraction already runs today via
    :func:`build_sheet_graphs` (each :class:`SheetGraphEntry` carries the true
    per-entity ``page_index``) but its output was thrown away as preview-only.
    This merge consumes those per-page graphs for the canonical issue list.

    Design notes / invariants:
    - **Primary page is unchanged.** The page that ``project_graph`` was built
      from (normally page 0) is evaluated against ``project_graph`` itself with
      the FULL rule set, exactly as the legacy ``evaluate`` did. This preserves
      room/stair *schedule* application (schedules are applied to
      ``project_graph`` after ``build_graph`` but are not threaded into the
      per-page sheet graphs) and keeps single-page output behaviourally
      identical (only fresh ``issue_id`` uuids differ).
    - **Project rules run exactly once.** 18 of 32 rule cards are
      ``applies_to == "Project"`` and are page-agnostic (``page_index=0``).
      Running them per plan page would duplicate every project issue, so they
      are evaluated only in the primary pass. Entity rules on extra pages get
      ``project_graph``'s schedule-free sheet graph — schedule-unlocked entity
      rules therefore only fire on the primary page; this is a documented,
      strictly-additive limitation (those pages previously produced ZERO
      issues), not a regression.
    """
    # Project rules are EXCLUDED from the per-page loop (they run once in the
    # primary pass below via the full ``rules`` list); this exclusion is what
    # prevents the 18 project issues from duplicating across plan pages.
    entity_rules = [r for r in rules if r.applies_to != "Project"]

    issues: list[Issue] = []
    skipped_by_id: dict[str, SkippedRule] = {}

    def _absorb(result: EvalResult) -> None:
        issues.extend(result.issues)
        for sk in result.skipped:
            skipped_by_id.setdefault(sk.rule_id, sk)

    primary_index = project_graph.page_index

    # Extra plan pages (page_index != primary): entity rules only, evaluated
    # against each page's own sheet graph so issues carry the true page_index.
    for entry in sheet_graphs.graphs:
        if entry.page_index == primary_index:
            continue  # primary handled below against the post-schedule graph
        _absorb(evaluate(entry.graph, entity_rules, standards, project_meta=project_meta))

    # Primary page: full rule set against the post-schedule graph == legacy path.
    _absorb(evaluate(project_graph, rules, standards, project_meta=project_meta))

    return EvalResult(issues=issues, skipped=list(skipped_by_id.values()))


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
    "merge_sheet_issues",
    "write_sheet_issues",
]
