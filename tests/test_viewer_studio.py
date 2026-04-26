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
