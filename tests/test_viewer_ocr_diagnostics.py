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
