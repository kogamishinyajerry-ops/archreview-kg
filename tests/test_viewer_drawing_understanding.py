from archkg.viewer.drawing_understanding import build_drawing_understanding


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
        "dimensions": 1,
        "ocr_texts": 2,
    }
    assert payload["components"]["spaces"][0]["label_zh"] == "卧室"
    assert payload["components"]["openings"][0]["width_text"] == "0.85 m"
    assert payload["components"]["circulation"][0]["min_width_text"] == "1.20 m"
    assert payload["dimension_evidence"]["ocr_bound_count"] == 1
    assert payload["dimension_evidence"]["ocr_dimensions"][0]["target_id"] == "door-1"
    assert any("未分类房间" in flag for flag in payload["uncertainty_flags"])
