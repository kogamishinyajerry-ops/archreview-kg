from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

IssueReviewStatus = Literal[
    "candidate",
    "confirmed",
    "rejected",
    "needs_info",
    "resolved",
    "superseded",
]


class IssueReviewStateItem(BaseModel):
    """Human review state for one rule-engine candidate issue."""

    model_config = ConfigDict(extra="forbid")

    issue_id: str
    rule_card_id: str
    status: IssueReviewStatus = "candidate"
    reviewer: str | None = None
    note: str | None = None
    source_run_id: str | None = None
    superseded_by_run_id: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class IssueReviewState(BaseModel):
    """Stable JSON artifact stored next to issues.json for each review run."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["issue_review_state.v1"] = "issue_review_state.v1"
    run_id: str | None = None
    generated_at: str | None = None
    summary: dict[IssueReviewStatus, int] = Field(default_factory=dict)
    items: list[IssueReviewStateItem] = Field(default_factory=list)
