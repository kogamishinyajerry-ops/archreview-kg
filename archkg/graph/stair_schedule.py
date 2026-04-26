"""Apply StairSchedule to an EntityGraph (Phase 18-C).

Materializes Stair entities from a user-supplied schedule and appends
them to graph.stairs. Unlike RoomSchedule (augmenting existing rooms),
StairSchedule is the entity *source* — the PDF builder produces zero
stairs today.

Conflict policy: if a schedule entry's stair_id already exists in
graph.stairs, the entry is recorded as `conflicted` rather than
overwriting. The builder is the authoritative source the moment it
gains stair detection; refusing to silently overwrite preserves that
contract.

Design note: schedule entries don't carry geometry, so synthesized
Stair entities use a placeholder bbox of (0, 0, 0, 0) and confidence
0.0 with `uncertain=True`. The annotator skips zero-area bboxes, so
schedule-only stairs surface in the issue list and report but not as
red boxes on the PDF — which is the right behaviour: we know the
stair exists by user assertion, not by geometric detection.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from archkg.graph.builder import EntityGraph
from archkg.schemas import Stair, StairSchedule, StairScheduleEntry

# Placeholder geometry for schedule-only stairs. The annotator's
# bbox-drawing path skips zero-area bboxes already (annotate_pdf
# clamps to the page), so this is a faithful "we don't know where
# it sits on the page" signal rather than a misleading anchor.
_PLACEHOLDER_BBOX = (0.0, 0.0, 0.0, 0.0)


class StairScheduleApplyError(ValueError):
    """Raised when a stair schedule entry can't be safely applied to the graph
    (e.g. page_index out of range)."""


@dataclass
class ApplyStairScheduleResult:
    """Audit trail for apply_stair_schedule.

    `materialized`: entry index → newly-created Stair.id.
    `conflicted`: entry indexes whose stair_id already existed in the
    input graph.stairs. Builder geometry is preserved; schedule
    metrics are merged onto the existing stair where the existing
    field is None (Codex P18-C R1 P1: "builder authoritative,
    schedule supplements" pattern).
    `empty_metric_entries`: entries with no metrics set; they create
    a Stair with all-None metrics, which is a no-op against the
    Phase 15 rules (every rule short-circuits on None) and is worth
    flagging.
    """

    graph: EntityGraph
    materialized: dict[int, str] = field(default_factory=dict)
    conflicted: list[int] = field(default_factory=list)
    empty_metric_entries: list[int] = field(default_factory=list)


def _entry_to_stair(entry: StairScheduleEntry) -> Stair:
    properties: dict[str, float | int | str | bool] = {}
    if entry.flight_width_m is not None:
        properties["flight_width_m"] = entry.flight_width_m
    if entry.handrail_height_m is not None:
        properties["handrail_height_m"] = entry.handrail_height_m
    if entry.well_width_m is not None:
        properties["well_width_m"] = entry.well_width_m
    return Stair(
        id=entry.stair_id,
        page_index=entry.page_index,
        bbox=_PLACEHOLDER_BBOX,
        confidence=0.0,
        uncertain=True,
        tread_width_m=entry.tread_width_m,
        riser_height_m=entry.riser_height_m,
        properties=properties,
    )


def _merge_metrics_onto_existing(existing: Stair, entry: StairScheduleEntry) -> Stair:
    """Schedule supplements builder. Fill in None fields on the existing stair
    with schedule values; never overwrite values the builder already set."""
    update_fields: dict[str, float | None] = {}
    if existing.tread_width_m is None and entry.tread_width_m is not None:
        update_fields["tread_width_m"] = entry.tread_width_m
    if existing.riser_height_m is None and entry.riser_height_m is not None:
        update_fields["riser_height_m"] = entry.riser_height_m

    new_props: dict[str, float | int | str | bool] = dict(existing.properties)
    if entry.flight_width_m is not None and "flight_width_m" not in new_props:
        new_props["flight_width_m"] = entry.flight_width_m
    if entry.handrail_height_m is not None and "handrail_height_m" not in new_props:
        new_props["handrail_height_m"] = entry.handrail_height_m
    if entry.well_width_m is not None and "well_width_m" not in new_props:
        new_props["well_width_m"] = entry.well_width_m

    return existing.model_copy(update={**update_fields, "properties": new_props})


def apply_stair_schedule(
    graph: EntityGraph, schedule: StairSchedule
) -> ApplyStairScheduleResult:
    """Return a new EntityGraph whose stairs list has the schedule's
    materialized entries appended.

    Existing graph.stairs keep their builder-supplied geometry; schedule
    metrics merge onto them only where the builder left a field None.
    The original graph is not mutated.

    Raises StairScheduleApplyError if any entry's page_index is outside
    the graph's page range. The current builder is single-page so anything
    other than graph.page_index is rejected; future multi-page graphs
    would relax this against an explicit page-count attribute.
    """
    existing_by_id = {s.id: s for s in graph.stairs}
    new_stairs: list[Stair] = list(graph.stairs)

    materialized: dict[int, str] = {}
    conflicted: list[int] = []
    empty: list[int] = []

    for idx, entry in enumerate(schedule.entries):
        # Codex P18-C R1 P0: page_index must be valid for the graph.
        # The builder is single-page; entry.page_index != graph.page_index
        # would otherwise crash the annotator with IndexError.
        if entry.page_index != graph.page_index:
            raise StairScheduleApplyError(
                f"stair schedule entry {idx} (stair_id='{entry.stair_id}') has "
                f"page_index={entry.page_index}, but the entity graph only covers "
                f"page_index={graph.page_index}. Adjust the schedule or extend the "
                f"builder to multi-page first."
            )

        if entry.stair_id in existing_by_id:
            # Merge schedule metrics onto builder-sourced stair (Codex
            # P18-C R1 P1). Builder geometry stays authoritative.
            merged = _merge_metrics_onto_existing(existing_by_id[entry.stair_id], entry)
            # Replace by id in the running list AND in the lookup map so
            # later rows with the same stair_id merge onto the running
            # state, not the stale original (Codex P18-C R2 P1).
            for i, s in enumerate(new_stairs):
                if s.id == entry.stair_id:
                    new_stairs[i] = merged
                    break
            existing_by_id[entry.stair_id] = merged
            conflicted.append(idx)
            continue

        stair = _entry_to_stair(entry)
        new_stairs.append(stair)
        existing_by_id[stair.id] = stair
        materialized[idx] = stair.id
        if not entry.has_any_metric():
            empty.append(idx)

    new_graph = graph.model_copy(update={"stairs": new_stairs})
    return ApplyStairScheduleResult(
        graph=new_graph,
        materialized=materialized,
        conflicted=conflicted,
        empty_metric_entries=empty,
    )
