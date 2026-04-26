"""Loader tests for room schedule YAML files (Phase 18-B)."""

from __future__ import annotations

from pathlib import Path

import pytest

from archkg.knowledge.room_schedule import RoomScheduleError, load_room_schedule


def test_load_packaged_demo_schedule() -> None:
    """The shipped demo schedule must round-trip through the loader."""
    path = Path(__file__).parent.parent / "samples" / "room_schedule_demo.yaml"
    schedule = load_room_schedule(path)
    assert schedule.project_id == "DEMO-001"
    assert len(schedule.entries) == 4
    labels = {e.label for e in schedule.entries}
    assert labels == {"bedroom", "living", "bathroom", "kitchen"}


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(RoomScheduleError, match="missing"):
        load_room_schedule(tmp_path / "no-such-file.yaml")


def test_non_mapping_top_level_raises(tmp_path: Path) -> None:
    target = tmp_path / "schedule.yaml"
    target.write_text("- just a list\n", encoding="utf-8")
    with pytest.raises(RoomScheduleError, match="YAML mapping"):
        load_room_schedule(target)


def test_invalid_schema_raises(tmp_path: Path) -> None:
    target = tmp_path / "schedule.yaml"
    target.write_text(
        "project_id: X\nentries:\n  - net_height_m: 2.5\n",
        encoding="utf-8",
    )
    # Entry has no selector — model_validator should reject.
    with pytest.raises(RoomScheduleError, match="invalid room schedule"):
        load_room_schedule(target)


def test_extra_key_rejected(tmp_path: Path) -> None:
    target = tmp_path / "schedule.yaml"
    target.write_text(
        "project_id: X\nentries:\n  - label: bedroom\n    height_m: 2.5\n",
        encoding="utf-8",
    )
    with pytest.raises(RoomScheduleError):
        load_room_schedule(target)
