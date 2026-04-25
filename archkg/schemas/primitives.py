from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

BBox = tuple[float, float, float, float]
TextSource = Literal["vector", "ocr"]


class TextPrimitive(BaseModel):
    """A single text fragment lifted from the page (vector text block or OCR result)."""

    model_config = ConfigDict(extra="forbid")

    text: str
    bbox: BBox
    source: TextSource = "vector"
    confidence: float = Field(1.0, ge=0.0, le=1.0)


class LinePrimitive(BaseModel):
    model_config = ConfigDict(extra="forbid")

    p0: tuple[float, float]
    p1: tuple[float, float]


class PagePrimitives(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_index: int = Field(..., ge=0)
    width_pt: float
    height_pt: float
    lines: list[LinePrimitive] = Field(default_factory=list)
    texts: list[TextPrimitive] = Field(default_factory=list)


class Primitives(BaseModel):
    """Top-level container persisted as primitives.json."""

    model_config = ConfigDict(extra="forbid")

    source_pdf: str
    points_per_meter: float = Field(50.0, gt=0)
    pages: list[PagePrimitives]
