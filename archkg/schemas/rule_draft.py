from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from archkg.schemas.rule_card import RuleCardTestCase, RuleScope
from archkg.schemas.standard import ClauseCategory, ThresholdOp


class DraftSourceClause(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    source: str
    category: ClauseCategory
    clause_text: str
    unit: str
    threshold_value: float | None = None
    threshold_op: ThresholdOp | None = None
    paraphrase: bool = False


class DraftThreshold(BaseModel):
    model_config = ConfigDict(extra="forbid")

    op: ThresholdOp | None = None
    value: float | None = None
    unit: str | None = None
    source: Literal["standard_clause_schema", "missing"] = "standard_clause_schema"


class RuleCardDraft(BaseModel):
    """Review-only rule-card candidate; never active compliance logic."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["rule_card_draft.v1"] = "rule_card_draft.v1"
    status: Literal["draft"] = "draft"
    draft_id: str
    source_clause: DraftSourceClause
    proposed_rule_id: str
    proposed_applies_to: RuleScope | None = None
    required_inputs: list[str] = Field(default_factory=list)
    extracted_threshold: DraftThreshold
    proposed_logic_expression: str | None = None
    proposed_output_template: str | None = None
    proposed_tests: list[RuleCardTestCase] = Field(default_factory=list)
    applicability: dict[str, object] = Field(default_factory=dict)
    ambiguity_notes: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    review_gate: str = (
        "Draft only. Human review is required before any promotion to active rule_cards.yaml."
    )
