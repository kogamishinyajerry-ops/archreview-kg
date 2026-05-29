import json
from pathlib import Path

from archkg.viewer.understanding_benchmark import (
    author_expected_benchmark_spec,
    run_understanding_benchmark,
)


def _write_understanding_payload(run_dir: Path) -> None:
    run_dir.mkdir()
    payload = {
        "schema_version": "drawing_understanding.v2",
        "drawing_type": "建筑平面图",
        "likely_design": "住宅平面图 - 两室一厅",
        "component_counts": {
            "lines": 48,
            "texts": 12,
            "rooms": 3,
            "doors": 2,
            "corridors": 1,
            "stairs": 0,
            "dimensions": 4,
            "ocr_texts": 6,
        },
        "component_inventory": [
            {"semantic_kind": "residential_room"},
            {"semantic_kind": "door_opening"},
            {"semantic_kind": "horizontal_circulation"},
            {"semantic_kind": "dimension_annotation"},
            {"semantic_kind": "door_opening"},
        ],
        "drawing_profile": {
            "understanding_level": "layout_with_dimensions",
            "evidence_signals": [
                "spatial_layout",
                "openings",
                "dimension_evidence",
                "openings",
            ],
        },
        "benchmark_signals": {
            "has_spatial_layout": True,
            "has_openings": True,
            "has_vertical_circulation": False,
            "has_dimension_evidence": True,
        },
    }
    (run_dir / "drawing_understanding.json").write_text(json.dumps(payload), "utf-8")


def test_author_expected_benchmark_spec_drafts_reviewable_inventory(tmp_path: Path) -> None:
    run_dir = tmp_path / "real-run"
    _write_understanding_payload(run_dir)

    draft = author_expected_benchmark_spec(run_dir, benchmark_id="real-case-draft")

    assert draft == {
        "schema_version": "understanding_benchmark_expected.v1",
        "benchmark_id": "real-case-draft",
        "min_score": 1.0,
        "review_required": True,
        "source_schema_version": "drawing_understanding.v2",
        "drawing_type": "建筑平面图",
        "likely_design_contains": "住宅平面图 - 两室一厅",
        "component_counts": {
            "rooms": {"exact": 3},
            "doors": {"exact": 2},
            "corridors": {"exact": 1},
            "dimensions": {"exact": 4},
            "ocr_texts": {"exact": 6},
        },
        "required_semantic_kinds": [
            "residential_room",
            "door_opening",
            "horizontal_circulation",
            "dimension_annotation",
        ],
        "required_evidence_signals": [
            "spatial_layout",
            "openings",
            "dimension_evidence",
        ],
        "required_benchmark_signals": {
            "has_spatial_layout": True,
            "has_openings": True,
            "has_dimension_evidence": True,
        },
        "authoring_note": (
            "Draft generated from current recognition output; review and adjust "
            "before promoting a real drawing case to active benchmark status."
        ),
    }


def test_authored_expected_spec_scores_source_run(tmp_path: Path) -> None:
    run_dir = tmp_path / "real-run"
    _write_understanding_payload(run_dir)

    draft = author_expected_benchmark_spec(run_dir, benchmark_id="self-check")
    result = run_understanding_benchmark(run_dir, draft)

    assert result["passed"] is True
    assert result["score"] == 1.0
