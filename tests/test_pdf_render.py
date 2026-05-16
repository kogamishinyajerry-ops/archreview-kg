"""Tests for archkg.kg.pdf_render (M7.W1 PDF viewport)."""

from __future__ import annotations

from pathlib import Path

import pytest

from archkg.kg.pdf_render import (
    DEFAULT_DPI,
    _png_dimensions,
    render_page,
    resolve_pdf_for_drawing,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_PDF = REPO_ROOT / "samples" / "real_plans" / "cambridge-343medford-overview.pdf"


@pytest.mark.skipif(not SAMPLE_PDF.exists(), reason="real plan PDF not committed locally")
def test_render_returns_real_png_with_known_dimensions(tmp_path: Path) -> None:
    """Page 0 of the cambridge medford overview must render to a valid PNG
    matching the page's rotated dimensions."""
    rp = render_page(SAMPLE_PDF, page_index=0, dpi=DEFAULT_DPI, repo_root=tmp_path)
    assert rp.image_bytes.startswith(b"\x89PNG\r\n\x1a\n")
    assert rp.image_width_px > 0 and rp.image_height_px > 0
    # Known: this PDF is rotated 90deg, post-rotation page rect is 2592 x 1728 pts.
    assert abs(rp.page_width_pts - 2592.0) < 1.0
    assert abs(rp.page_height_pts - 1728.0) < 1.0
    assert rp.rotation_degrees == 90
    # At 144 dpi (2x), the rendered image should be 5184 x 3456.
    expected_w = int(rp.page_width_pts * (DEFAULT_DPI / 72.0))
    expected_h = int(rp.page_height_pts * (DEFAULT_DPI / 72.0))
    assert abs(rp.image_width_px - expected_w) <= 2
    assert abs(rp.image_height_px - expected_h) <= 2
    assert rp.cache_path.exists()


@pytest.mark.skipif(not SAMPLE_PDF.exists(), reason="real plan PDF not committed locally")
def test_render_uses_cache_on_second_call(tmp_path: Path) -> None:
    rp1 = render_page(SAMPLE_PDF, page_index=0, repo_root=tmp_path)
    mtime1 = rp1.cache_path.stat().st_mtime_ns
    # Second call should hit the cache (no re-render). We assert the cache
    # file was not rewritten by checking the mtime is unchanged.
    rp2 = render_page(SAMPLE_PDF, page_index=0, repo_root=tmp_path)
    mtime2 = rp2.cache_path.stat().st_mtime_ns
    assert mtime1 == mtime2
    assert rp1.image_bytes == rp2.image_bytes


def test_render_raises_on_missing_pdf(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        render_page(tmp_path / "nope.pdf", page_index=0, repo_root=tmp_path)


@pytest.mark.skipif(not SAMPLE_PDF.exists(), reason="real plan PDF not committed locally")
def test_render_raises_on_out_of_range_page(tmp_path: Path) -> None:
    with pytest.raises(IndexError):
        render_page(SAMPLE_PDF, page_index=999, repo_root=tmp_path)


def test_png_dimensions_parses_header() -> None:
    # Build a minimal PNG header
    png = (
        b"\x89PNG\r\n\x1a\n"  # magic
        b"\x00\x00\x00\rIHDR"  # IHDR chunk header (length=13, type=IHDR)
        + (1920).to_bytes(4, "big")
        + (1080).to_bytes(4, "big")
        + b"\x08\x02\x00\x00\x00"  # bit depth, color type, etc.
    )
    w, h = _png_dimensions(png)
    assert (w, h) == (1920, 1080)


def test_png_dimensions_rejects_garbage() -> None:
    with pytest.raises(ValueError, match="not a valid PNG"):
        _png_dimensions(b"hello world")


def test_resolve_finds_samples_real_plans_by_slug(tmp_path: Path) -> None:
    real_dir = tmp_path / "samples" / "real_plans"
    real_dir.mkdir(parents=True)
    pdf_at_slug = real_dir / "my-project.pdf"
    pdf_at_slug.write_bytes(b"%PDF-1.4 fake")
    found = resolve_pdf_for_drawing(tmp_path, "my-project", "<unknown-source-for:my_project_run>")
    assert found == pdf_at_slug


def test_resolve_returns_none_when_no_match(tmp_path: Path) -> None:
    found = resolve_pdf_for_drawing(tmp_path, "no-such", "<unknown-source-for:nope>")
    assert found is None


def test_resolve_uses_explicit_source_path_when_real(tmp_path: Path) -> None:
    pdf = tmp_path / "elsewhere.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    found = resolve_pdf_for_drawing(tmp_path, "any-slug", str(pdf))
    assert found == pdf


@pytest.mark.skipif(not SAMPLE_PDF.exists(), reason="real plan PDF not committed locally")
def test_web_drawing_page_png_endpoint_returns_png(tmp_path: Path) -> None:
    """Integration: the Flask endpoint should serve the rendered PNG."""
    # Build a tiny KG with one drawing pointing at the real PDF (via slug).
    import sqlite3

    from archkg.kg.web import create_app

    db = tmp_path / "kg.db"
    repo_dir = tmp_path / "repo"
    (repo_dir / "samples" / "real_plans").mkdir(parents=True)
    target_pdf = repo_dir / "samples" / "real_plans" / "test-slug.pdf"
    target_pdf.write_bytes(SAMPLE_PDF.read_bytes())
    (repo_dir / ".archkg").mkdir()
    db = repo_dir / ".archkg" / "kg.db"
    # Init schema
    from archkg.kg.store import KGStore

    now = "2026-05-16T00:00:00Z"
    with KGStore(db, create=True) as store:
        store._conn.execute(
            "INSERT INTO project(slug, name, created_at) VALUES (?, ?, ?)",
            ("test-slug", "Test", now),
        )
        pid = store._conn.execute("SELECT id FROM project").fetchone()["id"]
        store._conn.execute(
            "INSERT INTO drawing(project_id, source_path, page_count, created_at) VALUES (?, ?, ?, ?)",
            (pid, "<unknown>", 1, now),
        )
        did = store._conn.execute("SELECT id FROM drawing").fetchone()["id"]
    app = create_app(db_path=db)
    client = app.test_client()
    r = client.get(f"/api/drawings/{did}/page/0.png")
    assert r.status_code == 200
    assert r.mimetype == "image/png"
    assert r.data.startswith(b"\x89PNG\r\n\x1a\n")
    # And bboxes endpoint returns at least the dim info (empty bbox list since no issues)
    b = client.get(f"/api/drawings/{did}/page/0/bboxes")
    assert b.status_code == 200
    data = b.get_json()
    assert data["drawing_id"] == did
    assert abs(data["page_width_pts"] - 2592.0) < 1.0
    assert isinstance(data["bboxes"], list)
    # Also verify the 404 path: nonexistent drawing
    nf = client.get("/api/drawings/9999/page/0.png")
    assert nf.status_code == 404
