"""Build per-plan-sheet graph artifacts for multi-sheet drawing sets."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from archkg.graph.builder import EntityGraph, build_graph
from archkg.ingest.sheet_classification import SheetClassificationReport, SheetType
from archkg.schemas import PagePrimitives, Primitives


class SheetGraphSkippedPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_index: int = Field(..., ge=0)
    sheet_type: SheetType
    confidence: float = Field(..., ge=0.0, le=1.0)
    reason: str


class SheetGraphEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_index: int = Field(..., ge=0)
    sheet_type: Literal["plan"] = "plan"
    classification_confidence: float = Field(..., ge=0.0, le=1.0)
    component_counts: dict[str, int]
    graph: EntityGraph


class SheetGraphsReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["sheet_graphs.v1"] = "sheet_graphs.v1"
    source_pdf: str
    graph_count: int = Field(..., ge=0)
    confidence_floor: float = Field(..., ge=0.0, le=1.0)
    graphs: list[SheetGraphEntry] = Field(default_factory=list)
    skipped_pages: list[SheetGraphSkippedPage] = Field(default_factory=list)


def build_sheet_graphs(
    primitives: Primitives,
    classification: SheetClassificationReport,
    *,
    min_room_area_m2: float = 0.0,
    confidence_floor: float = 0.50,
) -> SheetGraphsReport:
    page_by_index = {page.page_index: page for page in primitives.pages}
    graphs: list[SheetGraphEntry] = []
    skipped_pages: list[SheetGraphSkippedPage] = []

    for classified in classification.pages:
        page = page_by_index.get(classified.page_index)
        if page is None:
            skipped_pages.append(
                SheetGraphSkippedPage(
                    page_index=classified.page_index,
                    sheet_type=classified.sheet_type,
                    confidence=classified.confidence,
                    reason="page missing from graph primitives",
                )
            )
            continue
        if not (
            classified.sheet_type == "plan"
            and classified.eligible_for_graph
            and classified.confidence >= confidence_floor
        ):
            skipped_pages.append(
                SheetGraphSkippedPage(
                    page_index=classified.page_index,
                    sheet_type=classified.sheet_type,
                    confidence=classified.confidence,
                    reason="not a confident graph-eligible plan page",
                )
            )
            continue

        graph = build_graph(
            _single_page_primitives(primitives, page),
            min_room_area_m2=min_room_area_m2,
        )
        graphs.append(
            SheetGraphEntry(
                page_index=classified.page_index,
                classification_confidence=classified.confidence,
                component_counts=_component_counts(graph),
                graph=graph,
            )
        )

    return SheetGraphsReport(
        source_pdf=primitives.source_pdf,
        graph_count=len(graphs),
        confidence_floor=confidence_floor,
        graphs=graphs,
        skipped_pages=skipped_pages,
    )


def write_sheet_graphs(report: SheetGraphsReport, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return out_path


def _single_page_primitives(source: Primitives, page: PagePrimitives) -> Primitives:
    return Primitives(
        source_pdf=source.source_pdf,
        points_per_meter=source.points_per_meter,
        pages=[page],
    )


def _component_counts(graph: EntityGraph) -> dict[str, int]:
    return {
        "rooms": len(graph.rooms),
        "doors": len(graph.doors),
        "corridors": len(graph.corridors),
        "stairs": len(graph.stairs),
        "dimensions": len(graph.dimensions),
    }


__all__ = [
    "SheetGraphEntry",
    "SheetGraphSkippedPage",
    "SheetGraphsReport",
    "build_sheet_graphs",
    "write_sheet_graphs",
]
