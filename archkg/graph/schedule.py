"""Apply RoomSchedule to an EntityGraph (Phase 18-B).

The schedule is a manual upstream data source for Room.properties keys
the PDF builder doesn't yet extract. This module is the bridge: take a
loaded EntityGraph + RoomSchedule, return a new EntityGraph whose Rooms
carry the merged properties, plus an audit trail describing what was
matched and what wasn't (so the reviewer can spot dangling entries).

Merge semantics:
- Selector precedence: `room_id` exact match wins; falls back to `label`.
  Each entry can therefore target one specific room or a class of rooms.
- A `label` entry applies to every Room whose label matches; a missing
  match is reported as `unmatched`.
- Properties on the entry overwrite Room.properties on collision. The
  schedule is treated as the user's authoritative input — they wrote it
  explicitly. A future builder pass would be the source of "automatic"
  defaults; the schedule is the manual override.
- Only properties explicitly set on the entry get merged; unset (=None)
  fields are skipped so partial schedules compose naturally.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from archkg.graph.builder import EntityGraph
from archkg.schemas import Room, RoomSchedule, RoomScheduleEntry


@dataclass
class ApplyScheduleResult:
    """Audit trail returned by `apply_room_schedule`.

    `matched`: entry → list of room ids the entry was applied to.
    `unmatched`: entries whose selector found zero rooms (likely typo
    or schedule out of sync with the plan).
    `empty_property_entries`: entries that have a selector but no
    actual property value (selector orphans). These don't error but
    are worth surfacing.
    """

    graph: EntityGraph
    matched: dict[int, list[str]] = field(default_factory=dict)
    unmatched: list[int] = field(default_factory=list)
    empty_property_entries: list[int] = field(default_factory=list)


def _select_rooms(graph: EntityGraph, entry: RoomScheduleEntry) -> list[Room]:
    if entry.room_id is not None:
        return [r for r in graph.rooms if r.id == entry.room_id]
    if entry.label is not None:
        return [r for r in graph.rooms if r.label == entry.label]
    return []


def _entry_properties(entry: RoomScheduleEntry) -> dict[str, float | int | str | bool]:
    """Pluck the non-None whitelisted fields off an entry into a properties dict."""
    out: dict[str, float | int | str | bool] = {}
    if entry.net_height_m is not None:
        out["net_height_m"] = entry.net_height_m
    if entry.majority_net_height_m is not None:
        out["majority_net_height_m"] = entry.majority_net_height_m
    if entry.level is not None:
        out["level"] = entry.level
    if entry.pitched_roof is not None:
        out["pitched_roof"] = entry.pitched_roof
    return out


def apply_room_schedule(
    graph: EntityGraph, schedule: RoomSchedule
) -> ApplyScheduleResult:
    """Return a new EntityGraph with schedule entries merged into Room.properties.

    The original graph is left untouched. Rooms not targeted by any
    entry pass through unchanged.
    """
    rooms_by_id = {r.id: r for r in graph.rooms}
    # Make a shallow per-room copy so we can mutate properties without
    # leaking writes into the caller's input graph.
    new_rooms: dict[str, Room] = {
        rid: r.model_copy(update={"properties": dict(r.properties)})
        for rid, r in rooms_by_id.items()
    }

    matched: dict[int, list[str]] = {}
    unmatched: list[int] = []
    empty: list[int] = []

    for idx, entry in enumerate(schedule.entries):
        targets = _select_rooms(graph, entry)
        if not targets:
            unmatched.append(idx)
            continue
        props = _entry_properties(entry)
        if not props:
            empty.append(idx)
            continue
        room_ids: list[str] = []
        for room in targets:
            updated = new_rooms[room.id]
            new_props = {**updated.properties, **props}
            new_rooms[room.id] = updated.model_copy(update={"properties": new_props})
            room_ids.append(room.id)
        matched[idx] = room_ids

    new_graph = graph.model_copy(update={"rooms": list(new_rooms.values())})
    return ApplyScheduleResult(
        graph=new_graph,
        matched=matched,
        unmatched=unmatched,
        empty_property_entries=empty,
    )
