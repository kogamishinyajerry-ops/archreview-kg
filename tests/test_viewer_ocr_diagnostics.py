from archkg.viewer.ocr_diagnostics import build_ocr_diagnostics


def test_build_ocr_diagnostics_counts_binding_and_bad_confidence() -> None:
    primitives = {
        "pages": [
            {
                "texts": [
                    {
                        "text": "卧室",
                        "bbox": [10, 10, 20, 20],
                        "source": "ocr",
                        "confidence": "bad",
                    },
                    {
                        "text": "人工备注",
                        "bbox": [12, 12, 16, 16],
                        "source": "pdf",
                        "confidence": 1.0,
                    },
                    {
                        "text": "杂字",
                        "bbox": [200, 200, 220, 220],
                        "source": "ocr",
                        "confidence": 0.95,
                    },
                ]
            }
        ]
    }
    graph = {
        "rooms": [
            {
                "id": "room-1",
                "label": "bedroom",
                "polygon": [[0, 0], [50, 0], [50, 50], [0, 50]],
            }
        ]
    }

    diagnostics = build_ocr_diagnostics(primitives, graph)

    assert diagnostics["text_count"] == 2
    assert diagnostics["bound_room_count"] == 1
    assert diagnostics["unbound_count"] == 1
    assert diagnostics["low_confidence_count"] == 1
    assert diagnostics["labeled_room_count"] == 1
    assert diagnostics["rows"][0]["confidence"] == 0.0
    assert diagnostics["rows"][0]["low_confidence"] is True
    assert diagnostics["rows"][0]["room_id"] == "room-1"
    assert diagnostics["rows"][1]["binding_state"] == "未绑定"


def test_build_ocr_diagnostics_marks_label_qa_candidates() -> None:
    primitives = {
        "pages": [
            {
                "texts": [
                    {
                        "text": "卧室",
                        "bbox": [10, 10, 20, 20],
                        "source": "ocr",
                        "confidence": 0.95,
                    },
                    {
                        "text": "厨房",
                        "bbox": [30, 10, 40, 20],
                        "source": "ocr",
                        "confidence": 0.92,
                    },
                    {
                        "text": "客厅",
                        "bbox": [200, 200, 220, 220],
                        "source": "ocr",
                        "confidence": 0.96,
                    },
                    {
                        "text": "卫生间",
                        "bbox": [80, 10, 90, 20],
                        "source": "ocr",
                        "confidence": 0.44,
                    },
                ]
            }
        ]
    }
    graph = {
        "rooms": [
            {
                "id": "room-1",
                "label": "bedroom",
                "polygon": [[0, 0], [50, 0], [50, 50], [0, 50]],
            },
            {
                "id": "room-2",
                "label": "bathroom",
                "polygon": [[60, 0], [110, 0], [110, 50], [60, 50]],
            },
        ]
    }

    diagnostics = build_ocr_diagnostics(primitives, graph)

    assert diagnostics["qa_candidate_count"] == 3
    assert diagnostics["label_conflict_count"] == 1
    assert diagnostics["unbound_high_confidence_label_count"] == 1
    assert diagnostics["low_confidence_label_count"] == 1

    candidates = diagnostics["qa_candidates"]
    assert [candidate["reason_code"] for candidate in candidates] == [
        "label_conflict",
        "unbound_high_confidence_label",
        "low_confidence_label",
    ]
    assert candidates[0]["normalized_label"] == "kitchen"
    assert candidates[0]["room_label"] == "bedroom"
    assert candidates[1]["text"] == "客厅"
    assert candidates[1]["room_id"] is None
    assert candidates[2]["normalized_label"] == "bathroom"


def test_build_ocr_diagnostics_marks_dimension_binding_evidence() -> None:
    primitives = {
        "points_per_meter": 50.0,
        "pages": [
            {
                "texts": [
                    {
                        "text": "DOOR 0.85",
                        "bbox": [95, 95, 105, 105],
                        "source": "ocr",
                        "confidence": 0.94,
                    },
                    {
                        "text": "走廊 1200 mm",
                        "bbox": [235, 20, 265, 35],
                        "source": "ocr",
                        "confidence": 0.91,
                    },
                    {
                        "text": "999",
                        "bbox": [1000, 1000, 1030, 1020],
                        "source": "ocr",
                        "confidence": 0.88,
                    },
                ]
            }
        ],
    }
    graph = {
        "points_per_meter": 50.0,
        "rooms": [],
        "doors": [
            {
                "id": "door-1",
                "bbox": [90, 90, 110, 110],
                "width_m": 0.85,
            }
        ],
        "corridors": [
            {
                "id": "corridor-1",
                "bbox": [200, 0, 300, 50],
                "min_width_m": 1.2,
                "polygon": [[200, 0], [300, 0], [300, 50], [200, 50]],
            }
        ],
    }

    diagnostics = build_ocr_diagnostics(primitives, graph)

    assert diagnostics["dimension_text_count"] == 3
    assert diagnostics["bound_dimension_count"] == 2
    assert diagnostics["unbound_dimension_count"] == 1

    rows = diagnostics["dimension_rows"]
    assert rows[0]["text"] == "DOOR 0.85"
    assert rows[0]["target_kind"] == "Door"
    assert rows[0]["target_id"] == "door-1"
    assert rows[0]["value_m"] == 0.85
    assert rows[0]["target_value_m"] == 0.85
    assert rows[0]["binding_state"] == "绑定 Door"

    assert rows[1]["target_kind"] == "Corridor"
    assert rows[1]["target_id"] == "corridor-1"
    assert rows[1]["value_m"] == 1.2
    assert rows[1]["target_value_m"] == 1.2

    assert rows[2]["target_id"] is None
    assert rows[2]["binding_state"] == "未绑定尺寸实体"


def test_build_ocr_diagnostics_truncates_rows_and_qa_candidates() -> None:
    primitives = {
        "pages": [
            {
                "texts": [
                    {
                        "text": f"卧室_{idx}",
                        "bbox": [10 + idx * 5, 10 + idx * 2, 20 + idx * 5, 20 + idx * 2],
                        "source": "ocr",
                        "confidence": 0.96,
                    }
                    for idx in range(14)
                ]
            }
        ]
    }
    graph = {
        "rooms": [
            {
                "id": "room-1",
                "label": "kitchen",
                "polygon": [[0, 0], [150, 0], [150, 80], [0, 80]],
            }
        ]
    }

    diagnostics = build_ocr_diagnostics(primitives, graph, limit=12)

    assert diagnostics["text_count"] == 14
    assert diagnostics["displayed_count"] == 12
    assert diagnostics["omitted_count"] == 2
    assert diagnostics["bound_room_count"] == 14
    assert diagnostics["qa_candidate_count"] == 14
    assert diagnostics["qa_omitted_count"] == 2
    assert diagnostics["qa_candidates"][0]["reason_code"] == "label_conflict"
