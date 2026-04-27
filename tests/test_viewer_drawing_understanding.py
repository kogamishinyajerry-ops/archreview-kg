import json

from archkg.viewer.drawing_understanding import (
    build_drawing_understanding,
    load_or_build_drawing_understanding,
)


def test_build_drawing_understanding_summarizes_plan_components() -> None:
    primitives = {
        "points_per_meter": 50.0,
        "pages": [
            {
                "lines": [{"p0": [0, 0], "p1": [100, 0]} for _ in range(8)],
                "texts": [
                    {"text": "卧室", "bbox": [10, 10, 30, 30], "source": "ocr"},
                    {"text": "DOOR 0.85", "bbox": [95, 95, 105, 105], "source": "ocr"},
                ],
            }
        ],
    }
    graph = {
        "rooms": [
            {
                "id": "room-1",
                "label": "bedroom",
                "area_m2": 12.5,
                "bbox": [0, 0, 100, 100],
                "confidence": 0.85,
                "uncertain": False,
            },
            {
                "id": "room-2",
                "label": None,
                "area_m2": 8.0,
                "bbox": [100, 0, 180, 80],
                "confidence": 0.6,
                "uncertain": True,
            },
        ],
        "doors": [
            {
                "id": "door-1",
                "bbox": [90, 90, 110, 110],
                "width_m": 0.85,
                "connects": ["room-1", "room-2"],
                "confidence": 0.85,
            }
        ],
        "corridors": [
            {
                "id": "corridor-1",
                "bbox": [0, 100, 180, 130],
                "min_width_m": 1.2,
                "confidence": 0.8,
            }
        ],
        "dimensions": [
            {
                "id": "dim-1",
                "text": "DOOR 0.85",
                "value_m": 0.85,
                "bbox": [95, 95, 105, 105],
                "confidence": 0.94,
            }
        ],
    }
    ocr_diagnostics = {
        "text_count": 2,
        "qa_candidate_count": 1,
        "dimension_text_count": 1,
        "bound_dimension_count": 1,
        "dimension_rows": [
            {
                "text": "DOOR 0.85",
                "value_text": "0.85 m",
                "target_kind": "Door",
                "target_id": "door-1",
                "binding_state": "绑定 Door",
            }
        ],
    }

    payload = build_drawing_understanding(primitives, graph, ocr_diagnostics)

    assert payload["drawing_type"] == "建筑平面图"
    assert payload["likely_design"] == "住宅平面图"
    assert "识别到 2 个空间" in payload["summary"]
    assert payload["component_counts"] == {
        "lines": 8,
        "texts": 2,
        "rooms": 2,
        "doors": 1,
        "corridors": 1,
        "stairs": 0,
        "dimensions": 1,
        "ocr_texts": 2,
    }
    assert payload["components"]["spaces"][0]["label_zh"] == "卧室"
    assert payload["components"]["openings"][0]["width_text"] == "0.85 m"
    assert payload["components"]["circulation"][0]["min_width_text"] == "1.20 m"
    assert payload["dimension_evidence"]["ocr_bound_count"] == 1
    assert payload["dimension_evidence"]["ocr_dimensions"][0]["target_id"] == "door-1"
    assert any("未分类房间" in flag for flag in payload["uncertainty_flags"])


def test_build_drawing_understanding_emits_component_taxonomy_and_profile() -> None:
    primitives = {
        "points_per_meter": 50.0,
        "pages": [
            {
                "lines": [{"p0": [0, 0], "p1": [100, 0]} for _ in range(12)],
                "texts": [
                    {"text": "卧室", "bbox": [10, 10, 30, 30], "source": "ocr"},
                    {"text": "楼梯", "bbox": [150, 10, 180, 30], "source": "ocr"},
                    {"text": "走廊 1.20", "bbox": [90, 110, 130, 130], "source": "ocr"},
                ],
            }
        ],
    }
    graph = {
        "rooms": [
            {
                "id": "room-1",
                "label": "bedroom",
                "area_m2": 12.5,
                "bbox": [0, 0, 100, 100],
                "confidence": 0.86,
                "uncertain": False,
            }
        ],
        "doors": [
            {
                "id": "door-1",
                "bbox": [90, 90, 110, 110],
                "width_m": 0.9,
                "connects": ["room-1", "corridor-1"],
                "confidence": 0.78,
            }
        ],
        "corridors": [
            {
                "id": "corridor-1",
                "bbox": [0, 100, 180, 130],
                "min_width_m": 1.2,
                "confidence": 0.64,
            }
        ],
        "stairs": [
            {
                "id": "stair-1",
                "bbox": [0, 0, 0, 0],
                "tread_width_m": 0.24,
                "riser_height_m": 0.18,
                "confidence": 0.0,
                "uncertain": True,
                "properties": {
                    "flight_width_m": 0.95,
                    "handrail_height_m": 0.85,
                    "well_width_m": 0.14,
                },
            }
        ],
        "dimensions": [
            {
                "id": "dim-1",
                "text": "走廊 1.20",
                "value_m": 1.2,
                "bbox": [90, 110, 130, 130],
                "confidence": 0.94,
            }
        ],
    }
    ocr_diagnostics = {
        "text_count": 3,
        "dimension_text_count": 1,
        "bound_dimension_count": 1,
        "dimension_rows": [
            {
                "text": "走廊 1.20",
                "value_text": "1.20 m",
                "target_kind": "Corridor",
                "target_id": "corridor-1",
                "binding_state": "绑定 Corridor",
            }
        ],
    }

    payload = build_drawing_understanding(primitives, graph, ocr_diagnostics)

    assert payload["component_counts"]["stairs"] == 1
    assert payload["components"]["vertical_circulation"][0]["id"] == "stair-1"
    assert payload["components"]["vertical_circulation"][0]["flight_width_text"] == "0.95 m"
    assert payload["drawing_profile"]["understanding_level"] == "layout_with_dimensions"
    assert payload["drawing_profile"]["evidence_signals"] == [
        "spatial_layout",
        "residential_room_labels",
        "openings",
        "horizontal_circulation",
        "vertical_circulation",
        "dimension_evidence",
        "ocr_text",
    ]
    assert payload["benchmark_signals"] == {
        "has_spatial_layout": True,
        "has_openings": True,
        "has_horizontal_circulation": True,
        "has_vertical_circulation": True,
        "has_dimension_evidence": True,
        "has_ocr_text": True,
    }
    inventory = payload["component_inventory"]
    assert {row["semantic_kind"] for row in inventory} >= {
        "residential_room",
        "door_opening",
        "horizontal_circulation",
        "stair",
        "dimension_annotation",
        "ocr_dimension",
    }
    stair_row = next(row for row in inventory if row["semantic_kind"] == "stair")
    assert stair_row["category"] == "vertical_circulation"
    assert stair_row["metric_text"] == "踏步 0.24 m / 踢面 0.18 m / 梯段 0.95 m"
    assert stair_row["confidence_band"] == "external_or_unknown"
    assert any("楼梯/垂直交通" in flag for flag in payload["uncertainty_flags"])


def test_build_drawing_understanding_infers_stair_hint_from_direction_text() -> None:
    primitives = {
        "points_per_meter": 50.0,
        "pages": [
            {
                "lines": [{"p0": [0, 0], "p1": [100, 0]} for _ in range(12)],
                "texts": [
                    {"text": "UP", "bbox": [10, 10, 20, 20], "source": "vector"},
                    {"text": "DN", "bbox": [30, 10, 40, 20], "source": "vector"},
                    {"text": "SETUP", "bbox": [200, 10, 240, 20], "source": "vector"},
                ],
            }
        ],
    }
    graph = {
        "rooms": [
            {
                "id": "room-1",
                "label": "living",
                "area_m2": 24.0,
                "bbox": [0, 0, 100, 100],
                "confidence": 0.8,
            }
        ],
        "doors": [
            {
                "id": "door-1",
                "bbox": [90, 90, 110, 110],
                "width_m": 0.9,
                "connects": ["room-1"],
                "confidence": 0.78,
            }
        ],
        "corridors": [],
        "stairs": [],
        "dimensions": [],
    }

    payload = build_drawing_understanding(primitives, graph, {"text_count": 3})

    assert payload["component_counts"]["stairs"] == 2
    assert payload["benchmark_signals"]["has_vertical_circulation"] is True
    assert "vertical_circulation" in payload["drawing_profile"]["evidence_signals"]
    vertical_rows = payload["components"]["vertical_circulation"]
    assert [row["label"] for row in vertical_rows] == ["UP", "DN"]
    assert all(row["semantic_kind"] == "stair" for row in vertical_rows)
    assert all(row["evidence_source"] == "text_hint" for row in vertical_rows)
    inventory = payload["component_inventory"]
    assert any(row["semantic_kind"] == "stair" for row in inventory)
    assert not any(row["label"] == "SETUP" for row in inventory)


def test_build_drawing_understanding_extracts_text_label_inventory() -> None:
    primitives = {
        "points_per_meter": 50.0,
        "pages": [
            {
                "lines": [{"p0": [0, 0], "p1": [100, 0]} for _ in range(12)],
                "texts": [
                    {"text": "BEDROOM #1", "bbox": [10, 10, 30, 30], "source": "vector"},
                    {"text": "BEDROOM #2", "bbox": [40, 10, 60, 30], "source": "vector"},
                    {"text": "LIN.", "bbox": [70, 10, 90, 30], "source": "vector"},
                    {"text": "WALK-IN", "bbox": [100, 10, 130, 30], "source": "vector"},
                    {"text": "3068", "bbox": [10, 60, 30, 75], "source": "vector"},
                    {"text": "SLD6068", "bbox": [40, 60, 80, 75], "source": "vector"},
                    {"text": "24'-0\"", "bbox": [10, 100, 50, 115], "source": "vector"},
                    {"text": "2'-0\"", "bbox": [60, 100, 90, 115], "source": "vector"},
                    {"text": "3/16\" = 1'-0\"", "bbox": [100, 100, 160, 115], "source": "vector"},
                ],
            }
        ],
    }
    graph = {
        "rooms": [],
        "doors": [],
        "corridors": [],
        "stairs": [],
        "dimensions": [],
    }

    payload = build_drawing_understanding(primitives, graph, {})

    assert payload["text_inventory"] == {
        "room_label_counts": {"bedroom": 2, "linen": 1, "walk_in": 1},
        "door_or_opening_size_label_counts": {"3068": 1, "SLD6068": 1},
        "major_dimension_texts": ["24'-0\""],
    }


def test_load_or_build_rebuilds_legacy_payload_without_taxonomy(tmp_path) -> None:
    (tmp_path / "drawing_understanding.json").write_text(
        json.dumps({"drawing_type": "建筑平面图"}, ensure_ascii=False),
        "utf-8",
    )
    primitives = {"pages": [{"lines": [{"p0": [0, 0], "p1": [10, 0]}], "texts": []}]}
    graph = {
        "rooms": [
            {
                "id": "room-1",
                "label": "bedroom",
                "area_m2": 10.0,
                "bbox": [0, 0, 100, 100],
                "confidence": 0.9,
            }
        ],
        "doors": [],
        "corridors": [],
        "dimensions": [],
        "stairs": [],
    }

    payload = load_or_build_drawing_understanding(tmp_path, primitives, graph, {})

    assert payload["schema_version"] == "drawing_understanding.v2"
    assert payload["component_counts"]["rooms"] == 1
    assert payload["component_inventory"][0]["semantic_kind"] == "residential_room"
    stored = json.loads((tmp_path / "drawing_understanding.json").read_text("utf-8"))
    assert stored["schema_version"] == "drawing_understanding.v2"
