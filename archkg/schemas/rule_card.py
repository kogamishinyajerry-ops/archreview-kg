from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

EntityType = Literal["Room", "Door", "Wall", "Corridor", "Dimension", "Stair"]


class RuleCardTestCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    entity: dict[str, Any]
    expect_pass: bool
    note: str | None = None


class RuleCard(BaseModel):
    """A geometry-decidable rule, resolved to a single clause family."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., description="Stable rule id, e.g. 'RC-CORRIDOR-WIDTH'")
    source_clause_ids: list[str] = Field(..., min_length=1)
    applies_to: EntityType
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
    test_cases: list[RuleCardTestCase] = Field(default_factory=list)

    @field_validator("logic_expression")
    @classmethod
    def _non_empty_expression(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("logic_expression must not be empty")
        return v
