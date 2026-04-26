"""Schema-level tests for RoomSchedule (Phase 18-B)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from archkg.schemas import RoomSchedule, RoomScheduleEntry


def test_entry_requires_at_least_one_selector() -> None:
    with pytest.raises(ValidationError, match="room_id or label"):
        RoomScheduleEntry(net_height_m=2.4)


def test_entry_accepts_room_id_only() -> None:
    e = RoomScheduleEntry(room_id="room-3", net_height_m=2.50)
    assert e.room_id == "room-3"
    assert e.label is None


def test_entry_accepts_label_only() -> None:
    e = RoomScheduleEntry(label="bedroom", level="basement")
    assert e.label == "bedroom"
    assert e.level == "basement"


def test_entry_rejects_invalid_level() -> None:
    with pytest.raises(ValidationError):
        RoomScheduleEntry(label="bedroom", level="attic")


def test_entry_rejects_zero_or_negative_net_height() -> None:
    with pytest.raises(ValidationError):
        RoomScheduleEntry(label="bedroom", net_height_m=0.0)
    with pytest.raises(ValidationError):
        RoomScheduleEntry(label="bedroom", net_height_m=-1.0)


def test_entry_rejects_extra_fields() -> None:
    # extra="forbid" — protects against typos in property names that
    # would otherwise silently produce a no-op entry.
    with pytest.raises(ValidationError):
        RoomScheduleEntry(label="bedroom", height_m=2.5)  # type: ignore[call-arg]


def test_has_any_property_detects_selector_orphans() -> None:
    selector_only = RoomScheduleEntry(label="bedroom")
    assert not selector_only.has_any_property()
    with_height = RoomScheduleEntry(label="bedroom", net_height_m=2.40)
    assert with_height.has_any_property()
    with_only_pitched = RoomScheduleEntry(label="bedroom", pitched_roof=False)
    assert with_only_pitched.has_any_property()


def test_schedule_requires_project_id() -> None:
    with pytest.raises(ValidationError):
        RoomSchedule(entries=[])  # type: ignore[call-arg]


def test_schedule_is_frozen() -> None:
    s = RoomSchedule(project_id="DEMO", entries=[])
    with pytest.raises(ValidationError):
        s.project_id = "OTHER"  # type: ignore[misc]
