"""Loader tests for stair schedule YAML files (Phase 18-C)."""

from __future__ import annotations

from pathlib import Path

import pytest

from archkg.knowledge.stair_schedule import (
    StairScheduleError,
    load_stair_schedule,
)


def test_load_packaged_demo_schedule() -> None:
    path = Path(__file__).parent.parent / "samples" / "stair_schedule_demo.yaml"
    schedule = load_stair_schedule(path)
    assert schedule.project_id == "DEMO-001"
    assert len(schedule.entries) == 1
    entry = schedule.entries[0]
    assert entry.stair_id == "stair-1"
    # Adversarial fixture — every metric set:
    assert entry.tread_width_m == 0.24
    assert entry.riser_height_m == 0.18
    assert entry.flight_width_m == 0.95
    assert entry.handrail_height_m == 0.85
    assert entry.well_width_m == 0.14


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(StairScheduleError, match="missing"):
        load_stair_schedule(tmp_path / "no-such-file.yaml")


def test_non_mapping_top_level_raises(tmp_path: Path) -> None:
    target = tmp_path / "schedule.yaml"
    target.write_text("- just a list\n", encoding="utf-8")
    with pytest.raises(StairScheduleError, match="YAML mapping"):
        load_stair_schedule(target)


def test_invalid_schema_raises(tmp_path: Path) -> None:
    # Missing stair_id — entry is invalid.
    target = tmp_path / "schedule.yaml"
    target.write_text(
        "project_id: X\nentries:\n  - tread_width_m: 0.26\n",
        encoding="utf-8",
    )
    with pytest.raises(StairScheduleError, match="invalid stair schedule"):
        load_stair_schedule(target)


def test_extra_key_rejected(tmp_path: Path) -> None:
    target = tmp_path / "schedule.yaml"
    target.write_text(
        "project_id: X\nentries:\n  - stair_id: s1\n    tread: 0.26\n",
        encoding="utf-8",
    )
    with pytest.raises(StairScheduleError):
        load_stair_schedule(target)
