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

from io import BytesIO
from pathlib import Path

import pytest

from archkg.viewer.studio import create_app, run_pipeline

REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_PDF = REPO_ROOT / "samples" / "sample_clean.pdf"
SAMPLE_META = REPO_ROOT / "samples" / "project_meta_demo.yaml"
SAMPLE_ROOM = REPO_ROOT / "samples" / "room_schedule_demo.yaml"
SAMPLE_STAIR = REPO_ROOT / "samples" / "stair_schedule_demo.yaml"


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
    client, _ = studio_client
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
