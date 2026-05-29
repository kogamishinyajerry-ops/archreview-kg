"""Protected routing from multi-sheet primitives to graph-builder input."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from archkg.ingest.sheet_classification import SheetClassificationReport
from archkg.schemas import PagePrimitives, Primitives

RoutingMode = Literal["legacy_all_pages", "classified_single_plan_page"]


class SheetRoutingDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["sheet_routing.v1"] = "sheet_routing.v1"
    mode: RoutingMode
    selected_page_indexes: list[int] = Field(default_factory=list)
    excluded_page_indexes: list[int] = Field(default_factory=list)
    original_page_count: int = Field(..., ge=0)
    graph_page_count: int = Field(..., ge=0)
    confidence_floor: float = Field(..., ge=0.0, le=1.0)
    reason: str
    fallback_reason: str | None = None
    source_sheet_classification_schema: str = "unknown"
    manual_sheet_region_applied: bool = False


@dataclass(frozen=True)
class SheetRoutingResult:
    primitives: Primitives
    decision: SheetRoutingDecision


def route_primitives_for_graph(
    primitives: Primitives,
    classification: SheetClassificationReport,
    *,
    confidence_floor: float = 0.50,
    manual_sheet_region_applied: bool = False,
) -> SheetRoutingResult:
    """Return the protected graph input and the routing decision.

    Routing is intentionally conservative. It only narrows graph input when a
    multi-sheet run has exactly one confident plan page and every other page is
    a confident non-graph sheet. Unknown, low-confidence, missing, or multiple
    plan pages fall back to legacy all-page input.
    """

    all_indexes = [page.page_index for page in primitives.pages]
    if len(primitives.pages) <= 1:
        return _legacy(
            primitives,
            confidence_floor=confidence_floor,
            reason="single page run; legacy graph input retained",
            fallback_reason="single_page_run",
            classification=classification,
            manual_sheet_region_applied=manual_sheet_region_applied,
        )

    classified_by_page = {page.page_index: page for page in classification.pages}
    if set(classified_by_page) != set(all_indexes):
        return _legacy(
            primitives,
            confidence_floor=confidence_floor,
            reason="classification page set does not match primitives page set",
            fallback_reason="classification_page_mismatch",
            classification=classification,
            manual_sheet_region_applied=manual_sheet_region_applied,
        )

    eligible_plan_pages = [
        page
        for page in classification.pages
        if page.sheet_type == "plan"
        and page.eligible_for_graph
        and page.confidence >= confidence_floor
    ]
    if not eligible_plan_pages:
        return _legacy(
            primitives,
            confidence_floor=confidence_floor,
            reason="no confident plan page found; legacy graph input retained",
            fallback_reason="no_eligible_plan_page",
            classification=classification,
            manual_sheet_region_applied=manual_sheet_region_applied,
        )
    if len(eligible_plan_pages) > 1:
        return _legacy(
            primitives,
            confidence_floor=confidence_floor,
            reason="multiple confident plan pages require future multi-graph support",
            fallback_reason="multiple_eligible_plan_pages",
            classification=classification,
            manual_sheet_region_applied=manual_sheet_region_applied,
        )

    plan_page = eligible_plan_pages[0]
    non_plan_pages = [
        page for page in classification.pages if page.page_index != plan_page.page_index
    ]
    if any(
        page.sheet_type == "unknown" or page.confidence < confidence_floor
        for page in non_plan_pages
    ):
        return _legacy(
            primitives,
            confidence_floor=confidence_floor,
            reason="at least one non-plan page is unknown or low-confidence",
            fallback_reason="unknown_or_low_confidence_non_plan_page",
            classification=classification,
            manual_sheet_region_applied=manual_sheet_region_applied,
        )

    selected_indexes = [plan_page.page_index]
    routed_pages = _select_pages(primitives.pages, selected_indexes)
    routed_primitives = Primitives(
        source_pdf=primitives.source_pdf,
        points_per_meter=primitives.points_per_meter,
        pages=routed_pages,
    )
    excluded_indexes = [index for index in all_indexes if index not in selected_indexes]
    decision = SheetRoutingDecision(
        mode="classified_single_plan_page",
        selected_page_indexes=selected_indexes,
        excluded_page_indexes=excluded_indexes,
        original_page_count=len(primitives.pages),
        graph_page_count=len(routed_pages),
        confidence_floor=confidence_floor,
        reason="single confident plan page selected; non-graph sheets excluded from graph input",
        source_sheet_classification_schema=classification.schema_version,
        manual_sheet_region_applied=manual_sheet_region_applied,
    )
    return SheetRoutingResult(primitives=routed_primitives, decision=decision)


def write_sheet_routing(decision: SheetRoutingDecision, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(decision.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return out_path


def _legacy(
    primitives: Primitives,
    *,
    confidence_floor: float,
    reason: str,
    fallback_reason: str,
    classification: SheetClassificationReport,
    manual_sheet_region_applied: bool,
) -> SheetRoutingResult:
    selected_indexes = [page.page_index for page in primitives.pages]
    decision = SheetRoutingDecision(
        mode="legacy_all_pages",
        selected_page_indexes=selected_indexes,
        excluded_page_indexes=[],
        original_page_count=len(primitives.pages),
        graph_page_count=len(primitives.pages),
        confidence_floor=confidence_floor,
        reason=reason,
        fallback_reason=fallback_reason,
        source_sheet_classification_schema=classification.schema_version,
        manual_sheet_region_applied=manual_sheet_region_applied,
    )
    return SheetRoutingResult(primitives=primitives, decision=decision)


def _select_pages(
    pages: list[PagePrimitives],
    selected_indexes: list[int],
) -> list[PagePrimitives]:
    selected = set(selected_indexes)
    return [page for page in pages if page.page_index in selected]


__all__ = [
    "SheetRoutingDecision",
    "SheetRoutingResult",
    "route_primitives_for_graph",
    "write_sheet_routing",
]
