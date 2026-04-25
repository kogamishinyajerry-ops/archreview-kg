"""Project-context driven rule applicability.

A clause is "applicable" iff:
  - the project's building_type is in clause.applies_to_building_type
  - the clause has no height-class restriction, OR the project's
    height_class is in clause.applies_to_height_class

A rule is "applicable" iff at least ONE of its source_clause_ids resolves
to an applicable clause. (Multi-source rules can stay relevant if any of
their backing clauses match the project.)

When `meta is None` everything is applicable — preserves the pre-Phase-9
no-context behaviour.
"""

from __future__ import annotations

from archkg.labels import label_building_type, label_building_types
from archkg.schemas import ProjectMeta, RuleCard, StandardClause


def is_clause_applicable(clause: StandardClause, meta: ProjectMeta | None) -> bool:
    if meta is None:
        return True
    if meta.building_type not in clause.applies_to_building_type:
        return False
    if clause.applies_to_height_class is not None:
        if meta.height_class not in clause.applies_to_height_class:
            return False
    return True


def is_rule_applicable(
    rule: RuleCard,
    meta: ProjectMeta | None,
    standards_by_id: dict[str, StandardClause],
) -> bool:
    if meta is None:
        return True
    return any(
        cid in standards_by_id and is_clause_applicable(standards_by_id[cid], meta)
        for cid in rule.source_clause_ids
    )


def skip_reason(
    rule: RuleCard,
    meta: ProjectMeta,
    standards_by_id: dict[str, StandardClause],
) -> str:
    """Human-readable reason a rule was skipped under the current project meta.
    Caller is responsible for only invoking this when the rule is non-applicable.
    """
    parts: list[str] = []
    for cid in rule.source_clause_ids:
        clause = standards_by_id.get(cid)
        if clause is None:
            parts.append(f"{cid}: 标准库未找到")
            continue
        if meta.building_type not in clause.applies_to_building_type:
            wanted = label_building_types(clause.applies_to_building_type)
            actual = label_building_type(meta.building_type)
            parts.append(f"{cid}: 仅适用 {wanted}（项目为 {actual}）")
            continue
        if clause.applies_to_height_class is not None and meta.height_class not in clause.applies_to_height_class:
            wanted = "/".join(clause.applies_to_height_class)
            parts.append(f"{cid}: 仅适用 {wanted}（项目为 {meta.height_class}）")
            continue
        parts.append(f"{cid}: 已适用")
    return "; ".join(parts) if parts else "无原因"
