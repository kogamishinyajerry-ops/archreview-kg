from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from archkg.schemas.rule_card import RuleScope

RuleInputReadinessStatus = Literal[
    "ready",
    "missing_input",
    "low_confidence",
    "manual_only",
    "not_applicable",
    "unsupported_entity",
]


class RuleInputReadiness(BaseModel):
    """Per-run input readiness for one loaded rule card."""

    model_config = ConfigDict(extra="forbid")

    rule_id: str
    source_clause_ids: list[str]
    applies_to: RuleScope
    severity: str
    status: RuleInputReadinessStatus
    required_inputs: list[str] = Field(default_factory=list)
    available_inputs: list[str] = Field(default_factory=list)
    missing_inputs: list[str] = Field(default_factory=list)
    entity_count: int | None = None
    candidate_entity_ids: list[str] = Field(default_factory=list)
    low_confidence_entity_ids: list[str] = Field(default_factory=list)
    source: str
    reason: str


class RuleInputReadinessReport(BaseModel):
    """Stable JSON artifact written next to issues.json for each review run."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rule_input_readiness.v1"] = "rule_input_readiness.v1"
    summary: dict[RuleInputReadinessStatus, int]
    rules: list[RuleInputReadiness]
