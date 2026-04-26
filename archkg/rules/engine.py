"""Rule engine — pure entity_graph consumer (NEVER reads PDF or images).

The engine compiles each rule card's `logic_expression` to a restricted AST
evaluator that can only:
  - read names from the rule's declared `inputs` list
  - apply arithmetic + comparison + boolean operators
  - reference numeric / string / bool literals

No attribute access, no function calls, no subscripting, no comprehensions.
This keeps rule cards declarative and prevents arbitrary code execution.
"""

from __future__ import annotations

import ast
import uuid
from dataclasses import dataclass, field
from typing import Any

from archkg.graph.builder import EntityGraph
from archkg.rules.applicability import is_rule_applicable, skip_reason
from archkg.schemas import (
    Corridor,
    Door,
    Issue,
    IssueEvidence,
    ProjectMeta,
    Room,
    RuleCard,
    Stair,
    StandardClause,
)


@dataclass(frozen=True)
class SkippedRule:
    rule_id: str
    reason: str


@dataclass
class EvalResult:
    """Output of `evaluate()`: violating issues plus the rules that were
    skipped because the project context made them inapplicable."""

    issues: list[Issue] = field(default_factory=list)
    skipped: list[SkippedRule] = field(default_factory=list)


class RuleCompileError(ValueError):
    pass


_ALLOWED_NODES: tuple[type[ast.AST], ...] = (
    ast.Expression,
    ast.BoolOp,
    ast.BinOp,
    ast.UnaryOp,
    ast.Compare,
    ast.Name,
    ast.Constant,
    ast.Load,
)
_ALLOWED_OPS: tuple[type[ast.AST], ...] = (
    ast.And,
    ast.Or,
    ast.Not,
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Mod,
    ast.USub,
    ast.UAdd,
    # Phase 11-B: project-level rules need `is None` / `is not None` checks
    # so they can no-op gracefully when an optional ProjectMeta field is unset.
    ast.Is,
    ast.IsNot,
)


def _validate_ast(tree: ast.AST, allowed_names: set[str]) -> None:
    for node in ast.walk(tree):
        if isinstance(node, _ALLOWED_NODES):
            if isinstance(node, ast.Name) and node.id not in allowed_names:
                raise RuleCompileError(
                    f"name '{node.id}' is not in declared inputs {sorted(allowed_names)}"
                )
            continue
        if isinstance(node, _ALLOWED_OPS):
            continue
        raise RuleCompileError(f"AST node '{type(node).__name__}' is not allowed")


def compile_expression(expression: str, inputs: list[str]) -> ast.Expression:
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise RuleCompileError(f"syntax error: {exc}") from exc
    _validate_ast(tree, set(inputs))
    return tree


def evaluate_expression(tree: ast.Expression, env: dict[str, Any]) -> bool:
    """Eval the whitelisted AST against env. Any operand error (None compare,
    division by zero, value coercion) conservatively flags the rule as failed
    — "rather flag than silently miss" — instead of crashing the review run."""
    code = compile(tree, filename="<rule>", mode="eval")
    try:
        return bool(eval(code, {"__builtins__": {}}, env))
    except (TypeError, ValueError, ArithmeticError):
        return False


def _entity_env(entity: Room | Door | Corridor | Stair, inputs: list[str]) -> dict[str, Any]:
    env: dict[str, Any] = {}
    for key in inputs:
        if hasattr(entity, key):
            env[key] = getattr(entity, key)
        else:
            env[key] = entity.properties.get(key)
    return env


def _format_message(template: str, env: dict[str, Any]) -> str:
    safe_env = {k: ("?" if v is None else v) for k, v in env.items()}
    try:
        return template.format(**safe_env)
    except (KeyError, ValueError):
        return template


def _entity_iterable(graph: EntityGraph, applies_to: str) -> list[Room | Door | Corridor | Stair]:
    if applies_to == "Room":
        return list(graph.rooms)
    if applies_to == "Door":
        return list(graph.doors)
    if applies_to == "Corridor":
        return list(graph.corridors)
    if applies_to == "Stair":
        return list(graph.stairs)
    return []


def _project_env(meta: ProjectMeta, inputs: list[str]) -> dict[str, Any]:
    """Build the eval env for Project-level rules from a ProjectMeta dump.

    inputs lists which meta fields the rule reads (e.g. floors, height_m).
    Missing fields surface as None — rules use `is None` / `is not None`
    checks to no-op gracefully when an optional field is unset.
    """
    payload = meta.model_dump()
    return {key: payload.get(key) for key in inputs}


def _new_issue_id() -> str:
    return f"ISS-{uuid.uuid4().hex[:8]}"


def evaluate(
    graph: EntityGraph,
    rules: list[RuleCard],
    standards: list[StandardClause],
    project_meta: ProjectMeta | None = None,
) -> EvalResult:
    """Run all *applicable* rules over the graph.

    With `project_meta=None` (legacy mode) every rule fires — preserves
    pre-Phase-9 behaviour. With a project meta, rules whose source clauses
    don't apply to the project context are recorded in `result.skipped`
    rather than evaluated.
    """
    standards_by_id = {s.id: s for s in standards}
    result = EvalResult()

    for rule in rules:
        if not is_rule_applicable(rule, project_meta, standards_by_id):
            assert project_meta is not None  # is_rule_applicable returns True for None meta
            result.skipped.append(
                SkippedRule(rule_id=rule.id, reason=skip_reason(rule, project_meta, standards_by_id))
            )
            continue

        # Project-level rules need a ProjectMeta to evaluate; without one we skip.
        if rule.applies_to == "Project" and project_meta is None:
            result.skipped.append(
                SkippedRule(rule_id=rule.id, reason="needs --project-meta to evaluate")
            )
            continue

        try:
            tree = compile_expression(rule.logic_expression, rule.inputs)
        except RuleCompileError as exc:
            raise RuleCompileError(f"rule {rule.id}: {exc}") from exc

        clause = standards_by_id.get(rule.source_clause_ids[0])
        clause_id = clause.id if clause else rule.source_clause_ids[0]
        # Phase 15 Codex P1: rule-level threshold_value override beats clause's
        # primary threshold when the rule's metric differs from the source
        # clause's first-listed threshold (e.g. RC-STAIR-HANDRAIL-0.90 sourcing
        # GB50096-6.3.2 whose primary threshold is 0.26 m for tread width).
        threshold_for_evidence = (
            rule.threshold_value if rule.threshold_value is not None
            else (clause.threshold_value if clause else None)
        )

        if rule.applies_to == "Project":
            assert project_meta is not None
            env = _project_env(project_meta, rule.inputs)
            passed = evaluate_expression(tree, env)
            if passed:
                continue
            measured = None if rule.suppress_measured else _pick_measured(env, rule.inputs)
            evidence = IssueEvidence(
                snippet=_format_message(rule.output_template, env),
                page_index=0,
                measured_value=measured,
                threshold_value=threshold_for_evidence,
                unit=clause.unit if clause else None,
            )
            result.issues.append(
                Issue(
                    issue_id=_new_issue_id(),
                    rule_card_id=rule.id,
                    standard_clause_id=clause_id,
                    entity_ids=[f"project:{project_meta.project_id}"],
                    bbox=None,
                    page_index=0,
                    severity=rule.severity or "info",
                    message=_format_message(rule.output_template, env),
                    evidence=evidence,
                )
            )
            continue

        for entity in _entity_iterable(graph, rule.applies_to):
            env = _entity_env(entity, rule.inputs)
            passed = evaluate_expression(tree, env)
            if passed:
                continue

            measured = None if rule.suppress_measured else _pick_measured(env, rule.inputs)
            evidence = IssueEvidence(
                snippet=_format_message(rule.output_template, env),
                page_index=entity.page_index,
                measured_value=measured,
                threshold_value=threshold_for_evidence,
                unit=clause.unit if clause else None,
            )
            result.issues.append(
                Issue(
                    issue_id=_new_issue_id(),
                    rule_card_id=rule.id,
                    standard_clause_id=clause_id,
                    entity_ids=[entity.id],
                    bbox=entity.bbox,
                    page_index=entity.page_index,
                    severity=rule.severity or "error",
                    message=_format_message(rule.output_template, env),
                    evidence=evidence,
                )
            )
    return result


def _pick_measured(env: dict[str, Any], inputs: list[str]) -> float | None:
    for key in inputs:
        v = env.get(key)
        if isinstance(v, (int, float)):
            return float(v)
    return None
