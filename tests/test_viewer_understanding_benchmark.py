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


def test_understanding_benchmark_scores_sheet_graphs_and_sheet_issues(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    payload = {
        "schema_version": "drawing_understanding.v2",
        "drawing_type": "建筑平面图",
        "component_counts": {},
        "component_inventory": [],
        "drawing_profile": {"evidence_signals": ["multi_sheet_plan_graphs"]},
        "benchmark_signals": {},
    }
    sheet_graphs = {
        "schema_version": "sheet_graphs.v1",
        "graph_count": 2,
        "graphs": [
            {"page_index": 0, "component_counts": {"rooms": 4, "doors": 6, "corridors": 1}},
            {"page_index": 1, "component_counts": {"rooms": 4, "doors": 6, "corridors": 1}},
        ],
        "skipped_pages": [{"page_index": 2, "sheet_type": "schedule"}],
    }
    sheet_issues = {
        "schema_version": "sheet_issues.v1",
        "sheet_count": 2,
        "issue_count": 4,
        "sheets": [
            {
                "page_index": 0,
                "issue_count": 2,
                "issues": [
                    {"rule_card_id": "RC-CORRIDOR-WIDTH"},
                    {"rule_card_id": "RC-DOOR-WIDTH"},
                ],
            },
            {
                "page_index": 1,
                "issue_count": 2,
                "issues": [
                    {"rule_card_id": "RC-CORRIDOR-WIDTH"},
                    {"rule_card_id": "RC-DOOR-WIDTH"},
                ],
            },
        ],
    }
    (run_dir / "drawing_understanding.json").write_text(json.dumps(payload), "utf-8")
    (run_dir / "sheet_graphs.json").write_text(json.dumps(sheet_graphs), "utf-8")
    (run_dir / "sheet_issues.json").write_text(json.dumps(sheet_issues), "utf-8")
    expected = {
        "benchmark_id": "multi-plan-artifacts",
        "sheet_graphs": {
            "graph_count": {"exact": 2},
            "required_page_indexes": [0, 1],
            "component_counts": {
                "rooms": {"min": 4},
                "doors": {"min": 6},
                "corridors": {"min": 1},
            },
            "skipped_page_indexes": [2],
        },
        "sheet_issues": {
            "sheet_count": {"exact": 2},
            "issue_count": {"min": 4},
            "required_page_indexes": [0, 1],
            "required_rule_ids_by_page": {
                "0": ["RC-CORRIDOR-WIDTH", "RC-DOOR-WIDTH"],
                "1": ["RC-CORRIDOR-WIDTH", "RC-DOOR-WIDTH"],
            },
        },
    }

    result = run_understanding_benchmark(run_dir, expected)

    assert result["passed"] is True
    assert result["score"] == 1.0
    names = {check["name"] for check in result["checks"]}
    assert "sheet_graphs:graph_count" in names
    assert "sheet_issues:rule_ids:0" in names
    assert "sheet_issues:rule_ids:1" in names


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
