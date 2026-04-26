"""Geometry helpers: snapping, axis-aligned classification, door-gap bridging.

Coordinate conventions
----------------------
Everything in this module is in PDF points (PyMuPDF coords: origin top-left, y
grows downward). Conversions to meters happen at the property-extraction step
in `builder.py`.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import pairwise

from shapely.geometry import LineString, MultiLineString, Polygon
from shapely.ops import polygonize, unary_union

Point = tuple[float, float]
Segment = tuple[Point, Point]

AXIS_TOL_PT = 0.75  # snap tolerance to call a segment horizontal/vertical
SNAP_TOL_PT = 0.5   # endpoint quantization step
COLINEAR_TOL_PT = 1.0


def is_horizontal(seg: Segment) -> bool:
    return abs(seg[0][1] - seg[1][1]) < AXIS_TOL_PT


def is_vertical(seg: Segment) -> bool:
    return abs(seg[0][0] - seg[1][0]) < AXIS_TOL_PT


def _snap(p: Point) -> Point:
    return (round(p[0] / SNAP_TOL_PT) * SNAP_TOL_PT, round(p[1] / SNAP_TOL_PT) * SNAP_TOL_PT)


def normalize(seg: Segment) -> Segment:
    """Snap endpoints and order them so (x, y) is the lexicographically smaller end."""
    a, b = _snap(seg[0]), _snap(seg[1])
    return (a, b) if a <= b else (b, a)


@dataclass(frozen=True)
class GapBridge:
    """A segment we inserted to close a door-shaped opening between two collinear walls."""

    segment: Segment
    axis: str  # "h" or "v"
    width_pt: float


def bridge_door_gaps(
    segments: list[Segment],
    *,
    max_gap_pt: float,
    min_gap_pt: float = 1.0,
) -> tuple[list[Segment], list[GapBridge]]:
    """Find collinear axis-aligned wall fragments separated by a small gap and
    insert bridging segments. Returns (segments_including_bridges, bridges).

    The original `segments` list is preserved; bridges are appended.
    """
    bridges: list[GapBridge] = []
    augmented = list(segments)

    horizontals: dict[float, list[Segment]] = {}
    verticals: dict[float, list[Segment]] = {}
    for seg in segments:
        s = normalize(seg)
        if is_horizontal(s):
            y = round(s[0][1] / SNAP_TOL_PT) * SNAP_TOL_PT
            horizontals.setdefault(y, []).append(s)
        elif is_vertical(s):
            x = round(s[0][0] / SNAP_TOL_PT) * SNAP_TOL_PT
            verticals.setdefault(x, []).append(s)

    # Horizontal gaps
    for y, segs in horizontals.items():
        segs_sorted = sorted(segs, key=lambda s: s[0][0])
        for a, b in pairwise(segs_sorted):
            gap = b[0][0] - a[1][0]
            if min_gap_pt < gap < max_gap_pt:
                bridge = ((a[1][0], y), (b[0][0], y))
                augmented.append(bridge)
                bridges.append(GapBridge(segment=bridge, axis="h", width_pt=gap))

    # Vertical gaps
    for x, segs in verticals.items():
        segs_sorted = sorted(segs, key=lambda s: s[0][1])
        for a, b in pairwise(segs_sorted):
            gap = b[0][1] - a[1][1]
            if min_gap_pt < gap < max_gap_pt:
                bridge = ((x, a[1][1]), (x, b[0][1]))
                augmented.append(bridge)
                bridges.append(GapBridge(segment=bridge, axis="v", width_pt=gap))

    return augmented, bridges


def polygonize_segments(segments: list[Segment], *, min_area_pt2: float = 100.0) -> list[Polygon]:
    """Run shapely polygonize over the noded line network.

    Normalizes (snaps to SNAP_TOL_PT grid + lex-orders endpoints) every
    input segment before noding. Without this, generators producing
    endpoints that are off the snap grid (e.g. 78.75pt) leave the
    bridge-inserted segments not quite touching the original wall
    fragments — bridges end up snapped while originals don't, opening
    a sub-pt gap that breaks polygon closure. Phase 18-D adversarial
    examiner surfaced this on shrunken-bedroom layouts: bedroom and
    living merged into one polygon because the mid-wall break was
    slightly off the bridge snap grid.
    """
    if not segments:
        return []
    lines = [LineString(normalize(seg)) for seg in segments]
    noded = unary_union(MultiLineString(lines))
    polys = [p for p in polygonize(noded) if p.area >= min_area_pt2]
    polys.sort(key=lambda p: -p.area)
    return polys
