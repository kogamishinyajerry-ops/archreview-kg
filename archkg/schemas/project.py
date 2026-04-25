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
    notes: str | None = None
