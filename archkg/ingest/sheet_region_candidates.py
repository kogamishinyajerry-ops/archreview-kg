"""Reviewable sheet-region candidate suggestions.

The detector is deliberately advisory. It writes candidate regions and
evidence, but callers must explicitly pass ``--sheet-region`` before any
candidate changes graph input.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from archkg.ingest.sheet_region import SheetRegion
from archkg.schemas import LinePrimitive, PagePrimitives, Primitives, TextPrimitive

CandidateKind = Literal["design_region", "title_block", "schedule", "legend"]

TITLE_KEYWORDS = (
    "title",
    "sheet",
    "project",
    "drawing",
    "revision",
    "rev",
    "date",
    "scale",
    "not for review",
)
SCHEDULE_KEYWORDS = ("schedule", "table", "row", "door schedule", "room schedule")
LEGEND_KEYWORDS = ("legend", "symbol", "abbrev", "abbreviation", "notes")


class SheetRegionEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str
    text: str | None = None
    bbox: SheetRegion | None = None


class SheetRegionCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: CandidateKind
    region: SheetRegion
    confidence: float = Field(..., ge=0.0, le=1.0)
    reason: str
    evidence: list[SheetRegionEvidence] = Field(default_factory=list)


class ExcludedTextSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    bbox: SheetRegion
    reason: str


class SheetRegionPageCandidates(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_index: int
    page_width_pt: float
    page_height_pt: float
    candidates: list[SheetRegionCandidate] = Field(default_factory=list)
    excluded_texts: list[ExcludedTextSummary] = Field(default_factory=list)


class SheetRegionCandidateReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["sheet_region_candidates.v1"] = "sheet_region_candidates.v1"
    source_pdf: str
    applied_region: SheetRegion | None = None
    pages: list[SheetRegionPageCandidates]


def build_sheet_region_candidates(
    primitives: Primitives,
    *,
    applied_region: SheetRegion | None = None,
) -> SheetRegionCandidateReport:
    return SheetRegionCandidateReport(
        source_pdf=primitives.source_pdf,
        applied_region=applied_region,
        pages=[
            _page_candidates(page)
            for page in primitives.pages
        ],
    )


def write_sheet_region_candidates(
    report: SheetRegionCandidateReport,
    out_path: Path,
) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return out_path


def _page_candidates(page: PagePrimitives) -> SheetRegionPageCandidates:
    title = _title_block_candidate(page)
    candidates: list[SheetRegionCandidate] = []
    design_region: SheetRegion
    if title is not None:
        design_x1 = max(0.0, title.region[0] - 8.0)
        design_region = (0.0, 0.0, design_x1, page.height_pt)
        candidates.append(
            SheetRegionCandidate(
                kind="design_region",
                region=design_region,
                confidence=0.82,
                reason="suggested design area excludes the detected right-side title/table block",
                evidence=[
                    SheetRegionEvidence(
                        reason="bounded by title_block candidate",
                        bbox=title.region,
                    )
                ],
            )
        )
        candidates.append(title)
    else:
        design_region = (0.0, 0.0, page.width_pt, page.height_pt)
        candidates.append(
            SheetRegionCandidate(
                kind="design_region",
                region=design_region,
                confidence=0.45,
                reason="no title block candidate found; full page retained as the design-region suggestion",
            )
        )

    schedule = _keyword_region_candidate(page, "schedule", SCHEDULE_KEYWORDS)
    if schedule is not None:
        candidates.append(schedule)
    legend = _keyword_region_candidate(page, "legend", LEGEND_KEYWORDS)
    if legend is not None:
        candidates.append(legend)

    excluded = [
        ExcludedTextSummary(
            text=text.text,
            bbox=text.bbox,
            reason="outside suggested design_region; candidate only, not cropped unless applied",
        )
        for text in page.texts
        if not _text_center_inside(text, design_region)
    ][:20]

    return SheetRegionPageCandidates(
        page_index=page.page_index,
        page_width_pt=page.width_pt,
        page_height_pt=page.height_pt,
        candidates=candidates,
        excluded_texts=excluded,
    )


def _title_block_candidate(page: PagePrimitives) -> SheetRegionCandidate | None:
    right_threshold = page.width_pt * 0.68
    right_texts = [
        text for text in page.texts if _text_center(text)[0] >= right_threshold
    ]
    keyword_texts = [
        text for text in right_texts if _contains_any(text.text, TITLE_KEYWORDS)
    ]
    if right_texts:
        text_min_x = min(text.bbox[0] for text in right_texts)
        line_threshold = max(right_threshold, text_min_x - 30.0)
    else:
        line_threshold = right_threshold
    right_lines = [
        line for line in page.lines
        if _line_midpoint(line)[0] >= line_threshold
    ]
    table_like = _table_like_score(right_lines)

    if len(keyword_texts) < 2 and (len(right_texts) < 4 or table_like < 3):
        return None

    region = _pad_region(
        _union_region(
            [text.bbox for text in right_texts]
            + [_line_bbox(line) for line in right_lines]
        ),
        page,
        pad=12.0,
    )
    confidence = min(
        0.95,
        0.42
        + 0.08 * len(keyword_texts)
        + 0.015 * len(right_lines)
        + 0.03 * min(table_like, 6),
    )
    evidence = [
        SheetRegionEvidence(
            reason="title keyword",
            text=text.text,
            bbox=text.bbox,
        )
        for text in keyword_texts[:8]
    ]
    if right_lines:
        evidence.append(
            SheetRegionEvidence(
                reason=f"right-side table/grid line cluster ({len(right_lines)} lines)",
                bbox=region,
            )
        )
    return SheetRegionCandidate(
        kind="title_block",
        region=region,
        confidence=confidence,
        reason="right-side dense text/table region with title-block keywords",
        evidence=evidence,
    )


def _keyword_region_candidate(
    page: PagePrimitives,
    kind: CandidateKind,
    keywords: tuple[str, ...],
) -> SheetRegionCandidate | None:
    texts = [text for text in page.texts if _contains_any(text.text, keywords)]
    if not texts:
        return None
    region = _pad_region(_union_region([text.bbox for text in texts]), page, pad=10.0)
    return SheetRegionCandidate(
        kind=kind,
        region=region,
        confidence=min(0.9, 0.58 + 0.06 * len(texts)),
        reason=f"detected {kind} keyword text cluster",
        evidence=[
            SheetRegionEvidence(reason=f"{kind} keyword", text=text.text, bbox=text.bbox)
            for text in texts[:8]
        ],
    )


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in keywords)


def _union_region(regions: Iterable[SheetRegion]) -> SheetRegion:
    xs0: list[float] = []
    ys0: list[float] = []
    xs1: list[float] = []
    ys1: list[float] = []
    for x0, y0, x1, y1 in regions:
        xs0.append(float(x0))
        ys0.append(float(y0))
        xs1.append(float(x1))
        ys1.append(float(y1))
    if not xs0:
        return (0.0, 0.0, 0.0, 0.0)
    return (min(xs0), min(ys0), max(xs1), max(ys1))


def _pad_region(region: SheetRegion, page: PagePrimitives, *, pad: float) -> SheetRegion:
    x0, y0, x1, y1 = region
    return (
        max(0.0, x0 - pad),
        max(0.0, y0 - pad),
        min(page.width_pt, x1 + pad),
        min(page.height_pt, y1 + pad),
    )


def _line_bbox(line: LinePrimitive) -> SheetRegion:
    return (
        min(line.p0[0], line.p1[0]),
        min(line.p0[1], line.p1[1]),
        max(line.p0[0], line.p1[0]),
        max(line.p0[1], line.p1[1]),
    )


def _line_midpoint(line: LinePrimitive) -> tuple[float, float]:
    return ((line.p0[0] + line.p1[0]) / 2.0, (line.p0[1] + line.p1[1]) / 2.0)


def _text_center(text: TextPrimitive) -> tuple[float, float]:
    x0, y0, x1, y1 = text.bbox
    return ((x0 + x1) / 2.0, (y0 + y1) / 2.0)


def _text_center_inside(text: TextPrimitive, region: SheetRegion) -> bool:
    x, y = _text_center(text)
    x0, y0, x1, y1 = region
    return x0 <= x <= x1 and y0 <= y <= y1


def _table_like_score(lines: list[LinePrimitive]) -> int:
    horizontal = 0
    vertical = 0
    for line in lines:
        dx = abs(line.p0[0] - line.p1[0])
        dy = abs(line.p0[1] - line.p1[1])
        if dx >= dy:
            horizontal += 1
        else:
            vertical += 1
    return min(horizontal, vertical)


__all__ = [
    "ExcludedTextSummary",
    "SheetRegionCandidate",
    "SheetRegionCandidateReport",
    "SheetRegionEvidence",
    "SheetRegionPageCandidates",
    "build_sheet_region_candidates",
    "write_sheet_region_candidates",
]
