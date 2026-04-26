"""ProjectMeta — the project-level context that drives rule applicability.

Phase 9: rules whose source clauses don't match the project's building_type
or height_class are *skipped* rather than fired-and-failed. The review
report explicitly lists what was skipped and why so reviewers don't think
the engine forgot something.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from archkg.schemas.standard import BuildingType, HeightClass

FireClass = Literal["一级", "二级", "三级", "四级"]
ClimateZone = Literal["严寒", "寒冷", "夏热冬冷", "夏热冬暖", "温和"]


class ProjectMeta(BaseModel):
    """Project context for rule-applicability filtering.

    `building_type` and `height_class` are required because they drive the
    most important applicability gates (residential-only, 高层-only, etc.).
    Other fields are optional and reserved for Phase 11+ rules that need
    them (energy / fire-class / climate-zone gated rules).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    project_id: str = Field(..., min_length=1)
    project_name: str | None = None
    building_type: BuildingType
    height_class: HeightClass
    fire_class: FireClass | None = None
    climate_zone: ClimateZone | None = None
    use_type: str | None = Field(None, description="Specific use, e.g. '住宅' / '公寓' / '宿舍'.")
    height_m: float | None = Field(None, gt=0.0, description="Building height in metres.")
    floors: int | None = Field(None, ge=1)
    # Phase 17: residential housing unit accounting for GB 50763-7.4.3
    # (无障碍住房比例: 每 100 套 ≥2 套). Both fields optional — projects
    # without an accessibility plan won't carry these numbers, and the
    # rule short-circuits to a reminder rather than failing on None.
    total_units: int | None = Field(
        None,
        ge=1,
        description="Total residential housing unit count (套数). Drives GB 50763-7.4.3.",
    )
    accessible_units: int | None = Field(
        None,
        ge=0,
        description="Count of units designed as 无障碍住房. Compared against total_units * 0.02.",
    )
    notes: str | None = None
