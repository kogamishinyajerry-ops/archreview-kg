"""Run-level rule input readiness artifact.

This module does not evaluate compliance and does not mutate the rule-engine
result. It explains whether each loaded rule card had enough evidence in this
specific run to be evaluated as an automated check, a manual reminder, or a
blocked rule.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from archkg.graph.builder import EntityGraph
from archkg.rules.engine import SkippedRule
from archkg.schemas import (
    Corridor,
    Door,
    ProjectMeta,
    Room,
    RuleCard,
    RuleInputReadiness,
    RuleInputReadinessReport,
    RuleInputReadinessStatus,
    Stair,
    StandardClause,
)

LOW_CONFIDENCE_THRESHOLD = 0.5

_STATUS_VALUES: tuple[RuleInputReadinessStatus, ...] = (
    "ready",
    "missing_input",
    "low_confidence",
    "manual_only",
    "not_applicable",
    "unsupported_entity",
)

_InputEntity = Room | Door | Corridor | Stair


def build_rule_input_readiness(
    graph: EntityGraph,
    rules: Sequence[RuleCard],
    standards: Sequence[StandardClause],
    *,
    project_meta: ProjectMeta | None = None,
    skipped: Sequence[SkippedRule] | None = None,
    ocr_diagnostics: object | None = None,
    schedule_apply: object | None = None,
    stair_schedule_apply: object | None = None,
) -> RuleInputReadinessReport:
    """Build the per-run readiness report for every loaded rule card."""

    standards_by_id = {standard.id: standard for standard in standards}
    skipped_by_rule = {item.rule_id: item.reason for item in skipped or ()}
    rows: list[RuleInputReadiness] = []

    for rule in rules:
        missing_clause_ids = [
            clause_id
            for clause_id in rule.source_clause_ids
            if clause_id not in standards_by_id
        ]
        if missing_clause_ids:
            rows.append(
                _row(
                    rule,
                    status="missing_input",
                    source="knowledge_base",
                    reason=(
                        "rule references source clauses that were not loaded: "
                        f"{', '.join(missing_clause_ids)}"
                    ),
                    missing_inputs=rule.inputs,
                )
            )
            continue

        skipped_reason = skipped_by_rule.get(rule.id)
        if skipped_reason is not None:
            rows.append(_skipped_row(rule, skipped_reason))
            continue

        if rule.applies_to == "Project":
            rows.append(_project_row(rule, project_meta))
            continue

        rows.append(
            _entity_row(
                rule,
                graph,
                schedule_apply=schedule_apply,
                stair_schedule_apply=stair_schedule_apply,
                ocr_diagnostics=ocr_diagnostics,
            )
        )

    summary = _empty_summary()
    for row in rows:
        summary[row.status] += 1
    return RuleInputReadinessReport(summary=summary, rules=rows)


def write_rule_input_readiness(
    report: RuleInputReadinessReport,
    out_path: Path,
) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return out_path


def _empty_summary() -> dict[RuleInputReadinessStatus, int]:
    return {status: 0 for status in _STATUS_VALUES}


def _effective_severity(rule: RuleCard) -> str:
    if rule.severity is not None:
        return rule.severity
    return "info" if rule.applies_to == "Project" else "error"


def _row(
    rule: RuleCard,
    *,
    status: RuleInputReadinessStatus,
    source: str,
    reason: str,
    available_inputs: Sequence[str] = (),
    missing_inputs: Sequence[str] = (),
    entity_count: int | None = None,
    candidate_entity_ids: Sequence[str] = (),
    low_confidence_entity_ids: Sequence[str] = (),
) -> RuleInputReadiness:
    return RuleInputReadiness(
        rule_id=rule.id,
        source_clause_ids=list(rule.source_clause_ids),
        applies_to=rule.applies_to,
        severity=_effective_severity(rule),
        status=status,
        required_inputs=list(rule.inputs),
        available_inputs=list(available_inputs),
        missing_inputs=list(missing_inputs),
        entity_count=entity_count,
        candidate_entity_ids=list(candidate_entity_ids),
        low_confidence_entity_ids=list(low_confidence_entity_ids),
        source=source,
        reason=reason,
    )


def _skipped_row(rule: RuleCard, reason: str) -> RuleInputReadiness:
    if "needs --project-meta" in reason:
        return _row(
            rule,
            status="missing_input",
            source="project_meta",
            reason=reason,
            missing_inputs=rule.inputs,
        )
    return _row(
        rule,
        status="not_applicable",
        source="applicability",
        reason=reason,
    )


def _project_row(
    rule: RuleCard,
    project_meta: ProjectMeta | None,
) -> RuleInputReadiness:
    if project_meta is None:
        return _row(
            rule,
            status="missing_input",
            source="project_meta",
            reason="project_meta is absent; provide --project-meta to evaluate this rule",
            missing_inputs=rule.inputs,
        )

    payload = project_meta.model_dump()
    available_inputs = [
        input_name
        for input_name in rule.inputs
        if payload.get(input_name) is not None
    ]
    missing_inputs = [
        input_name
        for input_name in rule.inputs
        if payload.get(input_name) is None
    ]
    if missing_inputs:
        return _row(
            rule,
            status="missing_input",
            source="project_meta",
            reason=(
                "project_meta is present, but required fields are unset: "
                f"{', '.join(missing_inputs)}"
            ),
            available_inputs=available_inputs,
            missing_inputs=missing_inputs,
        )

    if _effective_severity(rule) == "info":
        return _row(
            rule,
            status="manual_only",
            source="project_meta",
            reason=(
                "all project inputs are present, but this info-level rule "
                "surfaces a manual-check reminder rather than a hard violation"
            ),
            available_inputs=available_inputs,
        )

    return _row(
        rule,
        status="ready",
        source="project_meta",
        reason="all required project inputs are present",
        available_inputs=available_inputs,
    )


def _entity_row(
    rule: RuleCard,
    graph: EntityGraph,
    *,
    schedule_apply: object | None,
    stair_schedule_apply: object | None,
    ocr_diagnostics: object | None,
) -> RuleInputReadiness:
    entities = _entity_iterable(graph, rule.applies_to)
    if not entities:
        return _row(
            rule,
            status="unsupported_entity",
            source="entity_graph",
            reason=f"this run contains no {rule.applies_to} entities",
            missing_inputs=rule.inputs,
            entity_count=0,
        )

    available_inputs = [
        input_name
        for input_name in rule.inputs
        if any(_has_input(entity, input_name) for entity in entities)
    ]
    missing_inputs = [
        input_name
        for input_name in rule.inputs
        if input_name not in set(available_inputs)
    ]
    candidate_entities = [
        entity
        for entity in entities
        if all(_has_input(entity, input_name) for input_name in rule.inputs)
    ]
    candidate_entity_ids = [entity.id for entity in candidate_entities]

    if missing_inputs or not candidate_entities:
        effective_missing = missing_inputs or list(rule.inputs)
        return _row(
            rule,
            status="missing_input",
            source=_entity_source(
                rule.applies_to,
                schedule_apply=schedule_apply,
                stair_schedule_apply=stair_schedule_apply,
                ocr_diagnostics=ocr_diagnostics,
            ),
            reason=(
                "required inputs are not available on any single "
                f"{rule.applies_to} entity"
            ),
            available_inputs=available_inputs,
            missing_inputs=effective_missing,
            entity_count=len(entities),
            candidate_entity_ids=candidate_entity_ids,
        )

    low_confidence_entity_ids = [
        entity.id
        for entity in candidate_entities
        if entity.uncertain or entity.confidence < LOW_CONFIDENCE_THRESHOLD
    ]
    if low_confidence_entity_ids:
        return _row(
            rule,
            status="low_confidence",
            source=_entity_source(
                rule.applies_to,
                schedule_apply=schedule_apply,
                stair_schedule_apply=stair_schedule_apply,
                ocr_diagnostics=ocr_diagnostics,
            ),
            reason=(
                "required inputs are present, but at least one input-complete "
                "entity is uncertain or low-confidence"
            ),
            available_inputs=available_inputs,
            entity_count=len(entities),
            candidate_entity_ids=candidate_entity_ids,
            low_confidence_entity_ids=low_confidence_entity_ids,
        )

    if _effective_severity(rule) == "info":
        return _row(
            rule,
            status="manual_only",
            source=_entity_source(
                rule.applies_to,
                schedule_apply=schedule_apply,
                stair_schedule_apply=stair_schedule_apply,
                ocr_diagnostics=ocr_diagnostics,
            ),
            reason=(
                "all inputs are present, but this info-level rule surfaces "
                "a manual-check reminder rather than a hard violation"
            ),
            available_inputs=available_inputs,
            entity_count=len(entities),
            candidate_entity_ids=candidate_entity_ids,
        )

    return _row(
        rule,
        status="ready",
        source=_entity_source(
            rule.applies_to,
            schedule_apply=schedule_apply,
            stair_schedule_apply=stair_schedule_apply,
            ocr_diagnostics=ocr_diagnostics,
        ),
        reason="all required entity inputs are present",
        available_inputs=available_inputs,
        entity_count=len(entities),
        candidate_entity_ids=candidate_entity_ids,
    )


def _entity_iterable(graph: EntityGraph, applies_to: str) -> list[_InputEntity]:
    if applies_to == "Room":
        return list(graph.rooms)
    if applies_to == "Door":
        return list(graph.doors)
    if applies_to == "Corridor":
        return list(graph.corridors)
    if applies_to == "Stair":
        return list(graph.stairs)
    return []


def _has_input(entity: _InputEntity, input_name: str) -> bool:
    return _input_value(entity, input_name) is not None


def _input_value(entity: _InputEntity, input_name: str) -> Any:
    if hasattr(entity, input_name):
        return getattr(entity, input_name)
    return entity.properties.get(input_name)


def _entity_source(
    applies_to: str,
    *,
    schedule_apply: object | None,
    stair_schedule_apply: object | None,
    ocr_diagnostics: object | None,
) -> str:
    sources = ["entity_graph"]
    if applies_to == "Room" and schedule_apply is not None:
        sources.append("room_schedule")
    if applies_to == "Stair" and stair_schedule_apply is not None:
        sources.append("stair_schedule")
    if ocr_diagnostics is not None:
        sources.append("ocr_diagnostics")
    return "+".join(sources)
