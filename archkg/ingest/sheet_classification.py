"""Per-page sheet classification for multi-sheet PDF evidence routing."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field

from archkg.schemas import PagePrimitives, Primitives

SheetType = Literal["plan", "detail", "elevation", "schedule", "title", "legend", "unknown"]

PLAN_KEYWORDS = (
    "plan",
    "floor plan",
    "first floor",
    "second floor",
    "bedroom",
    "living",
    "corridor",
    "room",
    "平面",
)
SCHEDULE_KEYWORDS = ("schedule", "door schedule", "room schedule", "table", "mark width height", "表")
TITLE_KEYWORDS = ("title", "title sheet", "project data", "revision", "sheet index", "封面")
LEGEND_KEYWORDS = ("legend", "symbol", "abbrev", "abbreviation", "notes", "图例")
DETAIL_KEYWORDS = ("detail", "enlarged", "大样", "详图")
ELEVATION_KEYWORDS = ("elevation", "section", "立面", "剖面")


class SheetClassificationPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_index: int = Field(..., ge=0)
    sheet_type: SheetType
    confidence: float = Field(..., ge=0.0, le=1.0)
    eligible_for_graph: bool
    reason: str
    evidence_texts: list[str] = Field(default_factory=list)
    line_count: int = Field(..., ge=0)
    text_count: int = Field(..., ge=0)


class SheetClassificationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["sheet_classification.v1"] = "sheet_classification.v1"
    source_pdf: str
    summary: dict[SheetType, int]
    pages: list[SheetClassificationPage]


def build_sheet_classification(primitives: Primitives) -> SheetClassificationReport:
    pages = [_classify_page(page) for page in primitives.pages]
    counts: Counter[SheetType] = Counter(page.sheet_type for page in pages)
    return SheetClassificationReport(
        source_pdf=primitives.source_pdf,
        summary={sheet_type: counts[sheet_type] for sheet_type in sorted(counts)},
        pages=pages,
    )


def write_sheet_classification(
    report: SheetClassificationReport,
    out_path: Path,
) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return out_path


def _classify_page(page: PagePrimitives) -> SheetClassificationPage:
    texts = [_clean_text(text.text) for text in page.texts if text.text.strip()]
    haystack = " ".join(texts).lower()
    evidence_texts: list[str]

    keyword_scores = {
        "schedule": _score_keywords(haystack, SCHEDULE_KEYWORDS),
        "title": _score_keywords(haystack, TITLE_KEYWORDS),
        "legend": _score_keywords(haystack, LEGEND_KEYWORDS),
        "detail": _score_keywords(haystack, DETAIL_KEYWORDS),
        "elevation": _score_keywords(haystack, ELEVATION_KEYWORDS),
        "plan": _score_keywords(haystack, PLAN_KEYWORDS),
    }
    best_type = max(keyword_scores, key=lambda key: keyword_scores[key])
    best_score = keyword_scores[best_type]
    line_count = len(page.lines)
    text_count = len(page.texts)

    if best_score > 0:
        sheet_type = cast(SheetType, best_type)
        confidence = min(0.92, 0.55 + 0.12 * best_score)
        reason = f"classified from {best_score} keyword signal(s)"
        evidence_texts = _keyword_evidence(texts, _keywords_for(best_type))
    elif line_count >= 10 and text_count <= 8:
        sheet_type = "plan"
        confidence = 0.50
        reason = "line-dense page with limited text; treated as plan candidate"
        evidence_texts = texts[:4]
    else:
        sheet_type = "unknown"
        confidence = 0.20
        reason = "no reliable sheet-type signal"
        evidence_texts = texts[:4]

    return SheetClassificationPage(
        page_index=page.page_index,
        sheet_type=sheet_type,
        confidence=confidence,
        eligible_for_graph=sheet_type == "plan",
        reason=reason,
        evidence_texts=evidence_texts[:6],
        line_count=line_count,
        text_count=text_count,
    )


def _score_keywords(haystack: str, keywords: tuple[str, ...]) -> int:
    return sum(1 for keyword in keywords if keyword.lower() in haystack)


def _keywords_for(sheet_type: str) -> tuple[str, ...]:
    return {
        "schedule": SCHEDULE_KEYWORDS,
        "title": TITLE_KEYWORDS,
        "legend": LEGEND_KEYWORDS,
        "detail": DETAIL_KEYWORDS,
        "elevation": ELEVATION_KEYWORDS,
        "plan": PLAN_KEYWORDS,
    }.get(sheet_type, ())


def _keyword_evidence(texts: list[str], keywords: tuple[str, ...]) -> list[str]:
    out: list[str] = []
    lowered_keywords = tuple(keyword.lower() for keyword in keywords)
    for text in texts:
        lowered = text.lower()
        if any(keyword in lowered for keyword in lowered_keywords):
            out.append(text)
    return out or texts[:3]


def _clean_text(text: str) -> str:
    return " ".join(text.split())
