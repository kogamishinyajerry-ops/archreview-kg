from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ThresholdOp = Literal[">=", "<=", ">", "<", "==", "!="]


class StandardClause(BaseModel):
    """A single normative clause from a building code (e.g. GB 50096)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(..., description="Stable id, e.g. 'GB50096-7.1.1'")
    source: str = Field(..., description="Standard short name, e.g. 'GB 50096-2011'")
    clause_text: str = Field(..., description="Verbatim clause text in source language")
    unit: str = Field(..., description="Unit of the threshold, e.g. 'm', 'm^2'")
    threshold_value: float | None = None
    threshold_op: ThresholdOp | None = None
