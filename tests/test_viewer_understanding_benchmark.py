import json
from pathlib import Path

from archkg.viewer.understanding_benchmark import (
    render_markdown_report,
    run_understanding_benchmark,
)


def _write_run_artifacts(run_dir: Path) -> None:
    run_dir.mkdir()
    primitives = {
        "points_per_meter": 50.0,
        "pages": [
            {
                "lines": [{"p0": [0, 0], "p1": [100, 0]} for _ in range(4)],
                "texts": [{"text": "卧室", "bbox": [10, 10, 30, 30], "source": "ocr"}],
            }
        ],
    }
    graph = {
        "source_pdf": "fixture.pdf",
        "points_per_meter": 50.0,
        "page_index": 0,
        "page_width_pt": 500.0,
        "page_height_pt": 400.0,
        "rooms": [
            {
                "id": "room-1",
                "page_index": 0,
                "bbox": [0, 0, 100, 100],
                "polygon": [[0, 0], [100, 0], [100, 100], [0, 100]],
                "label": "bedroom",
                "area_m2": 10.0,
                "confidence": 0.9,
            }
        ],
        "doors": [
            {
                "id": "door-1",
                "page_index": 0,
                "bbox": [90, 90, 110, 110],
                "width_m": 0.9,
                "connects": ["room-1", None],
                "confidence": 0.8,
            }
        ],
        "corridors": [],
        "dimensions": [
            {
                "id": "dim-1",
                "page_index": 0,
                "bbox": [85, 85, 115, 115],
                "text": "DOOR 0.90",
                "value_m": 0.9,
                "confidence": 0.95,
            }
        ],
        "stairs": [],
    }
    (run_dir / "primitives.json").write_text(json.dumps(primitives), "utf-8")
    (run_dir / "entity_graph.json").write_text(json.dumps(graph), "utf-8")


def test_understanding_benchmark_builds_missing_payload_and_scores_pass(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _write_run_artifacts(run_dir)
    expected = {
        "benchmark_id": "unit-bedroom-door",
        "min_score": 1.0,
        "drawing_type": "建筑平面图",
        "likely_design_contains": "住宅",
        "component_counts": {
            "rooms": {"exact": 1},
            "doors": {"min": 1},
            "dimensions": {"min": 1},
        },
        "required_semantic_kinds": [
            "residential_room",
            "door_opening",
            "dimension_annotation",
        ],
        "required_evidence_signals": [
            "spatial_layout",
            "residential_room_labels",
            "openings",
            "dimension_evidence",
            "ocr_text",
        ],
        "required_benchmark_signals": {
            "has_spatial_layout": True,
            "has_openings": True,
            "has_dimension_evidence": True,
            "has_ocr_text": True,
        },
    }

    result = run_understanding_benchmark(run_dir, expected)

    assert result["benchmark_id"] == "unit-bedroom-door"
    assert result["passed"] is True
    assert result["score"] == 1.0
    assert (run_dir / "drawing_understanding.json").exists()
    assert all(check["passed"] for check in result["checks"])


def test_understanding_benchmark_reports_missing_semantic_kind(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _write_run_artifacts(run_dir)
    expected = {
        "benchmark_id": "unit-missing-stair",
        "min_score": 1.0,
        "required_semantic_kinds": ["residential_room", "stair"],
    }

    result = run_understanding_benchmark(run_dir, expected)

    assert result["passed"] is False
    assert result["score"] < 1.0
    failed = [check for check in result["checks"] if not check["passed"]]
    assert failed == [
        {
            "name": "required_semantic_kind:stair",
            "passed": False,
            "expected": "stair",
            "actual": ["dimension_annotation", "door_opening", "residential_room"],
            "detail": "missing semantic kind in component_inventory",
        }
    ]


def test_understanding_benchmark_scores_text_inventory(tmp_path: Path) -> None:
    expected = {
        "benchmark_id": "text-inventory",
        "min_score": 1.0,
        "text_inventory": {
            "room_label_counts": {"bedroom": 2, "linen": 1},
            "door_or_opening_size_label_counts": {"3068": 1},
            "major_dimension_texts": ["24'-0\""],
        },
    }
    payload = {
        "schema_version": "drawing_understanding.v2",
        "drawing_type": "建筑平面图",
        "component_counts": {},
        "component_inventory": [],
        "drawing_profile": {"evidence_signals": []},
        "benchmark_signals": {},
        "text_inventory": {
            "room_label_counts": {"bedroom": 2, "linen": 1},
            "door_or_opening_size_label_counts": {"3068": 1},
            "major_dimension_texts": ["24'-0\"", "150'-0\""],
        },
    }
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "drawing_understanding.json").write_text(json.dumps(payload), "utf-8")

    result = run_understanding_benchmark(run_dir, expected)

    assert result["passed"] is True
    assert result["score"] == 1.0
    assert any(check["name"] == "text_inventory:major_dimension_text:24'-0\"" for check in result["checks"])


def test_understanding_benchmark_markdown_report(tmp_path: Path) -> None:
    result = {
        "benchmark_id": "demo",
        "passed": False,
        "score": 0.5,
        "checks": [
            {"name": "drawing_type", "passed": True, "expected": "建筑平面图", "actual": "建筑平面图"},
            {"name": "required_semantic_kind:stair", "passed": False, "expected": "stair", "actual": []},
        ],
    }

    md = render_markdown_report(result)

    assert "# Drawing Understanding Benchmark: demo" in md
    assert "Status: FAIL" in md
    assert "| required_semantic_kind:stair | FAIL |" in md
