from __future__ import annotations

from importlib.resources import files
from pathlib import Path

import yaml
from pydantic import TypeAdapter, ValidationError

from archkg.schemas import RuleCard, StandardClause


class KnowledgeBaseError(RuntimeError):
    """Raised when the knowledge base on disk is malformed or inconsistent."""


_STANDARDS_ADAPTER: TypeAdapter[list[StandardClause]] = TypeAdapter(list[StandardClause])
_RULES_ADAPTER: TypeAdapter[list[RuleCard]] = TypeAdapter(list[RuleCard])


def _packaged_data_path(name: str) -> Path:
    return Path(str(files("archkg.knowledge.data").joinpath(name)))


def _read_yaml(path: Path) -> object:
    if not path.exists():
        raise KnowledgeBaseError(f"knowledge file missing: {path}")
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_standards(path: Path | None = None) -> list[StandardClause]:
    """Load and validate building-code clauses. Raises on any schema violation."""
    target = path or _packaged_data_path("standards.yaml")
    raw = _read_yaml(target)
    if not isinstance(raw, list):
        raise KnowledgeBaseError(f"{target.name} must be a YAML list, got {type(raw).__name__}")
    try:
        clauses = _STANDARDS_ADAPTER.validate_python(raw)
    except ValidationError as exc:
        raise KnowledgeBaseError(f"invalid standards.yaml: {exc}") from exc
    _check_unique_ids(clauses, target.name)
    return clauses


def load_rules(
    path: Path | None = None,
    standards: list[StandardClause] | None = None,
) -> list[RuleCard]:
    """Load and validate rule cards. If `standards` is provided, also verifies
    that every `source_clause_ids` entry resolves to a known clause."""
    target = path or _packaged_data_path("rule_cards.yaml")
    raw = _read_yaml(target)
    if not isinstance(raw, list):
        raise KnowledgeBaseError(f"{target.name} must be a YAML list, got {type(raw).__name__}")
    try:
        rules = _RULES_ADAPTER.validate_python(raw)
    except ValidationError as exc:
        raise KnowledgeBaseError(f"invalid rule_cards.yaml: {exc}") from exc
    _check_unique_ids(rules, target.name)
    if standards is not None:
        _check_clause_references(rules, standards)
    return rules


def _check_unique_ids(items: list[StandardClause] | list[RuleCard], filename: str) -> None:
    seen: set[str] = set()
    for it in items:
        if it.id in seen:
            raise KnowledgeBaseError(f"duplicate id '{it.id}' in {filename}")
        seen.add(it.id)


def _check_clause_references(
    rules: list[RuleCard], standards: list[StandardClause]
) -> None:
    known = {s.id for s in standards}
    for rule in rules:
        missing = [cid for cid in rule.source_clause_ids if cid not in known]
        if missing:
            raise KnowledgeBaseError(
                f"rule {rule.id} references unknown clause(s): {missing}"
            )
