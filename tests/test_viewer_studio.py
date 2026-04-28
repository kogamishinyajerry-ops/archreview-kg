"""Smoke tests for the Studio upload UI (Phase 19-B / v1.2.0).

Cover the routes a first-time user touches:
- GET /             -> the upload page renders
- GET /demo         -> bundled sample run produces a viewer index
- POST /review      -> uploaded PDF + YAMLs produce a viewer index
- GET /runs/<id>/   -> serves the produced index.html
- POST /review fail -> mismatched project_id flashes an error and redirects home

Tests run the Flask app via its test client; no real socket is opened.
"""

from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path

import pytest

from archkg.schemas import TextPrimitive
from archkg.viewer.studio import create_app, run_pipeline

REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_PDF = REPO_ROOT / "samples" / "sample_clean.pdf"
SAMPLE_META = REPO_ROOT / "samples" / "project_meta_demo.yaml"
SAMPLE_ROOM = REPO_ROOT / "samples" / "room_schedule_demo.yaml"
SAMPLE_STAIR = REPO_ROOT / "samples" / "stair_schedule_demo.yaml"
RASTER_FIXTURE_200DPI = (
    REPO_ROOT / "tests" / "fixtures" / "raster_suite" / "sample_raster_200dpi.png"
)


@pytest.fixture
def studio_client(tmp_path: Path):
    app = create_app(tmp_path)
    app.config.update(TESTING=True)
    with app.test_client() as client:
        yield client, tmp_path


def test_index_page_renders(studio_client) -> None:
    client, _ = studio_client
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.data.decode("utf-8")
    assert "ArchReview-KG Studio" in body
    assert "拖到这里" in body
    # The "Try the demo" button must exist or first-time visitors have no
    # zero-input path to see the tool work end-to-end.
    assert "/demo" in body


def test_demo_route_produces_viewer_index(studio_client) -> None:
    client, state_dir = studio_client
    resp = client.get("/demo")
    assert resp.status_code == 302
    redirect_target = resp.headers["Location"]
    assert redirect_target.startswith("/runs/demo-"), redirect_target

    follow = client.get(redirect_target)
    assert follow.status_code == 200, follow.data[:300]
    body = follow.data.decode("utf-8")
    # Viewer template (re-rendered by run_pipeline) signals.
    assert "ArchReview-KG" in body
    assert "审查报告" in body or "Demo Viewer" in body

    # Run dir was actually populated.
    run_id = redirect_target.removeprefix("/runs/").rstrip("/")
    run_dir = state_dir / "runs" / run_id
    assert (run_dir / "annotated.pdf").exists()
    assert (run_dir / "issues.json").exists()
    assert (run_dir / "report.md").exists()


def test_post_review_with_pdf_only_succeeds(studio_client) -> None:
    client, state_dir = studio_client
    pdf_bytes = SAMPLE_PDF.read_bytes()
    resp = client.post(
        "/review",
        data={"pdf": (BytesIO(pdf_bytes), "plan.pdf")},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 302, resp.data[:300]
    target = resp.headers["Location"]
    assert target.startswith("/runs/")

    follow = client.get(target)
    assert follow.status_code == 200
    body = follow.data.decode("utf-8")
    assert "规则输入就绪度" in body
    assert "缺输入不等于通过" in body
    assert "RC-ELEVATOR-REQUIRED" in body
    run_id = target.removeprefix("/runs/").rstrip("/")
    run_dir = state_dir / "runs" / run_id
    readiness = json.loads((run_dir / "rule_input_readiness.json").read_text("utf-8"))
    assert readiness["schema_version"] == "rule_input_readiness.v1"
    assert len(readiness["rules"]) == 32


def test_post_review_with_full_meta_and_schedules_succeeds(studio_client) -> None:
    client, state_dir = studio_client
    resp = client.post(
        "/review",
        data={
            "pdf": (BytesIO(SAMPLE_PDF.read_bytes()), "plan.pdf"),
            "project_meta": (BytesIO(SAMPLE_META.read_bytes()), "meta.yaml"),
            "room_schedule": (BytesIO(SAMPLE_ROOM.read_bytes()), "rooms.yaml"),
            "stair_schedule": (BytesIO(SAMPLE_STAIR.read_bytes()), "stairs.yaml"),
        },
        content_type="multipart/form-data",
    )
    assert resp.status_code == 302
    run_id = resp.headers["Location"].removeprefix("/runs/").rstrip("/")
    run_dir = state_dir / "runs" / run_id
    # The full-schedule path must produce more issues than PDF-only because
    # 4 PARTIAL_AUTODETECT and 5 STAIR_PENDING rules become evaluable.
    issues = (run_dir / "issues.json").read_text("utf-8")
    assert "RC-LIVING-BEDROOM-NETHEIGHT-2.4" in issues, (
        "room schedule must unlock the bedroom-net-height rule"
    )
    assert "RC-STAIR-FLIGHT-WIDTH-1.10" in issues, (
        "stair schedule must materialize a Stair entity that the rules can fire on"
    )
    understanding = json.loads((run_dir / "drawing_understanding.json").read_text("utf-8"))
    assert understanding["component_counts"]["stairs"] == 1
    assert understanding["components"]["vertical_circulation"][0]["id"] == "stair-1"
    assert any(
        row["semantic_kind"] == "stair" for row in understanding["component_inventory"]
    )
    index_text = (run_dir / "index.html").read_text("utf-8")
    assert "垂直交通" in index_text
    assert "识别档案" in index_text


def test_post_review_without_pdf_redirects_with_flash(studio_client) -> None:
    client, _ = studio_client
    resp = client.post(
        "/review",
        data={},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert resp.status_code == 200
    body = resp.data.decode("utf-8")
    assert "请上传 PDF" in body


def test_post_review_with_inspect_only_skips_rules(studio_client) -> None:
    """Phase 19-C: ``inspect_only`` form field runs ingest + build_graph
    but does NOT evaluate rules. Useful for sanity-checking the builder
    output on an unfamiliar PDF before trusting the rule report.

    Codex P19-C R1 P0: the result page must NOT look like a successful
    review. Concretely the rendered HTML must NOT show "0 issues
    flagged" / "✓ 未发现违反规则" / "标注 PDF"; it MUST show the
    "规则评估未执行" badge + "skipped" pipeline labels. Without this
    assertion the test silently passes even if a future template
    refactor regresses the messaging.
    """
    client, state_dir = studio_client
    resp = client.post(
        "/review",
        data={
            "pdf": (BytesIO(SAMPLE_PDF.read_bytes()), "plan.pdf"),
            "inspect_only": "1",
        },
        content_type="multipart/form-data",
    )
    assert resp.status_code == 302
    run_id = resp.headers["Location"].removeprefix("/runs/").rstrip("/")
    run_dir = state_dir / "runs" / run_id

    issues = (run_dir / "issues.json").read_text("utf-8")
    assert issues.strip() == "[]", "inspect_only must produce empty issues"
    report = (run_dir / "report.md").read_text("utf-8")
    assert "仅识图模式" in report
    # entity_graph + overlay still produced so the user can inspect.
    assert (run_dir / "entity_graph.json").exists()
    assert (run_dir / "entity_overlay.png").exists()

    # Render the viewer index.html through the studio and assert the
    # "rules did not run" messaging is unmissable.
    follow = client.get(f"/runs/{run_id}/")
    assert follow.status_code == 200
    body = follow.data.decode("utf-8")
    assert "规则评估未执行" in body, (
        "inspect_only result page must explicitly say rules were not "
        "evaluated; otherwise the user reads 'no violations found' as "
        "'plan is compliant'."
    )
    assert "0 issues flagged" not in body, (
        "the success-state badge must not render in inspect_only mode"
    )
    assert "未发现违反规则的实体" not in body, (
        "the green 'no violations' message implies a clean review and "
        "must not render when rules were skipped"
    )
    assert "skipped" in body  # pipeline steps 3-5 marked skipped
    assert "源图副本" in body  # annotated PDF section relabelled
    assert "Issues (规则未跑)" in body  # stat tile clearly marked N/A


def test_run_meta_persists_tunable_knobs(studio_client) -> None:
    """Codex P19-D R1 P2: ppm and min_room_area_m2 materially change
    outputs, so a user reporting unexpected entity counts must be able
    to debug from the run dir alone. Persist both in run_meta.json."""
    client, state_dir = studio_client
    resp = client.post(
        "/review",
        data={
            "pdf": (BytesIO(SAMPLE_PDF.read_bytes()), "plan.pdf"),
            "points_per_meter": "50.0",
            "min_room_area_m2": "2.5",
        },
        content_type="multipart/form-data",
    )
    assert resp.status_code == 302
    run_id = resp.headers["Location"].removeprefix("/runs/").rstrip("/")
    run_dir = state_dir / "runs" / run_id

    meta = json.loads((run_dir / "run_meta.json").read_text("utf-8"))
    assert meta["mode"] == "full"
    assert meta["points_per_meter"] == 50.0
    assert meta["min_room_area_m2"] == 2.5


def test_post_review_sheet_region_crops_primitives_and_persists_meta(
    studio_client,
) -> None:
    client, state_dir = studio_client
    resp = client.post(
        "/review",
        data={
            "pdf": (BytesIO(SAMPLE_PDF.read_bytes()), "plan.pdf"),
            "sheet_region": "0,0,200,400",
        },
        content_type="multipart/form-data",
    )
    assert resp.status_code == 302
    run_id = resp.headers["Location"].removeprefix("/runs/").rstrip("/")
    run_dir = state_dir / "runs" / run_id

    meta = json.loads((run_dir / "run_meta.json").read_text("utf-8"))
    assert meta["sheet_region"] == [0.0, 0.0, 200.0, 400.0]

    primitives = json.loads((run_dir / "primitives.json").read_text("utf-8"))
    texts = {text["text"] for text in primitives["pages"][0]["texts"]}
    assert "BEDROOM" in texts
    assert "LIVING" not in texts
    assert "KITCHEN" not in texts


def test_run_pipeline_renders_sheet_region_candidate_panel(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    run_pipeline(REPO_ROOT / "samples" / "generated_complex_titleblock.pdf", out_dir)

    candidates = json.loads((out_dir / "sheet_region_candidates.json").read_text("utf-8"))
    assert candidates["schema_version"] == "sheet_region_candidates.v1"
    assert any(
        candidate["kind"] == "title_block"
        for candidate in candidates["pages"][0]["candidates"]
    )
    assert (out_dir / "sheet_region_candidates_overlay.png").exists()

    html = (out_dir / "index.html").read_text("utf-8")
    assert "候选区域" in html
    assert "title_block" in html
    assert "sheet_region_candidates_overlay.png" in html
    assert "不自动裁剪" in html


def test_post_review_min_room_area_filter_passes_through(studio_client) -> None:
    """Phase 19-D: ``min_room_area_m2`` form field threads from the
    studio form into the builder's room-area noise filter. With a 100
    m² floor every demo room drops (largest is 20 m²), so the resulting
    issues list must be empty (no rules can fire if there are no rooms)
    and the run_meta entity counts must reflect the filter.
    """
    client, state_dir = studio_client
    resp = client.post(
        "/review",
        data={
            "pdf": (BytesIO(SAMPLE_PDF.read_bytes()), "plan.pdf"),
            "min_room_area_m2": "100.0",
        },
        content_type="multipart/form-data",
    )
    assert resp.status_code == 302
    run_id = resp.headers["Location"].removeprefix("/runs/").rstrip("/")
    run_dir = state_dir / "runs" / run_id

    issues = (run_dir / "issues.json").read_text("utf-8")
    # All 4 demo rooms are <= 20 m² so a 100 m² floor wipes them out.
    # Without rooms the room-targeted rules (RC-LIVING-BEDROOM-* etc.)
    # cannot fire — the report should not contain them.
    assert "RC-LIVING-BEDROOM-NETHEIGHT-2.4" not in issues, (
        "min_room_area filter must drop rooms before rules fire on them"
    )

    graph = json.loads((run_dir / "entity_graph.json").read_text("utf-8"))
    assert graph["rooms"] == [], (
        f"100 m² floor should drop all rooms but got {len(graph['rooms'])}"
    )


def test_post_review_invalid_min_room_area_flashes(studio_client) -> None:
    """Phase 19-D: form field guards against bad input (matches the
    ppm validation pattern from R1)."""
    client, _ = studio_client
    resp = client.post(
        "/review",
        data={
            "pdf": (BytesIO(SAMPLE_PDF.read_bytes()), "plan.pdf"),
            "min_room_area_m2": "abc",
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "min_room_area_m2" in resp.data.decode("utf-8")

    # Negative is also invalid.
    resp = client.post(
        "/review",
        data={
            "pdf": (BytesIO(SAMPLE_PDF.read_bytes()), "plan.pdf"),
            "min_room_area_m2": "-1.0",
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "min_room_area_m2" in resp.data.decode("utf-8")


def test_post_review_invalid_ppm_flashes(studio_client) -> None:
    """Phase 19-C: form ppm field guards against bad input."""
    client, _ = studio_client
    resp = client.post(
        "/review",
        data={
            "pdf": (BytesIO(SAMPLE_PDF.read_bytes()), "plan.pdf"),
            "points_per_meter": "abc",
        },
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "points_per_meter" in resp.data.decode("utf-8")


def test_quality_flags_trigger_on_oversegmented_graph(tmp_path: Path) -> None:
    """Phase 19-C: ensure the quality-flag computation is correctly wired
    to the entity counts. We don't have a noisy PDF in samples/, so this
    test directly exercises the helper with synthetic counts that cross
    the thresholds. Codex P19-C R1 P2 — the helper accepts both an
    EntityGraph and a dict (the dict path is exercised here with
    fabricated graphs)."""
    from archkg.viewer.studio import _compute_quality_flags

    # Below thresholds: only the "no corridor" flag fires when rooms > 0.
    no_corridor = _compute_quality_flags(
        {"rooms": [{"id": "r1"}], "doors": [], "corridors": []}
    )
    assert any("未检出 corridor" in f for f in no_corridor)
    assert not any("over-segmenting" in f for f in no_corridor)

    # Above thresholds: over-segmentation flags fire.
    busy = _compute_quality_flags(
        {
            "rooms": [{"id": f"r{i}"} for i in range(60)],
            "doors": [{"id": f"d{i}"} for i in range(80)],
            "corridors": [{"id": "c1"}],
        }
    )
    assert any("over-segmenting" in f for f in busy)
    assert any("gap 检测" in f for f in busy)
    assert not any("未检出 corridor" in f for f in busy)


def test_quality_flags_accepts_typed_entity_graph() -> None:
    """Codex P19-C R1 P2: the safer path is to take the in-memory typed
    EntityGraph rather than reload from JSON. Verify the helper handles
    both shapes (typed object + dict) so future serialisation changes
    can't silently neuter the safeguard."""
    from archkg.graph.builder import EntityGraph
    from archkg.viewer.studio import _compute_quality_flags

    graph = EntityGraph(
        source_pdf="x.pdf",
        points_per_meter=50.0,
        page_index=0,
        page_width_pt=500,
        page_height_pt=400,
        rooms=[],
        doors=[],
        corridors=[],
        dimensions=[],
    )
    # Empty graph → no flags (rooms == 0 doesn't trip the no-corridor flag).
    assert _compute_quality_flags(graph) == ()


def test_standalone_viewer_rerender_honours_inspect_only(tmp_path: Path) -> None:
    """Codex P19-C R2 P0: ``archkg viewer <run-dir>`` (the standalone
    static-server CLI, not the studio Flask app) re-renders index.html
    by reading the artifacts in the run dir. Before R2 it had no way to
    tell an inspect_only run apart from a "rules ran, 0 violations" run
    and produced a misleading green-success page.

    The fix persists ``run_meta.json`` next to the artifacts and
    teaches ``viewer.server._render_index`` to honour it. This test is
    the regression guard: if a future refactor drops the meta file or
    stops reading it, an inspect_only run will once again render as a
    clean-review page, and this test will fail.
    """
    from archkg.viewer.server import _render_index
    from archkg.viewer.studio import run_pipeline

    out_dir = tmp_path / "out"
    run_pipeline(SAMPLE_PDF, out_dir, inspect_only=True)
    # The studio's own pre-rendered index.html already passes the inspect
    # banner; we want to verify the SEPARATE re-render code path also does.
    index_path = _render_index(out_dir, SAMPLE_PDF)
    body = index_path.read_text("utf-8")

    assert "规则评估未执行" in body, (
        "viewer.server._render_index must honour run_meta.json mode; "
        "without it, archkg viewer re-renders inspect_only as a green "
        "'0 violations' page and misleads the user into thinking the "
        "plan was reviewed and is compliant."
    )
    assert "0 issues flagged" not in body
    assert "未发现违反规则的实体" not in body
    assert "skipped" in body
    assert "源图副本" in body
    assert "Issues (规则未跑)" in body


def test_standalone_viewer_rerender_without_readiness_artifact_degrades(
    tmp_path: Path,
) -> None:
    from archkg.viewer.server import _render_index
    from archkg.viewer.studio import run_pipeline

    out_dir = tmp_path / "out"
    run_pipeline(SAMPLE_PDF, out_dir)
    (out_dir / "rule_input_readiness.json").unlink()

    index_path = _render_index(out_dir, SAMPLE_PDF)
    body = index_path.read_text("utf-8")

    assert "规则输入就绪度暂无数据" in body
    assert "缺失 readiness 不代表通过" in body
    assert "Issues" in body


def test_standalone_viewer_renders_review_state_and_missing_state_warning(
    tmp_path: Path,
) -> None:
    from archkg.viewer.server import _render_index
    from archkg.viewer.studio import run_pipeline

    out_dir = tmp_path / "out"
    run_pipeline(SAMPLE_PDF, out_dir)
    state_path = out_dir / "review_state.json"
    state = json.loads(state_path.read_text("utf-8"))
    state["items"][0]["status"] = "resolved"
    state["items"][0]["reviewer"] = "Zhu"
    state["items"][0]["note"] = "fixed in rev B"
    state["summary"] = {"candidate": len(state["items"]) - 1, "resolved": 1}
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    index_path = _render_index(out_dir, SAMPLE_PDF)
    body = index_path.read_text("utf-8")

    assert "复核状态" in body
    assert "resolved" in body
    assert "fixed in rev B" in body

    state_path.unlink()
    index_path = _render_index(out_dir, SAMPLE_PDF)
    body = index_path.read_text("utf-8")

    assert "review_state.json 暂无数据" in body
    assert "缺失复核状态不代表已确认" in body


def test_standalone_viewer_renders_sheet_classification_and_missing_warning(
    tmp_path: Path,
) -> None:
    from archkg.viewer.server import _render_index
    from archkg.viewer.studio import run_pipeline

    out_dir = tmp_path / "out"
    run_pipeline(SAMPLE_PDF, out_dir)

    index_path = _render_index(out_dir, SAMPLE_PDF)
    body = index_path.read_text("utf-8")

    assert "Sheet 分类" in body
    assert "审图工作台总览" in body
    assert "Sheet 路由" in body
    assert "Sheet Graphs" in body
    assert "Sheet Issue Preview" in body
    assert "平面图" in body
    assert "review_workbench.json" in body
    assert "sheet_classification.json" in body
    assert "sheet_routing.json" in body
    assert "sheet_graphs.json" in body
    assert "sheet_issues.json" in body

    (out_dir / "sheet_classification.json").unlink()
    (out_dir / "sheet_routing.json").unlink()
    (out_dir / "sheet_graphs.json").unlink()
    (out_dir / "sheet_issues.json").unlink()
    (out_dir / "review_workbench.json").unlink()
    index_path = _render_index(out_dir, SAMPLE_PDF)
    body = index_path.read_text("utf-8")

    assert "review_workbench.json 暂无数据" in body
    assert "sheet_classification.json 暂无数据" in body
    assert "缺失分类不代表可直接进入 graph" in body
    assert "sheet_routing.json 暂无数据" in body
    assert "缺失路由不代表已按 sheet 类型过滤" in body
    assert "sheet_graphs.json 暂无数据" in body
    assert "缺失多页 graph 不代表没有其他 plan sheet" in body
    assert "sheet_issues.json 暂无数据" in body
    assert "缺失 per-sheet issue preview 不代表多页无候选问题" in body


def test_run_pipeline_extracts_walls_from_png(tmp_path: Path) -> None:
    """Phase 20-A: a 200-DPI raster render of the demo PDF should
    produce roughly the same entity counts (4 rooms / 1 corridor /
    6 doors) when fed through the CV ingest path. This is the
    first-class regression that 'PNG support actually works'.

    Differences from the vector path:
    - No OCR, so labels are absent (rules needing labels won't fire).
    - The points_per_meter must be in PIXELS per metre, not points.
      For a PDF at ppm=50 rendered to PNG at 200 DPI, that's
      50 * 200 / 72 ≈ 138.89.
    """
    import fitz

    png_path = tmp_path / "rendered.png"
    doc = fitz.open(SAMPLE_PDF)
    try:
        zoom = 200.0 / 72.0
        pix = doc[0].get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        pix.save(str(png_path))
    finally:
        doc.close()

    out = tmp_path / "out"
    result = run_pipeline(
        png_path,
        out,
        points_per_meter=50.0 * 200.0 / 72.0,
        min_room_area_m2=0.0,
    )
    # The CV pipeline isn't pixel-perfect; allow some slack but the
    # major topology must be right. The clean demo render produces
    # exactly 4/1/6 today; loosen if Hough params drift in future.
    assert result.room_count == 4, (
        f"expected 4 rooms from PNG render of demo PDF, got "
        f"{result.room_count}"
    )
    assert result.corridor_count == 1, (
        f"expected 1 corridor, got {result.corridor_count}"
    )
    assert result.door_count == 6, (
        f"expected 6 doors, got {result.door_count}"
    )

    # The wrapped PDF + standard artifacts must exist for the viewer.
    for fname in (
        "annotated.pdf",
        "entity_graph.json",
        "entity_overlay.png",
        "issues.json",
        "primitives.json",
        "report.md",
        "rule_input_readiness.json",
        "sheet_region_candidates.json",
        "sheet_region_candidates_overlay.png",
        "source.pdf",
        "source_preview.png",
    ):
        assert (out / fname).exists(), f"missing artifact for raster run: {fname}"


def test_run_pipeline_stable_topology_across_dpis(tmp_path: Path) -> None:
    """Codex P20-A R1 P0: same plan rendered at 100 / 150 / 200 / 300
    / 600 DPI must give the same topology (4 rooms, 1 corridor,
    6 doors). Pre-R1 the pixel-fixed CV heuristics produced
    different results at each DPI; the scale-normalized version
    derives every length-like constant from ``points_per_meter``.
    """
    import fitz

    counts: list[tuple[int, int, int, int]] = []
    for dpi in (100, 150, 200, 300, 600):
        png = tmp_path / f"r{dpi}.png"
        doc = fitz.open(SAMPLE_PDF)
        try:
            zoom = dpi / 72.0
            pix = doc[0].get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
            pix.save(str(png))
        finally:
            doc.close()
        ppm = 50.0 * dpi / 72.0
        out = tmp_path / f"out{dpi}"
        result = run_pipeline(png, out, points_per_meter=ppm, min_room_area_m2=0.0)
        counts.append((dpi, result.room_count, result.corridor_count, result.door_count))

    expected = (4, 1, 6)
    failures = [c for c in counts if c[1:] != expected]
    assert not failures, (
        f"topology should be stable across DPIs but {failures} differ from "
        f"{expected}; full sweep: {counts}"
    )


def test_post_review_image_dpi_compounds_with_ppm(studio_client) -> None:
    """Codex P20-A R1 P0: studio form must let users specify the
    image's render DPI separately from the source CAD's
    ``points_per_meter``. Posting a 300-DPI render with
    ``image_dpi=300`` should produce the same topology as the same
    plan at any other DPI.
    """
    import fitz

    client, state_dir = studio_client
    doc = fitz.open(SAMPLE_PDF)
    try:
        pix = doc[0].get_pixmap(matrix=fitz.Matrix(300 / 72, 300 / 72), alpha=False)
        png_bytes = pix.tobytes(output="png")
    finally:
        doc.close()

    resp = client.post(
        "/review",
        data={
            "pdf": (BytesIO(png_bytes), "plan.png"),
            "points_per_meter": "50.0",
            "image_dpi": "300",
            "min_room_area_m2": "0",
        },
        content_type="multipart/form-data",
    )
    assert resp.status_code == 302, resp.data[:300]
    run_id = resp.headers["Location"].removeprefix("/runs/").rstrip("/")
    run_dir = state_dir / "runs" / run_id

    graph = json.loads((run_dir / "entity_graph.json").read_text("utf-8"))
    assert len(graph["rooms"]) == 4, (
        f"PNG@300 DPI with image_dpi=300 should yield 4 rooms; got {len(graph['rooms'])}"
    )

    # Codex P20-A R1 P1 / R2 P1: the result page must warn that
    # raster inputs lack OCR AND must NOT recommend room_schedule.yaml
    # (which can't match label-less raster rooms by id/label).
    follow = client.get(f"/runs/{run_id}/")
    body = follow.data.decode("utf-8")
    assert "栅格图无 OCR" in body, (
        "raster runs must surface the no-OCR warning so users don't "
        "mistake an incomplete review for a complete one"
    )
    assert "room_schedule.yaml" not in body, (
        "warning must NOT recommend room_schedule.yaml — it selects by "
        "existing room_id/label which raster rooms don't have, and the "
        "advice would be a dead end (Codex P20-A R2 P1)"
    )

    # Codex P20-A R3 P1: the banner must name the *actual* 5 label-input
    # Room rules from rule_cards.yaml, not approximated/non-existent IDs,
    # and must not pretend a 13-18 rule range when it's exactly 5.
    expected_rule_ids = (
        "RC-BEDROOM-AREA",
        "RC-LIVING-BEDROOM-NETHEIGHT-2.4",
        "RC-PITCHED-ROOF-MAJORITY-NETHEIGHT-2.1",
        "RC-BASEMENT-MEZZANINE-NETHEIGHT-2.0",
        "RC-NO-LIVING-IN-BASEMENT",
    )
    for rid in expected_rule_ids:
        assert rid in body, f"banner must list real rule id {rid}"
    bogus_ids = (
        "RC-LIVING-BEDROOM-AREA-5",
        "RC-LIVING-BEDROOM-PITCHED-2.10",
        "RC-BASEMENT-LIVING-NOT-ALLOWED",
    )
    for rid in bogus_ids:
        assert rid not in body, (
            f"banner must not reference non-existent rule id {rid} "
            "(Codex P20-A R3 P1)"
        )
    assert "13-18" not in body, (
        "banner must not approximate rule count when the precise number "
        "is 5 (Codex P20-A R3 P1)"
    )


def test_post_review_raster_use_ocr_persists_texts_and_clears_no_ocr_warning(
    studio_client,
    monkeypatch,
) -> None:
    """Phase 20-B: studio passes the OCR toggle into raster ingest.

    The test monkeypatches PaddleOCR's boundary so it is deterministic
    and does not require the heavyweight optional dependency in CI.
    """
    import fitz

    from archkg.ingest import raster_extractor

    client, state_dir = studio_client

    def fake_ocr_page_image(
        image_path: Path,
        *,
        keep_only_dimensions: bool = True,
        lang: str = "ch",
    ) -> list[TextPrimitive]:
        del image_path, lang
        assert keep_only_dimensions is False
        return [
            TextPrimitive(
                text="卧室",
                bbox=(140.0, 140.0, 180.0, 170.0),
                source="ocr",
                confidence=0.93,
            )
        ]

    monkeypatch.setattr(raster_extractor.ocr, "ocr_page_image", fake_ocr_page_image)

    doc = fitz.open(SAMPLE_PDF)
    try:
        pix = doc[0].get_pixmap(matrix=fitz.Matrix(200 / 72, 200 / 72), alpha=False)
        png_bytes = pix.tobytes(output="png")
    finally:
        doc.close()

    resp = client.post(
        "/review",
        data={
            "pdf": (BytesIO(png_bytes), "plan.png"),
            "points_per_meter": "50.0",
            "image_dpi": "200",
            "min_room_area_m2": "0",
            "use_ocr": "1",
        },
        content_type="multipart/form-data",
    )
    assert resp.status_code == 302, resp.data[:300]
    run_id = resp.headers["Location"].removeprefix("/runs/").rstrip("/")
    run_dir = state_dir / "runs" / run_id

    primitives = json.loads((run_dir / "primitives.json").read_text("utf-8"))
    assert primitives["pages"][0]["texts"][0]["text"] == "卧室"
    assert primitives["pages"][0]["texts"][0]["source"] == "ocr"

    meta = json.loads((run_dir / "run_meta.json").read_text("utf-8"))
    assert meta["use_ocr"] is True
    assert meta["ocr_text_count"] == 1
    assert any("栅格图 OCR beta" in flag for flag in meta["quality_flags"])
    assert not any("栅格图无 OCR" in flag for flag in meta["quality_flags"])

    follow = client.get(f"/runs/{run_id}/")
    body = follow.data.decode("utf-8")
    assert "栅格图 OCR beta" in body
    assert "栅格图无 OCR" not in body


def test_post_review_raster_ocr_evidence_panel_and_standalone_rerender(
    studio_client,
    monkeypatch,
) -> None:
    """Phase 20-C: OCR beta must be auditable on the result page.

    It is not enough to say "OCR ran"; the viewer needs to expose the
    OCR text, confidence, and room binding hints. The same diagnostics
    must survive standalone ``archkg viewer`` re-rendering from run
    artifacts.
    """
    import fitz

    from archkg.ingest import raster_extractor
    from archkg.viewer.server import _render_index

    client, state_dir = studio_client

    def fake_ocr_page_image(
        image_path: Path,
        *,
        keep_only_dimensions: bool = True,
        lang: str = "ch",
    ) -> list[TextPrimitive]:
        del image_path, lang
        assert keep_only_dimensions is False
        return [
            TextPrimitive(
                text="卧室",
                bbox=(140.0, 140.0, 180.0, 170.0),
                source="ocr",
                confidence=0.93,
            ),
            TextPrimitive(
                text="厨房",
                bbox=(190.0, 140.0, 230.0, 170.0),
                source="ocr",
                confidence=0.91,
            ),
            TextPrimitive(
                text="客厅",
                bbox=(5000.0, 5000.0, 5030.0, 5020.0),
                source="ocr",
                confidence=0.95,
            ),
            TextPrimitive(
                text="卫生间",
                bbox=(5200.0, 5200.0, 5230.0, 5220.0),
                source="ocr",
                confidence=0.42,
            ),
        ]

    monkeypatch.setattr(raster_extractor.ocr, "ocr_page_image", fake_ocr_page_image)

    doc = fitz.open(SAMPLE_PDF)
    try:
        pix = doc[0].get_pixmap(matrix=fitz.Matrix(200 / 72, 200 / 72), alpha=False)
        png_bytes = pix.tobytes(output="png")
    finally:
        doc.close()

    resp = client.post(
        "/review",
        data={
            "pdf": (BytesIO(png_bytes), "plan.png"),
            "points_per_meter": "50.0",
            "image_dpi": "200",
            "min_room_area_m2": "0",
            "use_ocr": "1",
        },
        content_type="multipart/form-data",
    )
    assert resp.status_code == 302, resp.data[:300]
    run_id = resp.headers["Location"].removeprefix("/runs/").rstrip("/")
    run_dir = state_dir / "runs" / run_id

    follow = client.get(f"/runs/{run_id}/")
    body = follow.data.decode("utf-8")
    assert "OCR 证据面" in body
    assert "OCR 文本" in body
    assert "低置信度" in body
    assert "卧室" in body
    assert "厨房" in body
    assert "客厅" in body
    assert "卫生间" in body
    assert "已绑定房间" in body
    assert "未绑定" in body
    assert "OCR label QA 候选" in body
    assert "label 冲突" in body
    assert "未绑定高置信度 label" in body
    assert "低置信度 label" in body

    index_path = _render_index(run_dir, run_dir / "source.pdf")
    rerendered = index_path.read_text("utf-8")
    assert "OCR 证据面" in rerendered
    assert "卧室" in rerendered
    assert "厨房" in rerendered
    assert "客厅" in rerendered
    assert "低置信度" in rerendered
    assert "OCR label QA 候选" in rerendered


def _p21_fixture_ocr_texts() -> list[TextPrimitive]:
    """Deterministic OCR payload for fixture-based raster regression tests."""
    return [
        TextPrimitive(
            text="卧室",
            bbox=(820.0, 130.0, 900.0, 170.0),
            source="ocr",
            confidence=0.95,
        ),
        TextPrimitive(
            text="厨房",
            bbox=(200.0, 120.0, 270.0, 170.0),
            source="ocr",
            confidence=0.95,
        ),
        TextPrimitive(
            text="客厅",
            bbox=(800.0, 840.0, 900.0, 890.0),
            source="ocr",
            confidence=0.95,
        ),
        TextPrimitive(
            text="卫生间",
            bbox=(200.0, 840.0, 280.0, 890.0),
            source="ocr",
            confidence=0.95,
        ),
        TextPrimitive(
            text="卧室",
            bbox=(810.0, 140.0, 900.0, 180.0),
            source="ocr",
            confidence=0.45,
        ),
        TextPrimitive(
            text="厨房",
            bbox=(1500.0, 1500.0, 1580.0, 1580.0),
            source="ocr",
            confidence=0.96,
        ),
        TextPrimitive(
            text="DOOR 0.77",
            bbox=(1118.0, 675.0, 1160.0, 695.0),
            source="ocr",
            confidence=0.94,
        ),
    ]


def test_post_review_raster_fixture_ocr_candidate_panel_and_json_signal(
    studio_client,
    monkeypatch,
) -> None:
    """P21: lock OCR evidence panel + candidate accounting on a real raster fixture.

    The fixture is a real 200-DPI rendered input (not synthetic geometry),
    while OCR remains deterministic via monkeypatch so CI stays dependency-free.
    """
    import json

    from archkg.ingest import raster_extractor
    from archkg.viewer.ocr_diagnostics import build_ocr_diagnostics
    from archkg.viewer.server import _render_index

    client, state_dir = studio_client
    ocr_texts = _p21_fixture_ocr_texts()

    def fake_ocr_page_image(
        image_path: Path,
        *,
        keep_only_dimensions: bool = True,
        lang: str = "ch",
    ) -> list[TextPrimitive]:
        del image_path, lang
        assert keep_only_dimensions is False
        return ocr_texts

    monkeypatch.setattr(raster_extractor.ocr, "ocr_page_image", fake_ocr_page_image)

    resp = client.post(
        "/review",
        data={
            "pdf": (BytesIO(RASTER_FIXTURE_200DPI.read_bytes()), "sample_raster_200dpi.png"),
            "points_per_meter": "50.0",
            "image_dpi": "200",
            "min_room_area_m2": "0",
            "use_ocr": "1",
        },
        content_type="multipart/form-data",
    )
    assert resp.status_code == 302, resp.data[:300]
    run_id = resp.headers["Location"].removeprefix("/runs/").rstrip("/")
    run_dir = state_dir / "runs" / run_id

    follow = client.get(f"/runs/{run_id}/")
    body = follow.data.decode("utf-8")
    assert "OCR 证据面" in body
    assert "OCR label QA 候选" in body
    assert "OCR 尺寸绑定证据" in body
    assert "DOOR 0.77" in body
    assert "绑定 Door" in body
    assert "低置信度 label" in body
    assert "未绑定高置信度 label" in body
    assert "不会自动修改 Room.label，也不会改变规则结论" in body

    primitives = json.loads((run_dir / "primitives.json").read_text("utf-8"))
    graph = json.loads((run_dir / "entity_graph.json").read_text("utf-8"))
    diagnostics = build_ocr_diagnostics(primitives, graph)
    assert diagnostics["text_count"] == len(ocr_texts)
    assert diagnostics["qa_candidate_count"] == 2
    assert diagnostics["low_confidence_label_count"] == 1
    assert diagnostics["unbound_high_confidence_label_count"] == 1
    assert diagnostics["dimension_text_count"] == 1
    assert diagnostics["bound_dimension_count"] == 1
    assert diagnostics["dimension_rows"][0]["text"] == "DOOR 0.77"
    assert diagnostics["dimension_rows"][0]["target_kind"] == "Door"
    # QA candidates should stay in evidence view, not become rule outcomes.
    issues = (run_dir / "issues.json").read_text("utf-8")
    assert "label 冲突" not in issues
    assert "低置信度" not in issues

    index_text = _render_index(run_dir, run_dir / "source.pdf").read_text("utf-8")
    assert "OCR 证据面" in index_text
    assert "OCR label QA 候选" in index_text
    assert "OCR 尺寸绑定证据" in index_text


def test_post_review_raster_fixture_writes_drawing_understanding(
    studio_client,
    monkeypatch,
) -> None:
    """P23: first explain the drawing, then worry about compliance."""
    from archkg.ingest import raster_extractor
    from archkg.viewer.server import _render_index

    client, state_dir = studio_client
    ocr_texts = _p21_fixture_ocr_texts()

    def fake_ocr_page_image(
        image_path: Path,
        *,
        keep_only_dimensions: bool = True,
        lang: str = "ch",
    ) -> list[TextPrimitive]:
        del image_path, lang
        assert keep_only_dimensions is False
        return ocr_texts

    monkeypatch.setattr(raster_extractor.ocr, "ocr_page_image", fake_ocr_page_image)

    resp = client.post(
        "/review",
        data={
            "pdf": (BytesIO(RASTER_FIXTURE_200DPI.read_bytes()), "sample_raster_200dpi.png"),
            "points_per_meter": "50.0",
            "image_dpi": "200",
            "min_room_area_m2": "0",
            "use_ocr": "1",
        },
        content_type="multipart/form-data",
    )
    assert resp.status_code == 302, resp.data[:300]
    run_id = resp.headers["Location"].removeprefix("/runs/").rstrip("/")
    run_dir = state_dir / "runs" / run_id

    understanding = json.loads(
        (run_dir / "drawing_understanding.json").read_text("utf-8")
    )
    assert understanding["drawing_type"] == "建筑平面图"
    assert "平面图" in understanding["likely_design"]
    assert understanding["component_counts"]["rooms"] >= 1
    assert understanding["component_counts"]["doors"] >= 1
    assert understanding["components"]["spaces"]
    assert understanding["components"]["openings"]
    assert understanding["dimension_evidence"]["ocr_bound_count"] >= 1
    assert "规范" not in understanding["summary"]

    body = client.get(f"/runs/{run_id}/").data.decode("utf-8")
    assert "图纸理解摘要" in body
    assert "建筑平面图" in body
    assert "部件清单" in body
    assert "尺寸证据" in body

    index_text = _render_index(run_dir, run_dir / "source.pdf").read_text("utf-8")
    assert "图纸理解摘要" in index_text
    assert "部件清单" in index_text


def test_get_index_drop_hint_no_false_room_schedule_remediation(studio_client) -> None:
    """Codex P20-A R3 P1 + R4 P1: the upload-page must not tell raster
    users that room_schedule.yaml can unlock anything for them. The
    schedule selector keys on existing room_id/label, which raster
    rooms lack, so any such suggestion is a dead end. R4 widened this
    to cover the capability bullet and the accordion summary, both of
    which previously promised raster users a fix path that does not
    exist."""
    client, _ = studio_client
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.data.decode("utf-8")
    assert "需要标签触发的规则需 room_schedule.yaml 补充" not in body, (
        "drop-hint must not recommend room_schedule.yaml for raster — "
        "the schedule cannot match label-less raster rooms (R3 P1)"
    )
    # R4 P1: capability bullet must qualify schedule as vector-only.
    assert "填房间排表 YAML 解锁 4 张净高 / 楼层 / 坡屋顶规则（仅矢量 PDF" in body, (
        "capability bullet must qualify room_schedule.yaml as vector-only "
        "so raster users don't expect it to unlock those 4 rules (R4 P1)"
    )
    # R4 P1: accordion summary must qualify itself as vector-only.
    assert "解锁 4 张净高 / 楼层 / 坡屋顶规则；仅矢量 PDF" in body, (
        "room_schedule accordion summary must mark itself vector-only (R4 P1)"
    )


def test_post_review_invalid_image_dpi_flashes(studio_client) -> None:
    """Codex P20-A R1 P0: bad image_dpi flashes an error rather than
    silently using a wrong default."""
    client, _ = studio_client
    pdf_bytes = SAMPLE_PDF.read_bytes()
    # Note: PDF upload should ignore image_dpi. Test only raster path.
    import fitz

    doc = fitz.open(SAMPLE_PDF)
    try:
        pix = doc[0].get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        png_bytes = pix.tobytes(output="png")
    finally:
        doc.close()

    for bad in ("xyz", "-50"):
        resp = client.post(
            "/review",
            data={
                "pdf": (BytesIO(png_bytes), "plan.png"),
                "image_dpi": bad,
            },
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert "image_dpi" in resp.data.decode("utf-8")
    # PDF upload should NOT bother validating image_dpi (it's ignored).
    resp = client.post(
        "/review",
        data={
            "pdf": (BytesIO(pdf_bytes), "plan.pdf"),
            "image_dpi": "xyz",
        },
        content_type="multipart/form-data",
    )
    assert resp.status_code == 302, "PDF upload must ignore image_dpi"


def test_post_review_accepts_png_upload(studio_client) -> None:
    """Phase 20-A: studio /review accepts a PNG upload, runs the CV
    pipeline, and produces the same set of viewer artifacts as a PDF.
    """
    import fitz

    client, state_dir = studio_client
    # Render the sample PDF to PNG bytes.
    doc = fitz.open(SAMPLE_PDF)
    try:
        pix = doc[0].get_pixmap(matrix=fitz.Matrix(200 / 72, 200 / 72), alpha=False)
        png_bytes = pix.tobytes(output="png")
    finally:
        doc.close()

    resp = client.post(
        "/review",
        data={
            "pdf": (BytesIO(png_bytes), "plan.png"),
            "points_per_meter": str(50.0 * 200.0 / 72.0),
            "min_room_area_m2": "0",
        },
        content_type="multipart/form-data",
    )
    assert resp.status_code == 302, resp.data[:300]
    run_id = resp.headers["Location"].removeprefix("/runs/").rstrip("/")
    run_dir = state_dir / "runs" / run_id

    graph = json.loads((run_dir / "entity_graph.json").read_text("utf-8"))
    assert len(graph["rooms"]) > 0, "PNG upload produced 0 rooms"

    follow = client.get(f"/runs/{run_id}/")
    assert follow.status_code == 200


def test_post_review_rejects_unsupported_extension(studio_client) -> None:
    """Phase 20-A: a .gif (or any unrecognised extension) flashes an
    explicit error rather than silently treating the upload as PDF."""
    client, _ = studio_client
    resp = client.post(
        "/review",
        data={"pdf": (BytesIO(b"not a real gif"), "plan.gif")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert resp.status_code == 200
    body = resp.data.decode("utf-8")
    assert "不支持的文件类型" in body
    assert ".gif" in body


def test_run_pipeline_smoke(tmp_path: Path) -> None:
    """Direct entry-point check — used by both /review and /demo. Catches
    the case where the studio HTML works but the pipeline itself broke."""
    out_dir = tmp_path / "out"
    result = run_pipeline(
        SAMPLE_PDF,
        out_dir,
        project_meta_path=SAMPLE_META,
        room_schedule_path=SAMPLE_ROOM,
        stair_schedule_path=SAMPLE_STAIR,
    )
    assert result.issues_count > 0
    assert result.error_count > 0  # demo PDF intentionally has violations
    for fname in (
        "annotated.pdf",
        "annotated_preview.png",
        "entity_graph.json",
        "entity_overlay.png",
        "index.html",
        "issues.json",
        "primitives.json",
        "report.md",
        "source.pdf",
        "source_preview.png",
    ):
        assert (out_dir / fname).exists(), f"missing artifact: {fname}"
