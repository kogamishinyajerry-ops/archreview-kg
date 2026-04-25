from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

BBox = tuple[float, float, float, float]


class _EntityBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    page_index: int = Field(..., ge=0)
    bbox: BBox
    confidence: float = Field(1.0, ge=0.0, le=1.0)
    uncertain: bool = False
    properties: dict[str, float | int | str | bool] = Field(default_factory=dict)


class Room(_EntityBase):
    type: Literal["Room"] = "Room"
    polygon: list[tuple[float, float]] = Field(..., min_length=3)
    area_m2: float | None = None
    label: str | None = None


class Door(_EntityBase):
    type: Literal["Door"] = "Door"
    width_m: float | None = None
    connects: tuple[str | None, str | None] = (None, None)


class Wall(_EntityBase):
    type: Literal["Wall"] = "Wall"
    p0: tuple[float, float]
    p1: tuple[float, float]
    thickness_m: float | None = None


class Corridor(_EntityBase):
    type: Literal["Corridor"] = "Corridor"
    polygon: list[tuple[float, float]] = Field(..., min_length=3)
    min_width_m: float | None = None


class Dimension(_EntityBase):
    type: Literal["Dimension"] = "Dimension"
    text: str
    value_m: float | None = None
    unit: str | None = None


class Stair(_EntityBase):
    type: Literal["Stair"] = "Stair"
    tread_width_m: float | None = None
    riser_height_m: float | None = None


Entity = Annotated[
    Room | Door | Wall | Corridor | Dimension | Stair,
    Field(discriminator="type"),
]
