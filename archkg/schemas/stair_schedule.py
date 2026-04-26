"""StairSchedule — manual entity-source lane for Stair (Phase 18-C).

Phase 15 added five Stair-applies-to rule cards (tread / riser / flight
width / handrail height / well width) plus engine wiring, but the PDF
graph builder produces zero Stair entities — stair detection from a
plan view needs CV + dimensional reasoning that doesn't exist yet.
v1.0.1's readiness lane therefore tiered all five as STAIR_PENDING.

Unlike RoomSchedule (which augments Room.properties on rooms the
builder already created), StairSchedule is the *source* of stair
entities. Each entry materializes one Stair appended to graph.stairs.
When a future PDF stair-detection pass lands, the builder becomes the
authoritative source and the schedule degrades to a manual override or
supplement — same pattern as RoomSchedule.

Selector model: each entry must have `stair_id` (becomes Stair.id).
There's no fallback "all stairs" semantic — without a builder anchor,
each stair is a distinct user-declared instance.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class StairScheduleEntry(BaseModel):
    """One stair declared by the user."""

    model_config = ConfigDict(extra="forbid")

    stair_id: str = Field(
        ...,
        min_length=1,
        description="Stable stair identifier (becomes Stair.id; e.g. 'stair-A').",
    )
    page_index: int = Field(
        0,
        ge=0,
        description="Sheet/page the stair lives on. Defaults to 0 for single-page demos.",
    )

    # Stair entity schema fields. The engine reads these directly via
    # hasattr fallback before checking properties; populating them keeps
    # serialized graphs faithful to the schema.
    tread_width_m: float | None = Field(None, gt=0.0)
    riser_height_m: float | None = Field(None, gt=0.0)

    # Stair.properties fields. Five Phase 15 rules read these; engine
    # falls back to entity.properties.get(key) when hasattr returns False.
    flight_width_m: float | None = Field(None, gt=0.0)
    handrail_height_m: float | None = Field(None, gt=0.0)
    well_width_m: float | None = Field(None, ge=0.0)

    note: str | None = None

    def has_any_metric(self) -> bool:
        return any(
            v is not None
            for v in (
                self.tread_width_m,
                self.riser_height_m,
                self.flight_width_m,
                self.handrail_height_m,
                self.well_width_m,
            )
        )


class StairSchedule(BaseModel):
    """Companion stair schedule keyed against a ProjectMeta.project_id."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    project_id: str = Field(..., min_length=1)
    entries: list[StairScheduleEntry] = Field(default_factory=list)
    notes: str | None = None
