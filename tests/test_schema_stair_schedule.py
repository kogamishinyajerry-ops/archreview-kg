"""Schema tests for StairSchedule (Phase 18-C)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from archkg.schemas import StairSchedule, StairScheduleEntry


def test_entry_requires_stair_id() -> None:
    with pytest.raises(ValidationError):
        StairScheduleEntry(tread_width_m=0.26)  # type: ignore[call-arg]


def test_entry_rejects_empty_stair_id() -> None:
    with pytest.raises(ValidationError):
        StairScheduleEntry(stair_id="", tread_width_m=0.26)


def test_entry_rejects_zero_tread_width() -> None:
    with pytest.raises(ValidationError):
        StairScheduleEntry(stair_id="s1", tread_width_m=0.0)


def test_entry_rejects_negative_metric() -> None:
    with pytest.raises(ValidationError):
        StairScheduleEntry(stair_id="s1", riser_height_m=-0.1)


def test_entry_rejects_extra_fields() -> None:
    # extra="forbid" — protects against typos in property names that
    # would silently produce a stair with the metric None.
    with pytest.raises(ValidationError):
        StairScheduleEntry(stair_id="s1", flight_widht_m=1.10)  # type: ignore[call-arg]


def test_entry_well_width_can_be_zero() -> None:
    # well_width_m: stairwell can legitimately be 0 (no well).
    entry = StairScheduleEntry(stair_id="s1", well_width_m=0.0)
    assert entry.well_width_m == 0.0


def test_has_any_metric_distinguishes_selector_only() -> None:
    bare = StairScheduleEntry(stair_id="s1")
    assert not bare.has_any_metric()
    with_tread = StairScheduleEntry(stair_id="s1", tread_width_m=0.26)
    assert with_tread.has_any_metric()
    with_handrail = StairScheduleEntry(stair_id="s1", handrail_height_m=0.90)
    assert with_handrail.has_any_metric()


def test_schedule_requires_project_id() -> None:
    with pytest.raises(ValidationError):
        StairSchedule(entries=[])  # type: ignore[call-arg]


def test_schedule_is_frozen() -> None:
    s = StairSchedule(project_id="DEMO", entries=[])
    with pytest.raises(ValidationError):
        s.project_id = "OTHER"  # type: ignore[misc]
