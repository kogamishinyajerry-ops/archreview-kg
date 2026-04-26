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
from shapely.geometry import LineString, Polygon
from shapely.geometry import Point as SPoint

from archkg.graph.geometry import (
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
    Stair,
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

# Codex P19-D R7 P1 (both findings): the right adjacency check is "does the
# polygon boundary CONTAIN the bridge segment?", not "is the polygon
# boundary close enough at any point" (a polygon touching only one
# bridge endpoint, or a parallel sliver within tol, would qualify
# under the loose check and falsely tag a real exterior door as
# anchored to noise). We require the bridge length to be substantially
# covered by the polygon's boundary buffer, then resolve which side
# the polygon's interior is on by stepping a tiny epsilon off the
# bridge midpoint along the signed normal — concave (L/U/C-shaped)
# polygons can have centroids outside the shape, so centroid-based
# side resolution is unsound.
BRIDGE_ADJACENCY_TOL_PT: float = 0.5
BRIDGE_COVERAGE_FRACTION: float = 0.5  # ≥ 50% of bridge must lie within boundary buffer
BRIDGE_LOCAL_STEP_PT: float = 0.5      # step off the bridge to test which side covers it


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
    # Phase 15: Stair iteration support. Default empty so older
    # entity_graph.json files (which never carried this key) keep loading.
    # The PDF builder pipeline does not yet detect stairs — entity-level
    # stair rules will fire when an upstream pass populates this list.
    stairs: list[Stair] = []


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


def _classify_door_side(
    point: tuple[float, float],
    rooms: list[Room],
    corridors: list[Corridor],
    filtered_polygons: list[Polygon],
) -> tuple[str, str | None]:
    """Classify which kind of polygon (if any) covers the door-side
    sample point.

    Returns ``(kind, id_or_None)`` where ``kind`` is one of:

    - ``"surviving"``: a kept room or corridor — return its id.
    - ``"filtered"``: a polygon rejected by ``min_room_area_m2`` — no
      id (filtered polygons aren't entities). Door touching this side
      is a wall break adjacent to noise and should be dropped.
    - ``"exterior"``: nothing covers the sample point. This is a true
      building-exterior side or an opening into a non-classified
      indoor region.

    Codex P19-D R3 P0: this three-way distinction is what lets the
    orphan-door filter tell a real entrance door (one side
    surviving, one side exterior) apart from a noise wall-break door
    (one side surviving, one side filtered). The pre-R3 code mapped
    both filtered and exterior to ``None`` and so couldn't
    distinguish them.
    """
    sp = SPoint(point)
    for r in rooms:
        if Polygon(r.polygon).covers(sp):
            return ("surviving", r.id)
    for c in corridors:
        if Polygon(c.polygon).covers(sp):
            return ("surviving", c.id)
    for fp in filtered_polygons:
        if fp.covers(sp):
            return ("filtered", None)
    return ("exterior", None)


def _classify_bridge_side(
    bridge_seg: tuple[tuple[float, float], tuple[float, float]],
    direction: int,
    rooms: list[Room],
    corridors: list[Corridor],
    filtered_polygons: list[Polygon],
) -> tuple[str, str | None]:
    """Identify which polygon (if any) the bridge segment is shared
    with on the given side.

    Adjacency: the bridge segment is substantially covered by the
    polygon's boundary (allowing :data:`BRIDGE_ADJACENCY_TOL_PT`
    fuzz). A polygon that only touches an endpoint, or sits within
    tol on a parallel sliver, fails this check.

    Side resolution: a small step off the bridge midpoint along the
    signed normal must land inside the polygon. This handles concave
    rooms whose centroids fall outside the polygon's enclosed area.

    Codex P19-D R7 P1 (both findings): pre-R7 used "boundary distance < tol" +
    centroid sign, which over-accepted endpoint-only adjacencies and
    misclassified sides for L/U/C-shaped polygons.
    """
    bridge_line = LineString(bridge_seg)
    bridge_length = bridge_line.length
    if bridge_length == 0:
        return ("exterior", None)
    (x0, y0), (x1, y1) = bridge_seg
    midpoint_x = (x0 + x1) / 2
    midpoint_y = (y0 + y1) / 2
    dx, dy = x1 - x0, y1 - y0
    nx = -dy / bridge_length * direction
    ny = dx / bridge_length * direction
    side_test_point = SPoint(
        midpoint_x + nx * BRIDGE_LOCAL_STEP_PT,
        midpoint_y + ny * BRIDGE_LOCAL_STEP_PT,
    )

    def _adjacent_to_this_side(polygon: Polygon) -> bool:
        # Coverage: at least BRIDGE_COVERAGE_FRACTION of the bridge
        # length must lie within the polygon-boundary buffer. This
        # rejects single-endpoint touches and parallel-sliver fuzz.
        boundary_buffer = polygon.boundary.buffer(BRIDGE_ADJACENCY_TOL_PT)
        shared = boundary_buffer.intersection(bridge_line)
        if shared.is_empty:
            return False
        shared_length = getattr(shared, "length", 0.0)
        if shared_length < bridge_length * BRIDGE_COVERAGE_FRACTION:
            return False
        # Side: the polygon's interior must contain (or touch) the
        # tiny offset point in the +normal direction. Concave polygons
        # are handled correctly because we check actual containment,
        # not centroid position.
        return bool(polygon.covers(side_test_point))

    for r in rooms:
        if _adjacent_to_this_side(Polygon(r.polygon)):
            return ("surviving", r.id)
    for c in corridors:
        if _adjacent_to_this_side(Polygon(c.polygon)):
            return ("surviving", c.id)
    for fp in filtered_polygons:
        if _adjacent_to_this_side(fp):
            return ("filtered", None)
    return ("exterior", None)


def _which_anchor(
    point: tuple[float, float],
    rooms: list[Room],
    corridors: list[Corridor],
) -> str | None:
    """Return the id of any room or corridor whose polygon covers the
    point, or None. Retained for backward compatibility with any
    downstream caller; the build_graph hot path uses
    :func:`_classify_door_side` instead.
    """
    kind, anchor_id = _classify_door_side(point, rooms, corridors, [])
    return anchor_id if kind == "surviving" else None


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


def build_graph(
    primitives: Primitives,
    *,
    min_room_area_m2: float = 0.0,
) -> EntityGraph:
    """MVP single-page graph builder.

    Phase 19-D: ``min_room_area_m2`` is an optional noise filter for
    real CAD PDFs. Polygons that pass the polygonize floor (~0.25 m²)
    but are still smaller than the threshold are dropped from the room
    list. Default 0.0 (no filtering) preserves backward-compat with the
    synthetic samples and existing CLI behaviour; the studio passes a
    non-zero default so first-time real-PDF uploads aren't drowned in
    sub-1 m² fixture / dim-box / window-frame outlines.
    """
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
    # Codex P19-D R3 P0: track polygons rejected by the area floor
    # so the door classifier can tell "wall break adjacent to filtered
    # noise" apart from "wall break to true exterior". Without this,
    # the orphan-door filter would either keep noise doors (current
    # bug) or kill real entrance doors (the alternative naive fix).
    filtered_polygons: list[Polygon] = []

    for poly in polygons:
        bbox, polygon_pts, area_m2 = _polygon_to_bbox_polygon_m(poly, ppm)
        short_m = _short_side_m(poly, ppm)
        aspect = _aspect_ratio(poly)
        is_corridor_shaped = (
            aspect >= CORRIDOR_ASPECT_MIN
            and CORRIDOR_SHORT_MIN_M <= short_m <= CORRIDOR_SHORT_MAX_M
        )

        # Phase 19-D noise filter: drop sub-threshold polygons before
        # they become rooms or corridors. Real Chinese residential
        # rooms are >=4 m²; window frames / dim boxes / fixture
        # outlines are typically 0.3-0.8 m². 1.0 m² is conservative.
        # Long-thin scraps that satisfy the corridor aspect test get
        # the same floor (Codex R2 P2): real corridors are >=3 m².
        if min_room_area_m2 > 0.0 and area_m2 < min_room_area_m2:
            filtered_polygons.append(poly)
            continue

        if is_corridor_shaped:
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

    # Door creation with three-way side classification (Codex R3 P0,
    # robustified per R6 P1). Each bridge's two sides are classified
    # as one of:
    #   - "surviving": polygon adjacent to the bridge boundary,
    #                  classified as a kept room/corridor.
    #   - "filtered":  polygon adjacent to the bridge boundary, but
    #                  rejected by ``min_room_area_m2``.
    #   - "exterior":  no polygon adjacent on this side.
    # A door is kept iff no side is "filtered" and at least one side
    # is "surviving" (real exterior doors satisfy "surviving + exterior";
    # noise doors fail because at least one side is "filtered"; both-
    # exterior bridges are degenerate and dropped to be safe).
    # When the filter is off (min_room_area_m2 == 0.0), filtered_polygons
    # is empty so the "filtered" verdict is unreachable → all doors are
    # kept, preserving the pre-19-D backward-compat path.
    doors: list[Door] = []
    for bridge in bridges:
        width_m = bridge.width_pt / ppm
        (x0, y0), (x1, y1) = bridge.segment
        bbox = (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
        a_kind, a_id = _classify_bridge_side(
            bridge.segment, -1, rooms, corridors, filtered_polygons
        )
        b_kind, b_id = _classify_bridge_side(
            bridge.segment, +1, rooms, corridors, filtered_polygons
        )

        if min_room_area_m2 > 0.0:
            if a_kind == "filtered" or b_kind == "filtered":
                continue
            if a_kind != "surviving" and b_kind != "surviving":
                continue

        confidence = 0.85 if (a_id and b_id) else 0.5
        doors.append(
            Door(
                id=_new_id("door"),
                page_index=page_index,
                bbox=bbox,
                width_m=width_m,
                connects=(a_id, b_id),
                confidence=confidence,
                uncertain=confidence < 0.6,
            )
        )

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
