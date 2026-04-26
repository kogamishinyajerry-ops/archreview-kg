from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from archkg.cli.main import app
from archkg.graph.builder import build_graph, render_overlay
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


def test_render_overlay_works_directly(sample_pdf: Path, tmp_path: Path) -> None:
    p = extract(sample_pdf)
    g = build_graph(p)
    out = render_overlay(g, sample_pdf, tmp_path / "ov.png", dpi=96)
    assert out.exists()
    assert out.stat().st_size > 0
