from __future__ import annotations

import pytest
from pydantic import ValidationError

from archkg.schemas import ProjectMeta


def test_project_meta_minimal() -> None:
    meta = ProjectMeta(
        project_id="P-001",
        building_type="residential",
        height_class="多层",
    )
    assert meta.project_id == "P-001"
    assert meta.fire_class is None
    assert meta.height_m is None


def test_project_meta_full() -> None:
    meta = ProjectMeta(
        project_id="P-002",
        project_name="演示住宅",
        building_type="residential",
        height_class="高层",
        fire_class="一级",
        climate_zone="寒冷",
        use_type="住宅",
        height_m=80.0,
        floors=27,
        notes="N/A",
    )
    assert meta.height_class == "高层"
    assert meta.height_m == 80.0


def test_project_meta_rejects_extra_field() -> None:
    with pytest.raises(ValidationError):
        ProjectMeta(
            project_id="P-003",
            building_type="residential",
            height_class="多层",
            unknown="boom",  # type: ignore[call-arg]
        )


def test_project_meta_rejects_unknown_building_type() -> None:
    with pytest.raises(ValidationError):
        ProjectMeta(
            project_id="P-004",
            building_type="bogus",  # type: ignore[arg-type]
            height_class="多层",
        )


def test_project_meta_rejects_unknown_height_class() -> None:
    with pytest.raises(ValidationError):
        ProjectMeta(
            project_id="P-005",
            building_type="residential",
            height_class="特高",  # type: ignore[arg-type]
        )


def test_project_meta_rejects_negative_height() -> None:
    with pytest.raises(ValidationError):
        ProjectMeta(
            project_id="P-006",
            building_type="residential",
            height_class="多层",
            height_m=-1.0,
        )


def test_project_meta_rejects_zero_floors() -> None:
    with pytest.raises(ValidationError):
        ProjectMeta(
            project_id="P-007",
            building_type="residential",
            height_class="多层",
            floors=0,
        )
