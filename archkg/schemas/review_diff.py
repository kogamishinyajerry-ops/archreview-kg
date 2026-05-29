from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ReviewDiffStatus = Literal["unchanged", "changed", "new", "resolved"]


class ReviewDiffIssueRef(BaseModel):
    """Compact copy of a primary issues.json item used for re-run tracking."""

    model_config = ConfigDict(extra="forbid")

    issue_id: str
    rule_card_id: str
    standard_clause_id: str
    entity_ids: list[str] = Field(default_factory=list)
    bbox: tuple[float, float, float, float] | None = None
    page_index: int
    severity: str
    message: str
    evidence: dict[str, Any] = Field(default_factory=dict)


class ReviewDiffItem(BaseModel):
    """One matched, changed, new, or resolved issue across two review runs."""

    model_config = ConfigDict(extra="forbid")

    status: ReviewDiffStatus
    group_key: str
    occurrence_index: int = 0
    fingerprint_before: str | None = None
    fingerprint_after: str | None = None
    before_issue: ReviewDiffIssueRef | None = None
    after_issue: ReviewDiffIssueRef | None = None
    changed_fields: list[str] = Field(default_factory=list)


class ReviewDiffReport(BaseModel):
    """Stable JSON artifact comparing primary issue candidates from two runs."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["review_diff.v1"] = "review_diff.v1"
    before_run_id: str
    after_run_id: str
    before_run: str
    after_run: str
    mutation_policy: Literal["read_only_primary_issues_json"] = (
        "read_only_primary_issues_json"
    )
    summary: dict[ReviewDiffStatus, int] = Field(default_factory=dict)
    items: list[ReviewDiffItem] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
