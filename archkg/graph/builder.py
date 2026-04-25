"""Entity-graph builder.

Pipeline (per page, MVP supports a single page):
  primitives.json
    -> bridge door gaps in the line network
    -> polygonize -> polygons (rooms / corridor candidates)
    -> classify each polygon (corridor vs room) by aspect ratio + short side
    -> bind text labels to rooms (point-in-polygon on text centers)
    -> bind dimension texts to nearest entity
    -> emit EntityGraph

ASSUMPTIONS (clearly bounded by Scope Freeze v0.1):
- All walls are axis-aligned (true for the synthetic sample; real CAD plans
  often are not — flagged in README and acceptable for MVP).
- Corridors are detected as polygons with aspect ratio >= 3 and short side
  between 0.5 m and 2.0 m. Anything else is a Room.
- Door candidates come from bridge segments produced when closing collinear
  wall gaps; their width is the gap length in meters.
- Room labels use exact substring match against {bedroom, bathroom, living,
  kitchen, balcony, study, dining, kids}.
- Dimension binding: regex pulls `\\d+(\\.\\d+)?` out of the text; nearest
  entity by centroid distance, capped at 1 m.
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict
from shapely.geometry import Point as SPoint
from shapely.geometry import Polygon

from archkg.graph.geometry import (
    GapBridge,
    bridge_door_gaps,
    polygonize_segments,
)
from archkg.schemas import (
    Corridor,
    Dimension,
    Door,
    PagePrimitives,
    Primitives,
    Room,
    TextPrimitive,
)

LABEL_KEYWORDS = {
    "bedroom": "bedroom",
    "卧室": "bedroom",
    "bathroom": "bathroom",
    "卫生间": "bathroom",
    "living": "living",
    "客厅": "living",
    "kitchen": "kitchen",
    "厨房": "kitchen",
    "balcony": "balcony",
    "阳台": "balcony",
    "study": "study",
    "书房": "study",
    "dining": "dining",
    "餐厅": "dining",
    "kids": "kids",
    "儿童房": "kids",
}

# Pull the first numeric value from text like "DOOR 0.85", "1.05 m", "1200 mm", "净宽1.2".
DIM_VALUE_RE = re.compile(r"(\d+(?:\.\d+)?)")
DOOR_KEYWORDS = ("door", "门")
CORRIDOR_KEYWORDS = ("corridor", "走廊", "通廊")

# Door-gap detection: 0.70-1.00 m. Tight upper bound on purpose so it doesn't
# bridge through a 1.05-m-wide corridor opening on the same wall axis.
DOOR_MIN_M = 0.70
DOOR_MAX_M = 1.00

CORRIDOR_ASPECT_MIN = 3.0
CORRIDOR_SHORT_MIN_M = 0.5
CORRIDOR_SHORT_MAX_M = 2.0


class EntityGraph(BaseModel):
    """Top-level entity_graph.json container — explicit per-type lists for easy consumption."""

    model_config = ConfigDict(extra="forbid")

    source_pdf: str
    points_per_meter: float
    page_index: int
    page_width_pt: float
    page_height_pt: float
    rooms: list[Room]
    doors: list[Door]
    corridors: list[Corridor]
    dimensions: list[Dimension]


# ---------- helpers ----------


def _centroid(t: TextPrimitive) -> tuple[float, float]:
    x0, y0, x1, y1 = t.bbox
    return ((x0 + x1) / 2, (y0 + y1) / 2)


def _polygon_to_bbox_polygon_m(poly: Polygon, ppm: float) -> tuple[
    tuple[float, float, float, float],
    list[tuple[float, float]],
    float,
]:
    minx, miny, maxx, maxy = poly.bounds
    bbox = (minx, miny, maxx, maxy)
    polygon_pts = [(float(x), float(y)) for x, y in poly.exterior.coords]
    area_m2 = poly.area / (ppm * ppm)
    return bbox, polygon_pts, area_m2


def _short_side_m(poly: Polygon, ppm: float) -> float:
    minx, miny, maxx, maxy = poly.bounds
    return float(min(maxx - minx, maxy - miny)) / ppm


def _aspect_ratio(poly: Polygon) -> float:
    minx, miny, maxx, maxy = poly.bounds
    w, h = float(maxx - minx), float(maxy - miny)
    if min(w, h) <= 0:
        return float("inf")
    return max(w, h) / min(w, h)


def _classify_label(text: str) -> str | None:
    lo = text.lower()
    for kw, normalized in LABEL_KEYWORDS.items():
        if kw in lo:
            return normalized
    return None


def _bind_label_to_room(poly: Polygon, texts: list[TextPrimitive]) -> tuple[str | None, str | None]:
    for t in texts:
        cx, cy = _centroid(t)
        if poly.covers(SPoint(cx, cy)):
            normalized = _classify_label(t.text)
            if normalized is not None:
                return normalized, t.text
    return None, None


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _door_from_bridge(
    bridge: GapBridge,
    page_index: int,
    ppm: float,
    rooms: list[Room],
) -> Door:
    width_m = bridge.width_pt / ppm
    (x0, y0), (x1, y1) = bridge.segment
    bbox = (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
    # Find rooms on either side of the door by sampling perpendicular points.
    mx, my = (x0 + x1) / 2, (y0 + y1) / 2
    if bridge.axis == "h":
        offset = (0.0, ppm * 0.3)
    else:
        offset = (ppm * 0.3, 0.0)
    side_a = (mx - offset[0], my - offset[1])
    side_b = (mx + offset[0], my + offset[1])
    a_id = _which_room(side_a, rooms)
    b_id = _which_room(side_b, rooms)
    confidence = 0.85 if (a_id and b_id) else 0.5
    return Door(
        id=_new_id("door"),
        page_index=page_index,
        bbox=bbox,
        width_m=width_m,
        connects=(a_id, b_id),
        confidence=confidence,
        uncertain=confidence < 0.6,
    )


def _which_room(point: tuple[float, float], rooms: list[Room]) -> str | None:
    sp = SPoint(point)
    for r in rooms:
        poly = Polygon(r.polygon)
        if poly.covers(sp):
            return r.id
    return None


def _bind_dimensions_to_entities(
    texts: list[TextPrimitive],
    page_index: int,
    rooms: list[Room],
    doors: list[Door],
    corridors: list[Corridor],
    ppm: float,
) -> tuple[list[Dimension], list[Door], list[Corridor]]:
    """Match dimension texts to the nearest applicable entity by centroid distance,
    cap 1.0 m. Mutates door.width_m / corridor.min_width_m when stronger evidence
    (explicit text dimension) overrides geometry-derived values.
    """
    dims: list[Dimension] = []
    door_lookup = {d.id: d for d in doors}
    corridor_lookup = {c.id: c for c in corridors}
    cap_pt = 1.0 * ppm

    for t in texts:
        m = DIM_VALUE_RE.search(t.text)
        if not m:
            continue
        value_m = float(m.group(1))
        # Heuristic unit detection: values >= 100 are mm, else m.
        if value_m >= 100:
            value_m = value_m / 1000.0
        cx, cy = _centroid(t)

        target_kind: str | None = None
        target_id: str | None = None
        best_dist = cap_pt
        lo = t.text.lower()
        prefer_door = any(k in lo for k in DOOR_KEYWORDS)
        prefer_corridor = any(k in lo for k in CORRIDOR_KEYWORDS)

        candidates: list[tuple[str, str, tuple[float, float]]] = []
        if prefer_corridor or not prefer_door:
            for c in corridors:
                bx0, by0, bx1, by1 = c.bbox
                candidates.append(("corridor", c.id, ((bx0 + bx1) / 2, (by0 + by1) / 2)))
        if prefer_door or not prefer_corridor:
            for d in doors:
                bx0, by0, bx1, by1 = d.bbox
                candidates.append(("door", d.id, ((bx0 + bx1) / 2, (by0 + by1) / 2)))

        for kind, eid, (ex, ey) in candidates:
            dist = ((cx - ex) ** 2 + (cy - ey) ** 2) ** 0.5
            if dist < best_dist:
                best_dist = dist
                target_kind = kind
                target_id = eid

        if target_kind == "door" and target_id is not None:
            door_lookup[target_id].width_m = value_m
        elif target_kind == "corridor" and target_id is not None:
            corridor_lookup[target_id].min_width_m = value_m

        dims.append(
            Dimension(
                id=_new_id("dim"),
                page_index=page_index,
                bbox=t.bbox,
                text=t.text,
                value_m=value_m,
                unit="m",
                confidence=t.confidence,
            )
        )

    return dims, list(door_lookup.values()), list(corridor_lookup.values())


# ---------- main entry ----------


def build_graph(primitives: Primitives) -> EntityGraph:
    """MVP single-page graph builder."""
    if not primitives.pages:
        raise ValueError("primitives has no pages")
    page: PagePrimitives = primitives.pages[0]
    ppm = primitives.points_per_meter
    page_index = page.page_index

    raw_segments = [(seg.p0, seg.p1) for seg in page.lines]
    augmented, bridges = bridge_door_gaps(
        raw_segments,
        max_gap_pt=DOOR_MAX_M * ppm,
        min_gap_pt=DOOR_MIN_M * ppm,
    )
    polygons = polygonize_segments(augmented, min_area_pt2=(0.5 * ppm) ** 2)

    rooms: list[Room] = []
    corridors: list[Corridor] = []

    for poly in polygons:
        bbox, polygon_pts, area_m2 = _polygon_to_bbox_polygon_m(poly, ppm)
        short_m = _short_side_m(poly, ppm)
        aspect = _aspect_ratio(poly)

        if (
            aspect >= CORRIDOR_ASPECT_MIN
            and CORRIDOR_SHORT_MIN_M <= short_m <= CORRIDOR_SHORT_MAX_M
        ):
            corridors.append(
                Corridor(
                    id=_new_id("corridor"),
                    page_index=page_index,
                    bbox=bbox,
                    polygon=polygon_pts,
                    min_width_m=short_m,
                    confidence=0.8,
                    uncertain=False,
                )
            )
        else:
            label, _label_src = _bind_label_to_room(poly, page.texts)
            confidence = 0.85 if label else 0.6
            rooms.append(
                Room(
                    id=_new_id("room"),
                    page_index=page_index,
                    bbox=bbox,
                    polygon=polygon_pts,
                    area_m2=area_m2,
                    label=label,
                    confidence=confidence,
                    uncertain=label is None,
                )
            )

    doors = [
        _door_from_bridge(b, page_index, ppm, rooms)
        for b in bridges
    ]

    dimensions, doors, corridors = _bind_dimensions_to_entities(
        page.texts, page_index, rooms, doors, corridors, ppm
    )

    return EntityGraph(
        source_pdf=primitives.source_pdf,
        points_per_meter=ppm,
        page_index=page_index,
        page_width_pt=page.width_pt,
        page_height_pt=page.height_pt,
        rooms=rooms,
        doors=doors,
        corridors=corridors,
        dimensions=dimensions,
    )


def write_json(graph: EntityGraph, out_path: Path) -> Path:
    import json

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(graph.model_dump(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return out_path


def render_overlay(
    graph: EntityGraph,
    pdf_path: Path,
    out_png: Path,
    *,
    dpi: int = 144,
) -> Path:
    """Render the source PDF with colored entity overlays for human spot-checks."""
    import fitz
    from PIL import Image, ImageDraw, ImageFont

    doc = fitz.open(str(pdf_path))
    try:
        page = doc[graph.page_index]
        zoom = dpi / 72.0
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples).convert("RGBA")
    finally:
        doc.close()

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font: Any
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 13)
    except OSError:
        font = ImageFont.load_default()

    def _scale(b: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
        return (b[0] * zoom, b[1] * zoom, b[2] * zoom, b[3] * zoom)

    def _badge(xy: tuple[float, float], text: str, fg: tuple[int, int, int, int]) -> None:
        x, y = xy
        bbox = draw.textbbox((x, y), text, font=font)
        pad = 2
        draw.rectangle(
            (bbox[0] - pad, bbox[1] - pad, bbox[2] + pad, bbox[3] + pad),
            fill=(255, 255, 255, 230),
            outline=fg,
            width=1,
        )
        draw.text((x, y), text, fill=fg, font=font)

    for r in graph.rooms:
        rect = _scale(r.bbox)
        draw.rectangle(rect, outline=(0, 128, 255, 220), width=2)
        label_text = (
            f"Room  {r.label or '?'}  {r.area_m2:.1f} m²"
            if r.area_m2 is not None
            else f"Room  {r.label or '?'}"
        )
        _badge((rect[0] + 6, rect[1] + 6), label_text, (0, 128, 255, 255))
    for c in graph.corridors:
        rect = _scale(c.bbox)
        draw.rectangle(rect, outline=(255, 128, 0, 220), width=2)
        if c.min_width_m is not None:
            _badge((rect[0] + 6, rect[1] + 6),
                   f"Corridor  w = {c.min_width_m:.2f} m",
                   (200, 90, 0, 255))
    for d in graph.doors:
        rect = _scale(d.bbox)
        draw.rectangle(rect, outline=(220, 30, 30, 240), width=3)
        if d.width_m is not None:
            _badge((rect[0], max(rect[1] - 18, 2)),
                   f"Door {d.width_m:.2f} m",
                   (200, 0, 0, 255))

    composed = Image.alpha_composite(img, overlay).convert("RGB")
    out_png.parent.mkdir(parents=True, exist_ok=True)
    composed.save(out_png)
    return out_png


__all__: tuple[str, ...] = (
    "EntityGraph",
    "build_graph",
    "render_overlay",
    "write_json",
)
