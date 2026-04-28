"""Render the human-readable Markdown review report."""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from archkg.labels import label_building_type
from archkg.review_state import build_review_state, review_state_by_issue_id
from archkg.rules.engine import SkippedRule
from archkg.schemas import Issue, ProjectMeta, StandardClause
from archkg.schemas.review_state import IssueReviewState


def _env() -> Environment:
    template_dir = str(files("archkg.annotate.templates"))
    return Environment(
        loader=FileSystemLoader(template_dir),
        autoescape=select_autoescape(default=False, default_for_string=False),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render(
    *,
    source_pdf: Path,
    entity_graph_path: Path,
    annotated_pdf: Path,
    issues: list[Issue],
    clauses: list[StandardClause],
    out_md: Path,
    project_meta: ProjectMeta | None = None,
    skipped: list[SkippedRule] | None = None,
    rule_readiness: dict[str, Any] | None = None,
    sheet_classification: dict[str, Any] | None = None,
    sheet_routing: dict[str, Any] | None = None,
    sheet_graphs: dict[str, Any] | None = None,
    sheet_issues: dict[str, Any] | None = None,
    sheet_issue_review_queue: dict[str, Any] | None = None,
    review_state: IssueReviewState | dict[str, Any] | None = None,
    review_workbench: dict[str, Any] | None = None,
    reviewer_onboarding: dict[str, Any] | None = None,
    reviewer_task_sequence: dict[str, Any] | None = None,
) -> Path:
    used_ids = {i.standard_clause_id for i in issues}
    clauses_used = [c for c in clauses if c.id in used_ids]
    template = _env().get_template("report.md.j2")

    meta_payload: dict[str, object] | None = None
    if project_meta is not None:
        meta_payload = project_meta.model_dump()
        meta_payload["building_type_label"] = label_building_type(project_meta.building_type)

    if isinstance(review_state, dict):
        review_state_model = IssueReviewState.model_validate(review_state)
    elif review_state is None:
        review_state_model = build_review_state(issues, run_id=None)
    else:
        review_state_model = review_state

    review_state_by_id = review_state_by_issue_id(review_state_model)
    issue_payloads: list[dict[str, Any]] = []
    for issue in issues:
        payload = issue.model_dump()
        item = review_state_by_id.get(issue.issue_id)
        if item is None:
            item = build_review_state([issue], run_id=None).items[0]
        payload["review_state"] = item.model_dump(mode="json")
        issue_payloads.append(payload)

    rendered = template.render(
        source_pdf=str(source_pdf),
        entity_graph_path=str(entity_graph_path),
        annotated_pdf=str(annotated_pdf),
        issues=issue_payloads,
        clauses_used=[c.model_dump() for c in clauses_used],
        project_meta=meta_payload,
        skipped=[{"rule_id": s.rule_id, "reason": s.reason} for s in (skipped or [])],
        rule_readiness=rule_readiness,
        sheet_classification=sheet_classification,
        sheet_routing=sheet_routing,
        sheet_graphs=sheet_graphs,
        sheet_issues=sheet_issues,
        sheet_issue_review_queue=sheet_issue_review_queue,
        review_state=review_state_model.model_dump(mode="json"),
        review_workbench=review_workbench,
        reviewer_onboarding=reviewer_onboarding,
        reviewer_task_sequence=reviewer_task_sequence,
    )
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(rendered, encoding="utf-8")
    return out_md
