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
from shapely.geometry import box as sbox

from archkg.graph.geometry import (
    bridge_door_gaps,
    is_vertical,
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

# Trunk-corridor carve (corridor-extraction milestone part 2, round-7 R7-BUG-003).
# A long circulation corridor's bounding wall can contain an opening WIDER than
# even the wide-opening repair closes (m16/m15 page-1: a 74pt/1.48m gap exceeding
# WIDE_GAP_MAX_PT). The wall stays open, so polygonize floods the corridor strip
# into the adjacent room band and no thin corridor polygon ever forms. This pass
# recovers it WITHOUT widening any bridge ceiling (which re-merges rooms across
# legitimate doorways and re-introduces phantom corridors — measured): it detects
# the corridor directly from its defining geometry — two long, mostly-covered
# parallel wall chords a corridor-width apart — and carves that band out of the
# flooded host room, measuring width from the chord gap (robust to the unclosed
# wall, so it reports the TRUE ~1.10m, not the flooded polygon's short side).
# Three discriminators keep it FP-neutral on the cambridge / m10-m14 control set
# (each verified load-bearing by ablation): the band must sit INSIDE a polygonized
# room (the flooded host), leave a real room remnant on BOTH sides (rejects bands
# glued to a room edge, e.g. m14), and have NO interior vertical crossing it
# (rejects furniture/fixture clusters chopped into cells, e.g. m13). The width
# window reuses the corridor classifier's CORRIDOR_SHORT_MIN_M..MAX_M (NOT a
# fixture-centered window — verified that widening it to the full corridor band
# changes nothing on any control plan, so the discriminators, not the width, carry
# FP-control). See .planning/m16/CORRIDOR_EXTRACTION_MILESTONE.md.
TRUNK_CARVE_SPAN_FRAC = 0.5          # a wall chord must span >= this fraction of the page width
TRUNK_CARVE_FILL_FRAC = 0.5          # covered length / span of the chord (tolerates the unclosed opening)
TRUNK_CARVE_OVERLAP_FRAC = 0.5       # x-overlap of the two chords vs the wider chord's span
TRUNK_CARVE_REMNANT_MIN_M = 0.5      # min room remnant ABOVE and BELOW the band
TRUNK_CARVE_CROSS_FRAC = 0.6         # a vertical covering >= this frac of band height "crosses" it
TRUNK_CARVE_CROSS_EDGE_MARGIN_PT = 20.0  # ignore verticals within this of the band x-edges (room end-walls)
TRUNK_CARVE_Y_TOL = 3.0              # collinearity tolerance when clustering horizontal chords

# Host-band carve (corridor-extraction milestone part 3, R7-BUG-003). The part-2
# carve above uses a PAGE-relative span gate (a chord must span >= half the sheet),
# which misses a *split* trunk corridor whose halves each span only ~40% of the
# page (m13 west/east, divided by a real elevator-lobby wall; m14's single full
# band is missed instead on the remnant gate). This additive second pass re-scopes
# the same chord-pair detection to the INTERIOR of a large flooded host room, so a
# half that spans most of *its host* (but <50% of the page) qualifies. It runs
# AFTER the part-2 carve and skips bands already covered by an existing corridor,
# so m15/m16's part-2 trunk is preserved byte-for-byte. The decisive anti-phantom
# gate is HOST_CARVE_OPEN_FRAC: the carved strip must be a genuinely OPEN area
# inside the host polygon (not a thin edge sliver of an irregular room) — without
# it a 62.9 m² cambridge-343medford room carves a degenerate phantom. Calibrated +
# verified FP-clean on the cambridge / m10-m12 control set; see
# .planning/CORPUS_RECALL_DECOMPOSITION.md (the m13/m14 trunk-corridor cluster).
HOST_CARVE_MIN_AREA_M2 = 30.0        # only generalize inside a large flooded host room
HOST_CARVE_CHORD_EXTENT_FRAC = 0.70  # a host-clipped wall chord must span >= this fraction of host width
HOST_CARVE_CHORD_COVER_FRAC = 0.80   # covered length / extent of the host-clipped chord
HOST_CARVE_ASPECT_MIN = 3.0          # carved strip length / width >= this (a tube, not a blob)
HOST_CARVE_OPEN_FRAC = 0.60          # strip ∩ host area >= this * strip area (genuinely open band, not a sliver)
HOST_CARVE_OVERLAP_FRAC = 0.30       # skip if strip overlaps an existing corridor by > this * strip area
HOST_CARVE_CROSS_EDGE_MARGIN_PT = 25.0  # crossing-test edge margin for host end-walls / lobby walls

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


# Round-7 R7-BUG-001/003: a drawing's border frame / legend strip / full-width
# title band gets polygonized into a long thin rectangle that passes the
# corridor shape test (aspect >= 3, short side 0.5-2.0 m) and then fires
# RC-CORRIDOR-WIDTH as a phantom. The discriminator vs a REAL corridor is
# position, not shape: an artifact band spans almost the whole SHEET (margins +
# title block included) AND hugs a sheet edge, whereas a circulation corridor —
# even a full-width one that splits the plan — sits well inside the margin with
# rooms on both long sides. Both gates are required so an interior full-width
# corridor (e.g. the synthetic sample's mid-page corridor at 100% width) is
# never dropped. Conservative by construction: ambiguous cases keep the corridor.
SHEET_BAND_SPAN_FRAC = 0.85
SHEET_BAND_EDGE_FRAC = 0.05


def _is_sheet_edge_band(
    bbox: tuple[float, float, float, float],
    page_w: float,
    page_h: float,
    *,
    span_frac: float = SHEET_BAND_SPAN_FRAC,
    edge_frac: float = SHEET_BAND_EDGE_FRAC,
) -> bool:
    """True if ``bbox`` (page points) is a sheet-spanning band hugging an edge —
    i.e. a border / legend / title strip, not a circulation corridor."""
    x0, y0, x1, y1 = bbox
    if page_w <= 0 or page_h <= 0:
        return False
    # Horizontal band spanning the sheet width, flush to the top or bottom edge.
    if (x1 - x0) >= span_frac * page_w and (
        y0 <= edge_frac * page_h or (page_h - y1) <= edge_frac * page_h
    ):
        return True
    # Vertical band spanning the sheet height, flush to the left or right edge.
    if (y1 - y0) >= span_frac * page_h and (
        x0 <= edge_frac * page_w or (page_w - x1) <= edge_frac * page_w
    ):
        return True
    return False


def _merge_intervals(
    intervals: list[tuple[float, float]], *, gap_tol: float = 0.5
) -> list[list[float]]:
    """Merge overlapping or touching ``[start, end]`` intervals."""
    merged: list[list[float]] = []
    for a, b in sorted(intervals):
        if merged and a <= merged[-1][1] + gap_tol:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    return merged


def _long_horizontal_chords(
    segments: list[tuple[tuple[float, float], tuple[float, float]]],
    page_w: float,
) -> list[tuple[float, float, float, float]]:
    """Cluster horizontal segments into wall-chord levels and keep the long,
    mostly-covered ones — i.e. building walls that span most of the sheet width.

    Returns ``[(y, x_min, x_max, span), ...]`` sorted by y. The fill fraction is
    measured over the merged coverage so a chord with a single wide doorway (the
    unclosed corridor opening) still qualifies.
    """
    items: list[tuple[float, float, float]] = []
    for (x0, y0), (x1, y1) in segments:
        if abs(y0 - y1) <= TRUNK_CARVE_Y_TOL:
            items.append(((y0 + y1) / 2.0, min(x0, x1), max(x0, x1)))
    items.sort()
    levels: list[tuple[float, list[tuple[float, float]]]] = []
    for yc, x0, x1 in items:
        for level_y, ivs in levels:
            if abs(level_y - yc) <= TRUNK_CARVE_Y_TOL:
                ivs.append((x0, x1))
                break
        else:
            levels.append((yc, [(x0, x1)]))
    chords: list[tuple[float, float, float, float]] = []
    for yc, ivs in levels:
        merged = _merge_intervals(ivs)
        x_min = min(a for a, _ in merged)
        x_max = max(b for _, b in merged)
        span = x_max - x_min
        covered = sum(b - a for a, b in merged)
        if span > 0 and span >= TRUNK_CARVE_SPAN_FRAC * page_w and covered >= TRUNK_CARVE_FILL_FRAC * span:
            chords.append((yc, x_min, x_max, span))
    chords.sort()
    return chords


def _band_has_crossing_vertical(
    segments: list[tuple[tuple[float, float], tuple[float, float]]],
    x0: float,
    x1: float,
    y_lo: float,
    y_hi: float,
    *,
    edge_margin_pt: float = TRUNK_CARVE_CROSS_EDGE_MARGIN_PT,
) -> bool:
    """True if an interior vertical segment crosses >= ``TRUNK_CARVE_CROSS_FRAC``
    of the band height. Verticals within ``edge_margin_pt`` of the band x-edges are
    ignored — those are the room's own end-walls. A genuine interior crossing means
    the band is chopped into cells (furniture / fixtures), not an open traversable
    corridor tube.
    """
    need = TRUNK_CARVE_CROSS_FRAC * (y_hi - y_lo)
    for seg in segments:
        if not is_vertical(seg):
            continue
        (sx0, sy0), (sx1, sy1) = seg
        xc = (sx0 + sx1) / 2.0
        if not (x0 + edge_margin_pt < xc < x1 - edge_margin_pt):
            continue
        sy_lo, sy_hi = min(sy0, sy1), max(sy0, sy1)
        if min(sy_hi, y_hi) - max(sy_lo, y_lo) >= need:
            return True
    return False


def _carve_trunk_corridors(
    rooms: list[Room],
    corridors: list[Corridor],
    doors: list[Door],
    augmented: list[tuple[tuple[float, float], tuple[float, float]]],
    page: PagePrimitives,
    ppm: float,
    page_index: int,
    min_room_area_m2: float,
) -> tuple[list[Room], list[Corridor], list[Door]]:
    """Recover a corridor that ``polygonize`` failed to isolate because its long
    bounding wall has an opening wider than any bridge closes, so the corridor
    strip floods into the room band. See the ``TRUNK_CARVE_*`` constants for the
    geometry and the FP-control discriminators.

    Returns updated ``(rooms, corridors, doors)``. Pure on plans with no flooded
    trunk corridor (every control plan in the regression set): no chord pair
    passes all three discriminators, so the inputs are returned unchanged.
    """
    chords = _long_horizontal_chords(augmented, page.width_pt)
    if len(chords) < 2:
        return rooms, corridors, doors

    w_min = CORRIDOR_SHORT_MIN_M * ppm
    w_max = CORRIDOR_SHORT_MAX_M * ppm
    remnant_min_pt = TRUNK_CARVE_REMNANT_MIN_M * ppm
    # Remnant area floor mirrors build_graph's two-tier room filter: the
    # polygonize floor (~0.25 m²) plus the caller's min_room_area_m2. Drops the
    # thin slivers a difference() can shed at the band edges.
    area_floor_pt2 = max((0.5 * ppm) ** 2, min_room_area_m2 * ppm * ppm)

    new_corridors: list[Corridor] = []
    remnant_rooms: list[Room] = []
    removed_room_ids: set[str] = set()

    for i in range(len(chords)):
        for j in range(i + 1, len(chords)):
            y_a, xa0, xa1, span_a = chords[i]
            y_b, xb0, xb1, span_b = chords[j]
            dy = abs(y_b - y_a)
            if not (w_min <= dy <= w_max):
                continue
            ox0 = max(xa0, xb0)
            ox1 = min(xa1, xb1)
            overlap = ox1 - ox0
            if overlap <= 0 or overlap < TRUNK_CARVE_OVERLAP_FRAC * max(span_a, span_b):
                continue
            y_lo, y_hi = min(y_a, y_b), max(y_a, y_b)
            center = SPoint((ox0 + ox1) / 2.0, (y_lo + y_hi) / 2.0)

            # GATE 1: the band must sit inside a polygonized room — the flooded
            # host the corridor strip merged into. A band over open sheet (no host)
            # is a margin artifact, not a corridor.
            host: Room | None = None
            host_poly: Polygon | None = None
            for room in rooms:
                if room.id in removed_room_ids:
                    continue
                try:
                    candidate = Polygon(room.polygon)
                    if candidate.contains(center):
                        host = room
                        host_poly = candidate
                        break
                except (ValueError, TypeError):
                    continue
            if host is None or host_poly is None:
                continue

            hx0, hy0, hx1, hy1 = host.bbox
            # GATE 2: a real room remnant on BOTH sides of the band. A band glued
            # to the host's top or bottom wall (m14: remnant above == 0) is an edge
            # feature, not a corridor flanked by rooms.
            if (y_lo - hy0) < remnant_min_pt or (hy1 - y_hi) < remnant_min_pt:
                continue
            # GATE 3: no interior vertical crossing the band (m13: 3 verticals chop
            # its band into furniture cells; a real corridor tube has none).
            if _band_has_crossing_vertical(augmented, ox0, ox1, y_lo, y_hi):
                continue

            cx0, cx1 = max(ox0, hx0), min(ox1, hx1)
            corridor_box = sbox(cx0, y_lo, cx1, y_hi)
            new_corridors.append(
                Corridor(
                    id=_new_id("corridor"),
                    page_index=page_index,
                    bbox=(cx0, y_lo, cx1, y_hi),
                    polygon=[(cx0, y_lo), (cx1, y_lo), (cx1, y_hi), (cx0, y_hi), (cx0, y_lo)],
                    min_width_m=round(dy / ppm, 2),
                    confidence=0.75,
                    uncertain=False,
                )
            )
            # Replace the host with its remainder MINUS the carved band, using the
            # host's TRUE (irregular) polygon — NOT its bounding box, which would
            # blanket and overlap the sibling rooms polygonize already found around
            # the flood (a real defect: the bbox remnants over-reported area by ~2.6x
            # and created ~155 m^2 of room overlap on m16). The host is a mis-merge
            # artifact, so its label is not reliably attributable to either side:
            # drop it (a flooded mega-room is never a real labelled room that should
            # drive a room-area verdict).
            removed_room_ids.add(host.id)
            remainder = host_poly.difference(corridor_box)
            for part in getattr(remainder, "geoms", [remainder]):
                if part.is_empty or part.geom_type != "Polygon" or part.area < area_floor_pt2:
                    continue
                px0, py0, px1, py1 = part.bounds
                remnant_rooms.append(
                    Room(
                        id=_new_id("room"),
                        page_index=page_index,
                        bbox=(px0, py0, px1, py1),
                        polygon=[(float(x), float(y)) for x, y in part.exterior.coords],
                        area_m2=round(part.area / (ppm * ppm), 2),
                        label=None,
                        confidence=host.confidence,
                        uncertain=True,
                    )
                )

    if not new_corridors:
        return rooms, corridors, doors

    rooms = [r for r in rooms if r.id not in removed_room_ids] + remnant_rooms
    corridors = list(corridors) + new_corridors
    # A door whose connected room was split no longer points at a live entity. Null
    # the stale ref (connects already permits None). We do not re-point because the
    # split is geometrically ambiguous; the door's bbox and surviving side stay.
    cleaned_doors: list[Door] = []
    for door in doors:
        a, b = door.connects
        if a in removed_room_ids or b in removed_room_ids:
            door = door.model_copy(
                update={
                    "connects": (
                        None if a in removed_room_ids else a,
                        None if b in removed_room_ids else b,
                    )
                }
            )
        cleaned_doors.append(door)
    return rooms, corridors, cleaned_doors


def _host_clipped_chords(
    segments: list[tuple[tuple[float, float], tuple[float, float]]],
    hx0: float,
    hx1: float,
) -> list[tuple[float, float, float, float]]:
    """Like :func:`_long_horizontal_chords` but scoped to a single host room: each
    horizontal segment is clipped to the host x-range ``[hx0, hx1]`` and the span /
    coverage gates are measured against the HOST width, not the page width. This is
    what lets a split-trunk half that spans most of *its host* (but <50% of the
    page) qualify. Returns ``[(y, x_min, x_max, extent), ...]`` sorted by y.
    """
    host_w = hx1 - hx0
    if host_w <= 0:
        return []
    items: list[tuple[float, float, float]] = []
    for (x0, y0), (x1, y1) in segments:
        if abs(y0 - y1) > TRUNK_CARVE_Y_TOL:
            continue
        cx0, cx1 = max(hx0, min(x0, x1)), min(hx1, max(x0, x1))
        if cx1 - cx0 <= 0:
            continue
        items.append(((y0 + y1) / 2.0, cx0, cx1))
    items.sort()
    levels: list[tuple[float, list[tuple[float, float]]]] = []
    for yc, x0, x1 in items:
        for level_y, ivs in levels:
            if abs(level_y - yc) <= TRUNK_CARVE_Y_TOL:
                ivs.append((x0, x1))
                break
        else:
            levels.append((yc, [(x0, x1)]))
    chords: list[tuple[float, float, float, float]] = []
    for yc, ivs in levels:
        merged = _merge_intervals(ivs)
        x_min = min(a for a, _ in merged)
        x_max = max(b for _, b in merged)
        extent = x_max - x_min
        covered = sum(b - a for a, b in merged)
        if extent >= HOST_CARVE_CHORD_EXTENT_FRAC * host_w and covered >= HOST_CARVE_CHORD_COVER_FRAC * extent:
            chords.append((yc, x_min, x_max, extent))
    chords.sort()
    return chords


def _carve_host_band_corridors(
    rooms: list[Room],
    corridors: list[Corridor],
    doors: list[Door],
    augmented: list[tuple[tuple[float, float], tuple[float, float]]],
    page: PagePrimitives,
    ppm: float,
    page_index: int,
    min_room_area_m2: float,
) -> tuple[list[Room], list[Corridor], list[Door]]:
    """Part-3 additive pass: recover a SPLIT trunk corridor whose halves each span
    most of their flooded host room but less than half the page, so the part-2
    page-relative span gate misses them (m13's west/east halves divided by the
    elevator lobby; m14's full band). Runs AFTER :func:`_carve_trunk_corridors` and
    skips any band an existing corridor already covers, so part-2's m15/m16 trunk is
    preserved byte-for-byte. See the ``HOST_CARVE_*`` constants for the FP gates.
    """
    w_min = CORRIDOR_SHORT_MIN_M * ppm
    w_max = CORRIDOR_SHORT_MAX_M * ppm
    area_floor_pt2 = max((0.5 * ppm) ** 2, min_room_area_m2 * ppm * ppm)
    host_min_pt2 = HOST_CARVE_MIN_AREA_M2 * ppm * ppm
    existing_polys = [Polygon(c.polygon) for c in corridors]

    new_corridors: list[Corridor] = []
    remnant_rooms: list[Room] = []
    removed_room_ids: set[str] = set()

    for host in rooms:
        hx0, _hy0, hx1, _hy1 = host.bbox
        try:
            host_poly = Polygon(host.polygon)
        except (ValueError, TypeError):
            continue
        if host_poly.area < host_min_pt2:
            continue
        chords = _host_clipped_chords(augmented, hx0, hx1)
        if len(chords) < 2:
            continue
        carved = False
        for i in range(len(chords)):
            if carved:
                break
            for j in range(i + 1, len(chords)):
                y_a, xa0, xa1, _ = chords[i]
                y_b, xb0, xb1, _ = chords[j]
                dy = abs(y_b - y_a)
                if not (w_min <= dy <= w_max):
                    continue
                ox0, ox1 = max(xa0, xb0), min(xa1, xb1)
                if ox1 - ox0 <= 0:
                    continue
                y_lo, y_hi = min(y_a, y_b), max(y_a, y_b)
                strip = sbox(ox0, y_lo, ox1, y_hi)
                strip_area = strip.area
                if strip_area <= 0:
                    continue
                # GATE-A (decisive anti-phantom): the strip must be a genuinely OPEN
                # area inside the host polygon, not a thin sliver of an irregular
                # room (without this a 62.9 m² cambridge room carves a phantom).
                inter = host_poly.intersection(strip)
                if inter.is_empty or inter.area < HOST_CARVE_OPEN_FRAC * strip_area:
                    continue
                # GATE-B: corridor-tube aspect (length / width).
                if (ox1 - ox0) < HOST_CARVE_ASPECT_MIN * dy:
                    continue
                # GATE-C: no interior vertical crosses the band (host end-walls and
                # the m13 lobby wall sit at the strip edges and are ignored).
                if _band_has_crossing_vertical(
                    augmented, ox0, ox1, y_lo, y_hi, edge_margin_pt=HOST_CARVE_CROSS_EDGE_MARGIN_PT
                ):
                    continue
                # GATE-D: don't double-carve a band an existing corridor already
                # covers (preserves m15/m16's part-2 trunk).
                if any(
                    ep.intersection(strip).area > HOST_CARVE_OVERLAP_FRAC * strip_area
                    for ep in existing_polys
                ):
                    continue
                # Clip the corridor footprint to the host polygon (Codex part-3 P2):
                # the strip is a rectangle that, on a concave/notched host, can
                # extend up to (1 - HOST_CARVE_OPEN_FRAC) outside the host into
                # neighbouring space. Emit the host∩strip footprint instead so the
                # corridor geometry never leaks. min_width_m stays the wall-to-wall
                # band gap (dy), not the clipped polygon's short side.
                footprint = inter if inter.geom_type == "Polygon" else max(
                    (g for g in getattr(inter, "geoms", []) if g.geom_type == "Polygon"),
                    key=lambda g: g.area,
                    default=None,
                )
                if footprint is None or footprint.is_empty:
                    continue
                fx0, fy0, fx1, fy1 = footprint.bounds
                new_corridors.append(
                    Corridor(
                        id=_new_id("corridor"),
                        page_index=page_index,
                        bbox=(fx0, fy0, fx1, fy1),
                        polygon=[(float(x), float(y)) for x, y in footprint.exterior.coords],
                        min_width_m=round(dy / ppm, 2),
                        confidence=0.75,
                        uncertain=False,
                    )
                )
                existing_polys.append(strip)
                removed_room_ids.add(host.id)
                remainder = host_poly.difference(strip)
                for part in getattr(remainder, "geoms", [remainder]):
                    if part.is_empty or part.geom_type != "Polygon" or part.area < area_floor_pt2:
                        continue
                    px0, py0, px1, py1 = part.bounds
                    remnant_rooms.append(
                        Room(
                            id=_new_id("room"),
                            page_index=page_index,
                            bbox=(px0, py0, px1, py1),
                            polygon=[(float(x), float(y)) for x, y in part.exterior.coords],
                            area_m2=round(part.area / (ppm * ppm), 2),
                            label=None,
                            confidence=host.confidence,
                            uncertain=True,
                        )
                    )
                carved = True
                break

    if not new_corridors:
        return rooms, corridors, doors

    rooms = [r for r in rooms if r.id not in removed_room_ids] + remnant_rooms
    corridors = list(corridors) + new_corridors
    cleaned_doors: list[Door] = []
    for door in doors:
        a, b = door.connects
        if a in removed_room_ids or b in removed_room_ids:
            door = door.model_copy(
                update={
                    "connects": (
                        None if a in removed_room_ids else a,
                        None if b in removed_room_ids else b,
                    )
                }
            )
        cleaned_doors.append(door)
    return rooms, corridors, cleaned_doors


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
            if _is_sheet_edge_band(bbox, page.width_pt, page.height_pt):
                # Border frame / legend / title band mis-shaped as a corridor
                # (round-7 R7-BUG-001/003). Drop it: it is not a circulation
                # corridor and must not fire RC-CORRIDOR-WIDTH. Tracked like a
                # filtered polygon so the door classifier treats its boundary
                # as non-surviving rather than a real interior wall.
                filtered_polygons.append(poly)
                continue
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
        bx0, by0, bx1, by1 = min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)
        # A door bridge is a single wall-gap segment, so exactly one axis is
        # degenerate: a horizontal opening gives by1 == by0, a vertical
        # opening gives bx1 == bx0. A zero-area bbox breaks downstream
        # evidence overlays, alias-dedup keys, and sheet-region IoU (round-7
        # R7-BUG-006: every door issue emitted bbox height 0). Expand the
        # thin axis symmetrically to the opening width (≈ the leaf-swing
        # footprint, since a door leaf ≈ its opening). Symmetric expansion
        # keeps the centroid fixed, so the centroid-based door-side
        # classification and dimension binding below are unaffected, and the
        # width measurement (width_m) is unchanged.
        opening_pt = bridge.width_pt
        if bx1 - bx0 < opening_pt:
            cx = (bx0 + bx1) / 2.0
            bx0, bx1 = cx - opening_pt / 2.0, cx + opening_pt / 2.0
        if by1 - by0 < opening_pt:
            cy = (by0 + by1) / 2.0
            by0, by1 = cy - opening_pt / 2.0, cy + opening_pt / 2.0
        bbox = (bx0, by0, bx1, by1)
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

    # Recover a flooded trunk corridor (part 2 of the corridor-extraction
    # milestone) before dimension binding, so a carved corridor can still receive
    # a nearby dimension override. No-op on plans without a flooded trunk corridor.
    rooms, corridors, doors = _carve_trunk_corridors(
        rooms, corridors, doors, augmented, page, ppm, page_index, min_room_area_m2
    )
    # Part 3: recover SPLIT trunk corridors scoped to a large flooded host (m13
    # west/east halves; m14's full band). Runs after the part-2 carve and skips
    # bands an existing corridor already covers, so m15/m16's part-2 trunk is a
    # strict no-op. No-op on plans without a large flooded host.
    rooms, corridors, doors = _carve_host_band_corridors(
        rooms, corridors, doors, augmented, page, ppm, page_index, min_room_area_m2
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
