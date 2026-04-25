from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from archkg.cli.main import app
from archkg.ingest import ocr
from archkg.ingest.pdf_loader import extract_pages
from archkg.ingest.primitive_extractor import extract, write_json


def test_pdf_loader_extracts_lines_and_texts(sample_pdf: Path) -> None:
    pages = extract_pages(sample_pdf)
    assert len(pages) == 1
    page = pages[0]
    # outer rect (4) + mid-wall (4) + horiz corridor walls (6) = 14 line segments
    assert len(page.lines) >= 12
    text_blob = " ".join(t.text for t in page.texts)
    assert "BEDROOM" in text_blob
    assert "CORRIDOR" in text_blob
    assert "DOOR" in text_blob


def test_extract_returns_well_formed_primitives(sample_pdf: Path) -> None:
    p = extract(sample_pdf, points_per_meter=50.0)
    assert p.points_per_meter == 50.0
    assert p.source_pdf == str(sample_pdf)
    assert len(p.pages) == 1
    assert all(t.source == "vector" for t in p.pages[0].texts)


def test_write_json_is_pydantic_round_trip(sample_pdf: Path, tmp_path: Path) -> None:
    p = extract(sample_pdf)
    out = write_json(p, tmp_path / "primitives.json")
    raw = json.loads(out.read_text(encoding="utf-8"))
    assert raw["source_pdf"] == str(sample_pdf)
    assert raw["pages"][0]["page_index"] == 0
    assert isinstance(raw["pages"][0]["lines"], list)


def test_cli_ingest_writes_file(sample_pdf: Path, tmp_path: Path) -> None:
    runner = CliRunner()
    out = tmp_path / "primitives.json"
    result = runner.invoke(app, ["ingest", str(sample_pdf), "-o", str(out)])
    assert result.exit_code == 0, result.output
    assert out.exists()
    assert "lines=" in result.output


def test_ocr_module_is_optional() -> None:
    # Whether or not paddleocr is installed, this must not raise.
    available = ocr.is_available()
    assert isinstance(available, bool)
