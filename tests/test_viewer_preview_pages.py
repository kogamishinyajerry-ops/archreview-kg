from __future__ import annotations

from pathlib import Path

from archkg.viewer.preview_pages import (
    load_preview_pages_view,
    render_entity_overlay_preview_pages,
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


def test_render_entity_overlay_preview_pages_writes_page_set_manifest(
    tmp_path: Path,
) -> None:
    from archkg.graph.builder import EntityGraph
    from archkg.schemas import Room

    graph_page_0 = EntityGraph(
        source_pdf=str(MULTI_PAGE_PDF),
        points_per_meter=50.0,
        page_index=0,
        page_width_pt=1120.0,
        page_height_pt=700.0,
        rooms=[
            Room(
                id="R-0",
                page_index=0,
                bbox=(100.0, 100.0, 200.0, 200.0),
                polygon=[
                    (100.0, 100.0),
                    (200.0, 100.0),
                    (200.0, 200.0),
                    (100.0, 200.0),
                ],
                area_m2=4.0,
            )
        ],
        doors=[],
        corridors=[],
        dimensions=[],
    )
    graph_page_1 = graph_page_0.model_copy(
        update={
            "page_index": 1,
            "rooms": [
                Room(
                    id="R-1",
                    page_index=1,
                    bbox=(120.0, 120.0, 220.0, 220.0),
                    polygon=[
                        (120.0, 120.0),
                        (220.0, 120.0),
                        (220.0, 220.0),
                        (120.0, 220.0),
                    ],
                    area_m2=4.0,
                )
            ],
        }
    )

    overlay_pages = render_entity_overlay_preview_pages(
        MULTI_PAGE_PDF,
        tmp_path,
        graphs=[graph_page_0, graph_page_1],
        dpi=24,
    )

    assert [page["page_index"] for page in overlay_pages] == [0, 1]
    assert overlay_pages[0]["src"] == "entity_overlay.png"
    assert overlay_pages[1]["src"] == "entity_overlay_page_2.png"
    assert (tmp_path / "entity_overlay.png").exists()
    assert (tmp_path / "entity_overlay_page_2.png").exists()

    write_preview_pages_manifest(
        tmp_path,
        source_pages=[],
        annotated_pages=[],
        overlay_pages=overlay_pages,
    )
    view = load_preview_pages_view(tmp_path)

    assert view["page_count"] == 2
    assert view["layers"]["overlay"][1]["page_number"] == 2
    assert view["warning_text"] == "多页 entity overlay preview 可用。"
