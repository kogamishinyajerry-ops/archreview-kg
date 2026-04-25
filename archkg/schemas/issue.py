from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Severity = Literal["error", "warning", "info"]
BBox = tuple[float, float, float, float]


class IssueEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snippet: str
    page_index: int = Field(..., ge=0)
    measured_value: float | None = None
    threshold_value: float | None = None
    unit: str | None = None


class Issue(BaseModel):
    """A reviewable defect tied to a rule card, clause, and at least one entity."""

    model_config = ConfigDict(extra="forbid")

    issue_id: str
    rule_card_id: str
    standard_clause_id: str
    entity_ids: list[str] = Field(..., min_length=1)
    bbox: BBox
    page_index: int = Field(..., ge=0)
    severity: Severity = "error"
    message: str
    evidence: IssueEvidence
