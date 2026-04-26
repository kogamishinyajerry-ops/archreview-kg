"""RoomSchedule — manual augmentation lane for Room.properties.

Phase 18-B motivation: 4 rule cards (RC-LIVING-BEDROOM-NETHEIGHT-2.4 /
RC-PITCHED-ROOF-MAJORITY-NETHEIGHT-2.1 / RC-BASEMENT-MEZZANINE-NETHEIGHT-2.0 /
RC-NO-LIVING-IN-BASEMENT) need Room.properties keys (`net_height_m`,
`level`, `pitched_roof`, `majority_net_height_m`) that the current PDF
graph builder cannot extract — they live on section views, in floor
schedules, or in title blocks the builder doesn't yet read.

Rather than block all four rules until a CV pass lands, this schema lets
the user supply the data manually via a companion YAML file. Same data
shape a future PDF-extraction pass would produce, so when the builder
gains those passes the schedule simply becomes one of two upstream
sources rather than a parallel data path.

Selector model: each entry must specify either `room_id` (exact match
against Room.id) or `label` (matches every Room with that normalized
label — e.g. `label: bedroom` applies to all rooms classified as
bedrooms). Both → `room_id` wins. Neither → validation error.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Whitelist of `level` values the rule cards understand (RC-BASEMENT-...
# checks `level == 'basement'`, RC-NO-LIVING-IN-BASEMENT same). Keep
# this in lock-step with the rule logic; widening it here without a
# matching rule update creates silent dead data.
RoomLevel = Literal["basement", "ground", "upper", "mezzanine"]


class RoomScheduleEntry(BaseModel):
    """One row of a room schedule. Selector + whitelisted properties."""

    model_config = ConfigDict(extra="forbid")

    # Selector — at least one of room_id / label must be set.
    room_id: str | None = Field(
        None,
        description="Exact Room.id match (deterministic — wins over label).",
    )
    label: str | None = Field(
        None,
        description="Normalized Room.label match (e.g. 'bedroom'). Applies to every room with that label.",
    )

    # Whitelisted properties. Kept tight to the four PARTIAL_AUTODETECT
    # rule cards' inputs as of v1.0.1; new fields land here only when a
    # rule consumes them.
    net_height_m: float | None = Field(
        None,
        gt=0.0,
        description="Room clear net height in metres (typically from section view).",
    )
    majority_net_height_m: float | None = Field(
        None,
        gt=0.0,
        description="For pitched-roof rooms: net height at the area-weighted majority point.",
    )
    level: RoomLevel | None = Field(
        None,
        description="Floor level the room sits on. Drives basement / mezzanine rules.",
    )
    pitched_roof: bool | None = Field(
        None,
        description="Whether the room is under a pitched roof (drives RC-PITCHED-ROOF-MAJORITY-NETHEIGHT-2.1).",
    )

    note: str | None = None

    @model_validator(mode="after")
    def _at_least_one_selector(self) -> RoomScheduleEntry:
        if self.room_id is None and self.label is None:
            raise ValueError("RoomScheduleEntry requires either room_id or label")
        return self

    def has_any_property(self) -> bool:
        return any(
            v is not None
            for v in (
                self.net_height_m,
                self.majority_net_height_m,
                self.level,
                self.pitched_roof,
            )
        )


class RoomSchedule(BaseModel):
    """Companion schedule keyed against a ProjectMeta.project_id."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    project_id: str = Field(..., min_length=1)
    entries: list[RoomScheduleEntry] = Field(default_factory=list)
    notes: str | None = None
