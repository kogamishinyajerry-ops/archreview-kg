from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ThresholdOp = Literal[">=", "<=", ">", "<", "==", "!="]

BuildingType = Literal["residential", "public", "industrial"]
HeightClass = Literal["低层", "多层", "中高层", "高层", "超高层"]
ClauseCategory = Literal[
    "geometric",
    "topological",
    "fire",
    "accessibility",
    "energy",
    "acoustic",
    "general",
]


class StandardClause(BaseModel):
    """A single normative clause from a building code (e.g. GB 50096).

    Phase 8 metadata fields (`category`, `applies_to_*`, `version`, `supersedes`,
    `paraphrase`) all carry backwards-compatible defaults so pre-Phase 8 yaml
    entries continue to validate.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(..., description="Stable id, e.g. 'GB50096-7.1.1'")
    source: str = Field(..., description="Standard short name, e.g. 'GB 50096-2011'")
    clause_text: str = Field(
        ..., description="Clause text — verbatim by default; mark `paraphrase: true` if rewritten."
    )
    unit: str = Field(..., description="Unit of the threshold, e.g. 'm', 'm^2'")
    threshold_value: float | None = None
    threshold_op: ThresholdOp | None = None

    category: ClauseCategory = Field(
        "geometric",
        description="Clause family — drives evaluator selection in Phase 11.",
    )
    applies_to_building_type: tuple[BuildingType, ...] = Field(
        ("residential",),
        description="Project-types this clause is mandatory for. Empty tuple is invalid.",
        min_length=1,
    )
    applies_to_height_class: tuple[HeightClass, ...] | None = Field(
        None,
        description="Height classes this clause applies to; None = all heights.",
    )
    version: str | None = Field(
        None,
        description="Authoritative edition tag, e.g. '2011'. Falls back to year embedded in `source`.",
    )
    supersedes: str | None = Field(
        None,
        description="If non-null, the id of the older clause this one replaces.",
    )
    paraphrase: bool = Field(
        False,
        description="True iff `clause_text` is rewritten rather than verbatim from the standard.",
    )
