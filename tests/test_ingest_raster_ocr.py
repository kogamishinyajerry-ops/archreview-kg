from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from archkg.graph.builder import build_graph
from archkg.ingest import raster_extractor
from archkg.schemas import LinePrimitive, PagePrimitives, Primitives, TextPrimitive


def _write_simple_plan_png(path: Path) -> None:
    img = Image.new("L", (160, 160), color=255)
    draw = ImageDraw.Draw(img)
    draw.rectangle((30, 30, 130, 130), outline=0, width=3)
    img.save(path)


def test_raster_extract_includes_ocr_text_only_when_enabled(
    tmp_path: Path,
    monkeypatch,
) -> None:
    image_path = tmp_path / "plan.png"
    _write_simple_plan_png(image_path)
    fake_text = TextPrimitive(
        text="卧室",
        bbox=(70.0, 70.0, 90.0, 90.0),
        source="ocr",
        confidence=0.91,
    )
    calls: list[tuple[Path, bool]] = []

    def fake_ocr_page_image(
        path: Path,
        *,
        keep_only_dimensions: bool = True,
        lang: str = "ch",
    ) -> list[TextPrimitive]:
        del lang
        calls.append((path, keep_only_dimensions))
        return [fake_text]

    monkeypatch.setattr(raster_extractor.ocr, "ocr_page_image", fake_ocr_page_image)

    without_ocr = raster_extractor.extract(image_path, points_per_meter=50.0)
    assert without_ocr.pages[0].texts == []
    assert calls == []

    with_ocr = raster_extractor.extract(
        image_path,
        points_per_meter=50.0,
        use_ocr=True,
    )
    assert with_ocr.pages[0].texts == [fake_text]
    assert calls == [(image_path, False)], (
        "raster OCR must keep label text, not only dimension strings"
    )


def test_ocr_text_primitives_bind_to_room_labels() -> None:
    primitives = Primitives(
        source_pdf="ocr.png",
        points_per_meter=50.0,
        pages=[
            PagePrimitives(
                page_index=0,
                width_pt=140.0,
                height_pt=140.0,
                lines=[
                    LinePrimitive(p0=(20.0, 20.0), p1=(120.0, 20.0)),
                    LinePrimitive(p0=(120.0, 20.0), p1=(120.0, 120.0)),
                    LinePrimitive(p0=(120.0, 120.0), p1=(20.0, 120.0)),
                    LinePrimitive(p0=(20.0, 120.0), p1=(20.0, 20.0)),
                ],
                texts=[
                    TextPrimitive(
                        text="主卧室",
                        bbox=(58.0, 58.0, 82.0, 76.0),
                        source="ocr",
                        confidence=0.88,
                    )
                ],
            )
        ],
    )

    graph = build_graph(primitives)

    assert len(graph.rooms) == 1
    assert graph.rooms[0].label == "bedroom"
    assert graph.rooms[0].uncertain is False
    assert graph.rooms[0].confidence == 0.85
