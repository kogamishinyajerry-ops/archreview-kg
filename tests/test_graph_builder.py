from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from archkg.cli.main import app
from archkg.graph.builder import _is_sheet_edge_band, build_graph, render_overlay
from archkg.graph.geometry import bridge_door_gaps, polygonize_segments
from archkg.ingest.primitive_extractor import extract


def test_geometry_polygonize_closes_a_simple_box() -> None:
    box = [
        ((0.0, 0.0), (10.0, 0.0)),
        ((10.0, 0.0), (10.0, 10.0)),
        ((10.0, 10.0), (0.0, 10.0)),
        ((0.0, 10.0), (0.0, 0.0)),
    ]
    polys = polygonize_segments(box, min_area_pt2=10.0)
    assert len(polys) == 1
    assert abs(polys[0].area - 100.0) < 1e-6


def test_polygonize_segments_closes_off_grid_endpoints() -> None:
    """Phase 18-D regression: bridge_door_gaps stores its bridge with
    snapped endpoints (multiples of SNAP_TOL_PT) but appends the original
    raw wall fragments unchanged. When the wall fragments end OFF the
    snap grid (e.g. 78.75pt) and the bridge endpoints are ON the grid
    (79pt / 121pt), the bridge ends a fractional pt away from the
    fragment endpoint and shapely never closes the polygon. The
    adversarial battery surfaced this on shrunken-bedroom layouts:
    bedroom and living merged into a single 36 m² polygon instead of
    being split by the mid-wall.

    This test exercises the *actual* failing topology: TWO separate
    wall fragments ending at off-grid coords, plus a SEPARATE bridge
    spanning the gap with on-grid endpoints. Pre-fix shapely would
    not close the box around x=[0,100]; post-fix `polygonize_segments`
    normalizes all inputs first so fragment and bridge endpoints
    coincide and the mid-wall splits the box.
    """
    from archkg.graph.geometry import SNAP_TOL_PT

    # Compose off-grid endpoints from SNAP_TOL_PT so this test stays
    # meaningful if the snap step ever changes (Codex P18-E R1 P2).
    off = SNAP_TOL_PT / 2
    bridge_lo, bridge_hi = 79.0, 121.0  # multiples of SNAP_TOL_PT
    frag_top_end = bridge_lo - off       # 78.75 — off-grid wall end
    frag_bot_start = bridge_hi + off     # 121.25 — off-grid wall start

    segs = [
        # Outer rectangle.
        ((0.0, 0.0), (200.0, 0.0)),
        ((200.0, 0.0), (200.0, 200.0)),
        ((200.0, 200.0), (0.0, 200.0)),
        ((0.0, 200.0), (0.0, 0.0)),
        # Mid-wall, top fragment: off-grid end.
        ((100.0, 0.0), (100.0, frag_top_end)),
        # Bridge inserted by bridge_door_gaps with snapped endpoints.
        # Note: this is a SEPARATE segment, not connected to the
        # fragments above unless polygonize_segments snaps inputs.
        ((100.0, bridge_lo), (100.0, bridge_hi)),
        # Mid-wall, bottom fragment: off-grid start.
        ((100.0, frag_bot_start), (100.0, 200.0)),
    ]
    polys = polygonize_segments(segs, min_area_pt2=100.0)
    assert len(polys) == 2, (
        f"mid-wall must split the box into two polygons; got {len(polys)}"
    )
    areas = sorted(round(p.area) for p in polys)
    assert areas == [20000, 20000], (
        f"expected two equal halves of 20000 pt², got {areas}"
    )


def test_geometry_bridges_door_gap_in_horizontal_wall() -> None:
    segs = [
        ((0.0, 0.0), (40.0, 0.0)),
        ((45.0, 0.0), (100.0, 0.0)),
    ]
    augmented, bridges = bridge_door_gaps(segs, max_gap_pt=10.0, min_gap_pt=1.0)
    assert len(augmented) == 3
    assert len(bridges) == 1
    assert abs(bridges[0].width_pt - 5.0) < 1e-6


def test_build_graph_on_synthetic_sample_finds_expected_entities(sample_pdf: Path) -> None:
    p = extract(sample_pdf, points_per_meter=50.0)
    g = build_graph(p)

    # 4 rooms + 1 corridor expected from the synthetic floor plan.
    assert len(g.corridors) == 1
    assert len(g.rooms) == 4

    # Corridor: 1.05 m wide (FAILS the >=1.20 m rule downstream)
    assert g.corridors[0].min_width_m is not None
    assert abs(g.corridors[0].min_width_m - 1.05) < 0.05

    # Doors: 4 gaps were drawn (2 in each horizontal corridor wall + 2 in the mid-wall),
    # all sized 0.85-0.90 m.
    assert len(g.doors) >= 4
    for d in g.doors:
        assert d.width_m is not None
        assert 0.7 <= d.width_m <= 1.1

    # At least one room labeled bedroom (text "BEDROOM" in the sample)
    labels = {r.label for r in g.rooms if r.label}
    assert "bedroom" in labels
    assert "kitchen" in labels


def test_door_bboxes_have_positive_area(sample_pdf: Path) -> None:
    """Round-7 R7-BUG-006 regression: a door bridge is a single wall-gap
    segment, so the raw segment bbox is degenerate on one axis (height 0
    for a horizontal opening). Every emitted door must instead carry a
    real rectangle so evidence overlays, alias-dedup and sheet-region IoU
    work. The thin axis is expanded to the opening width, so both
    dimensions must be >0 and at least the door's own width in points.
    """
    p = extract(sample_pdf, points_per_meter=50.0)
    g = build_graph(p)
    assert g.doors, "sample must produce doors to exercise this regression"
    for d in g.doors:
        x0, y0, x1, y1 = d.bbox
        w, h = x1 - x0, y1 - y0
        assert w > 0.0 and h > 0.0, f"door {d.id} has degenerate bbox {d.bbox}"


def test_is_sheet_edge_band_discriminates_artifacts_from_corridors() -> None:
    """Round-7 R7-BUG-001/003 helper: a sheet-spanning band hugging an edge is
    an artifact; an interior band (even full-width) is a real corridor."""
    W, H = 1190.0, 842.0
    # m16 phantom: full-width strip flush to the bottom edge → artifact.
    assert _is_sheet_edge_band((60.0, 762.0, 1130.0, 812.0), W, H) is True
    # full-width strip flush to the top edge → artifact.
    assert _is_sheet_edge_band((60.0, 30.0, 1130.0, 110.0), W, H) is True
    # full-height strip flush to the right edge → artifact.
    assert _is_sheet_edge_band((1100.0, 20.0, 1180.0, 820.0), W, H) is True
    # the synthetic sample's REAL corridor: full width but mid-page → kept.
    assert _is_sheet_edge_band((0.0, 200.0, 500.0, 252.5), 500.0, 400.0) is False
    # a normal interior corridor → kept.
    assert _is_sheet_edge_band((300.0, 350.0, 700.0, 402.0), W, H) is False


def test_titleblock_band_not_classified_as_corridor() -> None:
    """E2E (round-7 R7-BUG-001/003): the m16 plan's full-width bottom/top
    title-block & legend strips must NOT become corridors, so RC-CORRIDOR-WIDTH
    can't fire a phantom violation on them."""
    pdf = Path("samples/real_plans/test-m16-defective-plan.pdf")
    if not pdf.exists():
        import pytest

        pytest.skip("m16 sample not present")
    g = build_graph(extract(pdf))
    for c in g.corridors:
        assert not _is_sheet_edge_band(c.bbox, g.page_width_pt, g.page_height_pt), (
            f"corridor {c.id} bbox={c.bbox} is a sheet-edge band and should be dropped"
        )
    # The specific phantom from the round-7 audit ([60,762,1130,812], 1.0m).
    assert not any(
        abs(c.bbox[0] - 60.0) < 5 and abs(c.bbox[1] - 762.0) < 5 and abs(c.bbox[2] - 1130.0) < 5
        for c in g.corridors
    ), "the round-7 title-block phantom corridor must no longer be emitted"


def test_min_room_area_filter_drops_sub_threshold_polygons(sample_pdf: Path) -> None:
    """Phase 19-D: ``min_room_area_m2`` is a noise filter for real CAD
    PDFs. The synthetic sample has 4 rooms at 14.75-20 m² so a 10 m²
    floor drops none, a 16 m² floor drops the two 14.75 m² rooms, and
    a 100 m² floor drops everything. The default 0.0 keeps the
    backward-compat path used by ``archkg review``.

    The Medfield real-CAD case study motivates this: a 1.0 m² floor
    cuts ~40 % of the spurious "rooms" that were really window frames,
    dim boxes, and fixture outlines, before they become rule-fire
    targets.
    """
    p = extract(sample_pdf, points_per_meter=50.0)

    # Default 0.0: no filtering (backward-compat with archkg review).
    g_default = build_graph(p)
    assert len(g_default.rooms) == 4

    # 10 m² floor: all 4 rooms are above (14.75 m² is smallest).
    g_loose = build_graph(p, min_room_area_m2=10.0)
    assert len(g_loose.rooms) == 4

    # 16 m² floor: the two 14.75 m² rooms drop, leaving 2 of size 20 m².
    g_tight = build_graph(p, min_room_area_m2=16.0)
    assert len(g_tight.rooms) == 2
    for r in g_tight.rooms:
        assert r.area_m2 is not None and r.area_m2 >= 16.0

    # 100 m² floor: everything drops.
    g_strict = build_graph(p, min_room_area_m2=100.0)
    assert len(g_strict.rooms) == 0


def test_filter_drops_doors_anchored_to_filtered_noise() -> None:
    """Codex P19-D R3 P0: a door between a surviving room and a
    *filtered noise* polygon must be dropped, not kept. Pre-R3 the
    filtered side resolved to the same ``None`` as a true exterior,
    so the orphan filter (`drop iff (None, None)`) would keep this
    hybrid orphan and let RC-DOOR-WIDTH fire on it. The R3 fix
    classifies the side as ``"filtered"`` separately from
    ``"exterior"`` and drops any door touching a filtered side.

    Synthetic geometry: a 48 m² big room sharing one wall with a
    1.7 m² side polygon, joined by a 0.9 m gap. With
    ``min_room_area_m2=3.0`` the side polygon is dropped; the gap is
    a noise wall break, not a real door.
    """
    from archkg.schemas import LinePrimitive, PagePrimitives, Primitives

    # ppm=50 → 1 m = 50 pt. Door gap (400,100)-(400,145) is 45 pt = 0.9 m.
    segs = [
        # Big room outer (8 m x 6 m = 48 m²).
        LinePrimitive(p0=(0.0, 0.0), p1=(400.0, 0.0)),
        LinePrimitive(p0=(400.0, 0.0), p1=(400.0, 100.0)),
        # door gap at (400, 100) - (400, 145)
        LinePrimitive(p0=(400.0, 145.0), p1=(400.0, 300.0)),
        LinePrimitive(p0=(400.0, 300.0), p1=(0.0, 300.0)),
        LinePrimitive(p0=(0.0, 300.0), p1=(0.0, 0.0)),
        # Small side polygon (1 m x 1.7 m = 1.7 m²) sharing the door wall.
        LinePrimitive(p0=(400.0, 80.0), p1=(450.0, 80.0)),
        LinePrimitive(p0=(450.0, 80.0), p1=(450.0, 165.0)),
        LinePrimitive(p0=(450.0, 165.0), p1=(400.0, 165.0)),
        # Shared-wall fragments (above and below the door gap) — these
        # close BOTH polygons because they're collinear with the big
        # room's right wall fragments above.
        LinePrimitive(p0=(400.0, 80.0), p1=(400.0, 100.0)),
        LinePrimitive(p0=(400.0, 145.0), p1=(400.0, 165.0)),
    ]
    page = PagePrimitives(
        page_index=0, width_pt=600.0, height_pt=400.0,
        lines=segs, texts=[],
    )
    p = Primitives(
        source_pdf="synthetic.pdf", points_per_meter=50.0, pages=[page],
    )

    # Floor=0.0 (off): both polygons become rooms; door survives with
    # both sides anchored to a real room.
    g_off = build_graph(p, min_room_area_m2=0.0)
    assert len(g_off.rooms) == 2, (
        f"expected 2 rooms, got {len(g_off.rooms)} — synthetic geometry "
        "may have regressed; check polygonize output"
    )
    assert len(g_off.doors) == 1, f"expected 1 door, got {len(g_off.doors)}"

    # Floor=3.0: 1.7 m² polygon filtered. Door is now a hybrid orphan
    # (one side surviving room, one side filtered noise) and must be
    # dropped. Pre-R3 the door survived as ('big_room_id', None) and
    # the filter kept it.
    g_filt = build_graph(p, min_room_area_m2=3.0)
    assert len(g_filt.rooms) == 1, (
        f"expected 1 surviving room (1.7 m² is below the 3 m² floor), "
        f"got {len(g_filt.rooms)}"
    )
    assert g_filt.doors == [], (
        "door anchored to a filtered noise polygon must be pruned; "
        f"got {len(g_filt.doors)} survivor(s) with connects="
        f"{[d.connects for d in g_filt.doors]}"
    )


def test_filter_drops_doors_anchored_to_thin_filtered_strip() -> None:
    """Codex P19-D R4 P0: a 0.2 m x 4.0 m noise strip (0.8 m²,
    filtered at the studio's default 1.0 m² floor) used to fool the
    fixed 0.3 m probe — the perpendicular sample on the strip side
    overshot the strip and landed in true exterior, so the
    classifier returned "exterior" instead of "filtered" and the
    door survived as ``(big_room_id, None)``. The R4 fix multi-probes
    from 0.05 m outward, hitting the strip on the first or second
    probe.

    The test deliberately chooses 0.2 m (= 10 pt at ppm=50, well
    under the legacy 0.3 m probe) so a regression to a single fixed
    probe would resurface as a kept door.
    """
    from archkg.schemas import LinePrimitive, PagePrimitives, Primitives

    # ppm=50 → 1m = 50pt. Door gap (400,130)-(400,175): 45pt = 0.9m.
    segs = [
        # Big room outer (8 m x 6 m = 48 m²).
        LinePrimitive(p0=(0.0, 0.0), p1=(400.0, 0.0)),
        LinePrimitive(p0=(400.0, 0.0), p1=(400.0, 130.0)),
        LinePrimitive(p0=(400.0, 175.0), p1=(400.0, 300.0)),
        LinePrimitive(p0=(400.0, 300.0), p1=(0.0, 300.0)),
        LinePrimitive(p0=(0.0, 300.0), p1=(0.0, 0.0)),
        # 0.2 m x 4.0 m strip (10 pt x 200 pt = 0.8 m²) along the
        # right wall. Door gap is in the shared wall.
        LinePrimitive(p0=(400.0, 50.0), p1=(410.0, 50.0)),
        LinePrimitive(p0=(410.0, 50.0), p1=(410.0, 250.0)),
        LinePrimitive(p0=(410.0, 250.0), p1=(400.0, 250.0)),
        # Shared-wall fragments closing both polygons.
        LinePrimitive(p0=(400.0, 50.0), p1=(400.0, 130.0)),
        LinePrimitive(p0=(400.0, 175.0), p1=(400.0, 250.0)),
    ]
    page = PagePrimitives(
        page_index=0, width_pt=600.0, height_pt=400.0,
        lines=segs, texts=[],
    )
    p = Primitives(
        source_pdf="synthetic.pdf", points_per_meter=50.0, pages=[page],
    )

    # Floor=1.0 (studio default): strip filtered (0.8 m² < 1.0).
    g = build_graph(p, min_room_area_m2=1.0)
    assert len(g.rooms) == 1, (
        f"expected 1 surviving room, got {len(g.rooms)} — synthetic "
        "geometry may have regressed"
    )
    assert g.doors == [], (
        "thin filtered strip must trigger door pruning via multi-probe "
        f"classifier; got {len(g.doors)} survivor(s) with connects="
        f"{[d.connects for d in g.doors]}. If this fails, the side "
        "classifier likely regressed to a single fixed probe distance."
    )


def test_filter_keeps_real_door_when_filtered_polygon_only_touches_endpoint() -> None:
    """Codex P19-D R7 P1 (finding 1): a polygon that only touches a
    bridge ENDPOINT (single-point contact) must not be classified
    as adjacent to the bridge. Pre-R7 the boundary-distance check
    let single-point touchers through, so a real exterior door
    adjacent to a 1 m² noise square at the upper jamb was killed.

    The R7 fix requires a substantial fraction of the bridge length
    to lie within the polygon's boundary buffer (default ≥50%), so
    endpoint-only contact fails the adjacency test.
    """
    from archkg.schemas import LinePrimitive, PagePrimitives, Primitives

    segs = [
        # Big room (8 m x 6 m = 48 m²) with exterior door on top wall.
        LinePrimitive(p0=(0.0, 0.0), p1=(400.0, 0.0)),
        LinePrimitive(p0=(400.0, 0.0), p1=(400.0, 300.0)),
        LinePrimitive(p0=(400.0, 300.0), p1=(225.0, 300.0)),
        # door gap (225, 300) - (180, 300), 0.9 m wide
        LinePrimitive(p0=(180.0, 300.0), p1=(0.0, 300.0)),
        LinePrimitive(p0=(0.0, 300.0), p1=(0.0, 0.0)),
        # 1 m² square (50 pt x 50 pt) sharing only the upper jamb
        # endpoint at (225, 300). It does NOT cover any of the door
        # bridge between x=180 and x=225.
        LinePrimitive(p0=(225.0, 300.0), p1=(275.0, 300.0)),
        LinePrimitive(p0=(275.0, 300.0), p1=(275.0, 350.0)),
        LinePrimitive(p0=(275.0, 350.0), p1=(225.0, 350.0)),
        LinePrimitive(p0=(225.0, 350.0), p1=(225.0, 300.0)),
    ]
    page = PagePrimitives(
        page_index=0, width_pt=600.0, height_pt=400.0,
        lines=segs, texts=[],
    )
    p = Primitives(
        source_pdf="synthetic.pdf", points_per_meter=50.0, pages=[page],
    )

    # Floor=2.0: the 1 m² square is filtered. The big room remains.
    # The exterior door must still be kept — the square only touches
    # the bridge endpoint, not the bridge body.
    g = build_graph(p, min_room_area_m2=2.0)
    assert len(g.rooms) == 1, f"expected 1 surviving room; got {len(g.rooms)}"
    assert len(g.doors) == 1, (
        "endpoint-only contact must not count as bridge adjacency; "
        f"got {len(g.doors)} door(s) with connects="
        f"{[d.connects for d in g.doors]}. If this fails, the "
        "adjacency check has regressed to min-distance only."
    )


def test_classify_bridge_side_handles_concave_polygons() -> None:
    """Codex P19-D R7 P1 (finding 2): centroid-based side resolution
    is not sound for concave (L/U/C-shaped) polygons — a valid
    simple polygon's centroid can lie outside the shape and on the
    wrong side of the bridge. The R7 fix uses a tiny local step off
    the bridge midpoint along the signed normal and tests whether
    the polygon covers that point, which works correctly regardless
    of shape concavity.

    Codex's exact L-shape: ``[(0,0),(0,10),(2,10),(2,0),(20,0),
    (20,-4),(-40,-4),(-40,0)]``. The bridge ``((0,0),(0,10))`` is
    locally bounded by the 2x10 rectangle on the +x side; the
    polygon's bottom strip extends to x=-40 (and pulls the centroid
    out to x≈-9). Pre-R7, ``direction=-1`` (probing the +x side)
    incorrectly returned ``exterior`` because the centroid was on
    the -x side.
    """
    from shapely.geometry import Polygon as _Polygon

    from archkg.graph.builder import _classify_bridge_side

    poly = _Polygon([
        (0.0, 0.0), (0.0, 10.0), (2.0, 10.0), (2.0, 0.0),
        (20.0, 0.0), (20.0, -4.0), (-40.0, -4.0), (-40.0, 0.0),
    ])

    # direction=-1 probes the +x side. The 2x10 rectangle interior
    # is on +x, so the polygon is adjacent on that side.
    kind_pos, _ = _classify_bridge_side(
        ((0.0, 0.0), (0.0, 10.0)), -1, [], [], [poly]
    )
    assert kind_pos == "filtered", (
        f"L-shaped polygon's interior is on the +x side of bridge "
        f"(0,0)-(0,10); classifier should report 'filtered' but got "
        f"{kind_pos!r}. If this fails, side resolution has regressed "
        "to centroid-based logic, which is unsound for concave shapes."
    )


def test_filter_drops_doors_anchored_to_sub_probe_filtered_strip() -> None:
    """Codex P19-D R6 P1: any fixed positive single-probe offset has
    a deterministic blind band [0, offset] for adjacent polygons
    thinner than the offset. Codex's repro: 0.04 m × 8.0 m strip
    (0.32 m², passes polygonize's 0.25 m² floor but is filtered at
    1.0 m²). Pre-R6 single 0.05 m probe lands past the strip in true
    exterior, the door survives as a half-orphan.

    The R6 boundary-adjacency classifier has no probe band: it
    detects the strip because the bridge segment is part of the
    strip's polygon boundary, regardless of strip thickness.
    """
    from archkg.schemas import LinePrimitive, PagePrimitives, Primitives

    # ppm=50 → 0.04 m = 2 pt. Strip from x=400 to x=402, y=50..450
    # (8 m long). Door gap (400, 100)-(400, 145), 0.9 m.
    segs = [
        # Big room outer (8 m x 8 m = 64 m²).
        LinePrimitive(p0=(0.0, 0.0), p1=(400.0, 0.0)),
        LinePrimitive(p0=(400.0, 0.0), p1=(400.0, 100.0)),
        LinePrimitive(p0=(400.0, 145.0), p1=(400.0, 400.0)),
        LinePrimitive(p0=(400.0, 400.0), p1=(0.0, 400.0)),
        LinePrimitive(p0=(0.0, 400.0), p1=(0.0, 0.0)),
        # 0.04 m x 8.0 m strip (2 pt x 400 pt = 0.32 m²) sharing the
        # door wall.
        LinePrimitive(p0=(400.0, 0.0), p1=(402.0, 0.0)),
        LinePrimitive(p0=(402.0, 0.0), p1=(402.0, 400.0)),
        LinePrimitive(p0=(402.0, 400.0), p1=(400.0, 400.0)),
    ]
    page = PagePrimitives(
        page_index=0, width_pt=600.0, height_pt=500.0,
        lines=segs, texts=[],
    )
    p = Primitives(
        source_pdf="synthetic.pdf", points_per_meter=50.0, pages=[page],
    )

    # Floor=1.0: strip filtered (0.32 m² < 1.0).
    g = build_graph(p, min_room_area_m2=1.0)
    assert len(g.rooms) == 1, (
        f"expected 1 surviving room (strip is 0.32 m² < 1.0 floor); "
        f"got {len(g.rooms)}"
    )
    assert g.doors == [], (
        "0.04 m wide strip is thinner than any fixed probe distance; "
        "the boundary-adjacency classifier must still identify it as "
        f"the bridge's neighbour and drop the door. Got {len(g.doors)} "
        f"door(s) with connects={[d.connects for d in g.doors]}. If "
        "this fails, the classifier likely regressed to point-probe."
    )


def test_filter_keeps_real_exterior_door_with_detached_noise() -> None:
    """Codex P19-D R5 P1: a real exterior door must NOT be killed
    just because a filtered noise strip happens to sit a few cm past
    the wall. The pre-R5 multi-probe walked outward until it hit ANY
    polygon; if true exterior occupied the first 0.10 m and a
    detached noise strip lay at 0.15 m, the classifier returned
    "filtered" and the door was dropped. The R5 fix uses a single
    close-in probe so detached polygons no longer count as adjacent.

    Synthetic geometry: 8 m x 6 m room with a 0.9 m exterior door;
    a detached 0.2 m x 4.0 m noise strip starting 0.15 m past the
    outer wall. With ``min_room_area_m2=1.0`` the strip is filtered
    but the door is still anchored to true exterior on its outer
    side, not to the strip.
    """
    from archkg.schemas import LinePrimitive, PagePrimitives, Primitives

    # Room outer rectangle (0,0)-(400,300) with door gap on top wall.
    # Door gap: (180, 300) - (225, 300), 45 pt = 0.9 m wide.
    # Detached strip: starts 0.15 m (=7.5 pt) past y=300, so y in
    # (307.5 .. 317.5) — that is, 0.2 m strip width, 4.0 m long.
    segs = [
        LinePrimitive(p0=(0.0, 0.0), p1=(400.0, 0.0)),
        LinePrimitive(p0=(400.0, 0.0), p1=(400.0, 300.0)),
        LinePrimitive(p0=(400.0, 300.0), p1=(225.0, 300.0)),
        # Door gap (225,300) - (180,300) — 45 pt wide.
        LinePrimitive(p0=(180.0, 300.0), p1=(0.0, 300.0)),
        LinePrimitive(p0=(0.0, 300.0), p1=(0.0, 0.0)),
        # Detached noise strip outside the room (above the door wall).
        # Strip: (100, 307.5) - (300, 317.5), 200 pt x 10 pt = 0.8 m².
        LinePrimitive(p0=(100.0, 307.5), p1=(300.0, 307.5)),
        LinePrimitive(p0=(300.0, 307.5), p1=(300.0, 317.5)),
        LinePrimitive(p0=(300.0, 317.5), p1=(100.0, 317.5)),
        LinePrimitive(p0=(100.0, 317.5), p1=(100.0, 307.5)),
    ]
    page = PagePrimitives(
        page_index=0, width_pt=600.0, height_pt=400.0,
        lines=segs, texts=[],
    )
    p = Primitives(
        source_pdf="synthetic.pdf", points_per_meter=50.0, pages=[page],
    )

    g = build_graph(p, min_room_area_m2=1.0)
    assert len(g.rooms) == 1, (
        f"expected 1 surviving room (strip is 0.8 m², below 1.0 floor), "
        f"got {len(g.rooms)}"
    )
    assert len(g.doors) == 1, (
        "real exterior door must survive even when a detached noise "
        "strip sits within the legacy probe radius; got "
        f"{len(g.doors)} door(s)"
    )
    # The door's exterior side must classify as exterior, not filtered:
    # connects=(room_id, None) is the canonical exterior-door shape.
    door = g.doors[0]
    assert (door.connects[0] is None) ^ (door.connects[1] is None), (
        f"exterior door must have exactly one None side, got "
        f"connects={door.connects}"
    )


def test_door_connects_anchor_to_rooms_or_corridors(sample_pdf: Path) -> None:
    """Codex P19-D R2 P0: ``_door_from_bridge`` must search BOTH
    rooms and corridors when assigning ``connects``. Searching only
    rooms (the pre-R2 behaviour) misclassified real corridor-side
    doors as ``(room, None)`` orphans, which would then be falsely
    pruned by the orphan-door filter.

    The synthetic sample has 4 corridor-adjacent doors. After the
    R2 fix every one of them carries a corridor id on its corridor
    side, not ``None``.
    """
    p = extract(sample_pdf, points_per_meter=50.0)
    g = build_graph(p, min_room_area_m2=0.0)

    # Every door has at least one corridor or room on each side.
    corridor_ids = {c.id for c in g.corridors}
    room_ids = {r.id for r in g.rooms}
    seen_corridor_anchor = False
    for d in g.doors:
        for side in d.connects:
            if side is None:
                continue
            assert side in room_ids or side in corridor_ids, (
                f"door {d.id} connects to unknown id {side}"
            )
            if side in corridor_ids:
                seen_corridor_anchor = True
    assert seen_corridor_anchor, (
        "expected at least one door anchored to a corridor; if every "
        "connects entry is a room id, _door_from_bridge has regressed "
        "to room-only matching and the orphan-door filter will start "
        "killing real corridor-side doors"
    )


def test_min_room_area_filter_also_prunes_orphan_doors(sample_pdf: Path) -> None:
    """Codex P19-D R1 P0 + R2 P0: when ``min_room_area_m2`` drops
    noise polygons, the doors detected on wall breaks adjacent to
    those noise polygons must be pruned too. RC-DOOR-WIDTH otherwise
    fires on dozens of non-door wall breaks (the Medfield 89-
    violation root cause).

    The synthetic sample has 4 rooms (14.75-20 m²) + 1 corridor
    (10.5 m²) + 6 doors. Test against three thresholds:

    - ``floor=0.0`` (off): no filtering — full 4/1/6 baseline.
    - ``floor=1.0`` (default): no noise to drop — same 4/1/6, every
      door still anchored. Proves the filter is conservative on
      clean PDFs.
    - ``floor=16.0``: drops the two 14.75 m² rooms AND the 10.5 m²
      corridor. Doors anchored only to the dropped entities become
      orphans and must be pruned. Doors that still touch a 20 m²
      survivor must be kept.
    """
    p = extract(sample_pdf, points_per_meter=50.0)

    g_off = build_graph(p, min_room_area_m2=0.0)
    g_on = build_graph(p, min_room_area_m2=1.0)
    g_aggr = build_graph(p, min_room_area_m2=16.0)

    # 1.0 floor: identical to off (no noise in clean sample).
    assert len(g_on.doors) == len(g_off.doors)
    for d in g_on.doors:
        assert d.connects is not None
        assert d.connects[0] is not None or d.connects[1] is not None, (
            f"door {d.id} survived the filter but connects to no room"
        )

    # 16.0 floor: 2 small rooms + corridor drop, 2 large rooms remain.
    assert len(g_aggr.rooms) == 2
    assert g_aggr.corridors == []
    surviving_room_ids = {r.id for r in g_aggr.rooms}
    # Every surviving door must touch a surviving room on at least
    # one side (no surviving corridors at this floor).
    for d in g_aggr.doors:
        anchored = False
        for side in d.connects:
            if side in surviving_room_ids:
                anchored = True
                break
        assert anchored, (
            f"door {d.id} survived the orphan filter but connects "
            f"to no surviving room (connects={d.connects}, "
            f"surviving_rooms={surviving_room_ids})"
        )
    # And the count must be strictly less than off (some doors
    # were genuinely orphaned and pruned).
    assert len(g_aggr.doors) < len(g_off.doors), (
        "16 m² floor must drop at least one door (the doors that "
        "connected only to the dropped 14.75 m² rooms / corridor); "
        f"off={len(g_off.doors)}, aggressive={len(g_aggr.doors)}"
    )


def test_dimension_text_overrides_geometry_for_corridor(sample_pdf: Path) -> None:
    p = extract(sample_pdf, points_per_meter=50.0)
    g = build_graph(p)
    # The text "CORRIDOR W=1.05" should bind to the corridor and pin min_width_m to 1.05.
    assert g.corridors[0].min_width_m is not None
    assert abs(g.corridors[0].min_width_m - 1.05) < 1e-3


def test_cli_build_graph_writes_file_and_overlay(sample_pdf: Path, tmp_path: Path) -> None:
    runner = CliRunner()
    primitives_path = tmp_path / "primitives.json"
    graph_path = tmp_path / "entity_graph.json"
    overlay_path = tmp_path / "overlay.png"

    r1 = runner.invoke(app, ["ingest", str(sample_pdf), "-o", str(primitives_path)])
    assert r1.exit_code == 0, r1.output

    r2 = runner.invoke(
        app,
        [
            "build-graph",
            str(primitives_path),
            "-o",
            str(graph_path),
            "--overlay-pdf",
            str(sample_pdf),
            "--overlay-out",
            str(overlay_path),
        ],
    )
    assert r2.exit_code == 0, r2.output
    payload = json.loads(graph_path.read_text(encoding="utf-8"))
    assert payload["page_index"] == 0
    assert overlay_path.exists()


def test_cli_build_graph_applies_sheet_region_before_graphing(tmp_path: Path) -> None:
    from archkg.schemas import LinePrimitive, PagePrimitives, Primitives

    primitives = Primitives(
        source_pdf="fixture.pdf",
        points_per_meter=50.0,
        pages=[
            PagePrimitives(
                page_index=0,
                width_pt=500.0,
                height_pt=300.0,
                lines=[
                    LinePrimitive(p0=(10.0, 10.0), p1=(110.0, 10.0)),
                    LinePrimitive(p0=(110.0, 10.0), p1=(110.0, 110.0)),
                    LinePrimitive(p0=(110.0, 110.0), p1=(10.0, 110.0)),
                    LinePrimitive(p0=(10.0, 110.0), p1=(10.0, 10.0)),
                    LinePrimitive(p0=(350.0, 10.0), p1=(450.0, 10.0)),
                    LinePrimitive(p0=(450.0, 10.0), p1=(450.0, 110.0)),
                    LinePrimitive(p0=(450.0, 110.0), p1=(350.0, 110.0)),
                    LinePrimitive(p0=(350.0, 110.0), p1=(350.0, 10.0)),
                ],
                texts=[],
            )
        ],
    )
    primitives_path = tmp_path / "primitives.json"
    primitives_path.write_text(primitives.model_dump_json(), "utf-8")
    graph_path = tmp_path / "entity_graph.json"

    result = CliRunner().invoke(
        app,
        [
            "build-graph",
            str(primitives_path),
            "-o",
            str(graph_path),
            "--sheet-region",
            "0,0,200,200",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(graph_path.read_text("utf-8"))
    assert len(payload["rooms"]) == 1
    assert payload["rooms"][0]["bbox"] == [10.0, 10.0, 110.0, 110.0]


def test_render_overlay_works_directly(sample_pdf: Path, tmp_path: Path) -> None:
    p = extract(sample_pdf)
    g = build_graph(p)
    out = render_overlay(g, sample_pdf, tmp_path / "ov.png", dpi=96)
    assert out.exists()
    assert out.stat().st_size > 0
