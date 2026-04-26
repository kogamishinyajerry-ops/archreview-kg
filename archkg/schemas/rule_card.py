from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

EntityType = Literal["Room", "Door", "Wall", "Corridor", "Dimension", "Stair"]
RuleScope = Literal[
    "Room", "Door", "Wall", "Corridor", "Dimension", "Stair",
    "Project",
]


class RuleCardTestCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    entity: dict[str, Any]
    expect_pass: bool
    note: str | None = None


RuleSeverity = Literal["error", "warning", "info"]


class RuleCard(BaseModel):
    """A geometry-decidable rule, resolved to a single clause family."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., description="Stable rule id, e.g. 'RC-CORRIDOR-WIDTH'")
    source_clause_ids: list[str] = Field(..., min_length=1)
    applies_to: RuleScope
    inputs: list[str] = Field(
        ...,
        min_length=1,
        description="Names of entity properties consumed by the rule (whitelisted).",
    )
    logic_expression: str = Field(
        ...,
        description="Whitelisted expression evaluated by the rule engine.",
    )
    output_template: str = Field(
        ...,
        description="Jinja-style template producing the human-readable issue message.",
    )
    # Phase 15 Codex P1: rule-level evidence overrides. With multi-source rules
    # (e.g. RC-STAIR-HANDRAIL-0.90 sourcing GB50096-6.3.2 whose primary
    # threshold is 0.26 m for tread width, not 0.90 m for handrail), copying
    # evidence from `source_clause_ids[0]` produced wrong report payloads.
    # When set, the engine uses these instead of falling back to the source
    # clause's threshold_value / a one-size severity policy.
    threshold_value: float | None = Field(
        None,
        description="Override evidence.threshold_value when the rule's threshold differs from source clause's primary threshold (e.g. multi-source rules).",
    )
    severity: RuleSeverity | None = Field(
        None,
        description="Override issue severity. Default: 'error' for entity-level rules, 'info' for Project-level rules. Use 'info' for entity-anchored reminders the engine cannot fully verify (e.g. 6.3.5 stair-well child safety: engine knows the well is wide but cannot tell if mitigations were taken).",
    )
    # Phase 17 Codex P2: when a rule's threshold is a derived quantity
    # (e.g. RC-ACCESSIBLE-RESIDENTIAL-RATIO checks accessible/total ratio
    # against 0.02), the default _pick_measured = first numeric input
    # produces a meaningless evidence record (total_units=200 vs ratio
    # threshold=0.02). Setting suppress_measured=True leaves evidence.
    # measured_value as None so the report doesn't compare apples to oranges.
    suppress_measured: bool = Field(
        False,
        description="When true, engine emits evidence.measured_value=None instead of the first-numeric-input fallback. Use for rules where no single input is the 'measured' value (ratios, multi-field predicates).",
    )
    test_cases: list[RuleCardTestCase] = Field(default_factory=list)

    @field_validator("logic_expression")
    @classmethod
    def _non_empty_expression(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("logic_expression must not be empty")
        return v
