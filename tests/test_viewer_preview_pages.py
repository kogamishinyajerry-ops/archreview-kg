from __future__ import annotations

from pathlib import Path

from archkg.viewer.preview_pages import (
    load_preview_pages_view,
    render_pdf_preview_pages,
    write_preview_pages_manifest,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
MULTI_PAGE_PDF = REPO_ROOT / "samples" / "generated_complex_sheet_set.pdf"


def test_render_pdf_preview_pages_writes_page_set_manifest(tmp_path: Path) -> None:
    source_pages = render_pdf_preview_pages(
        MULTI_PAGE_PDF,
        tmp_path,
        layer="source",
        legacy_name="source_preview.png",
        dpi=24,
    )

    assert len(source_pages) == 4
    assert source_pages[0]["page_index"] == 0
    assert source_pages[0]["src"] == "source_preview.png"
    assert source_pages[1]["page_index"] == 1
    assert source_pages[1]["src"] == "source_preview_page_2.png"
    assert (tmp_path / "source_preview.png").exists()
    assert (tmp_path / "source_preview_page_2.png").exists()

    write_preview_pages_manifest(
        tmp_path,
        source_pages=source_pages,
        annotated_pages=[],
        overlay_available=False,
    )
    view = load_preview_pages_view(tmp_path)

    assert view["available"] is True
    assert view["page_count"] == 4
    assert view["layers"]["source"][1]["page_number"] == 2
    assert view["layers"]["annotated"] == []
    assert view["warning_text"] == "多页 source preview 可用; annotated preview 暂无多页页集。"
