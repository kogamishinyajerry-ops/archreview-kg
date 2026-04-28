from __future__ import annotations

from archkg.viewer.issue_focus import build_issue_focus_view


def test_build_issue_focus_view_maps_first_page_issue_bbox() -> None:
    primitives = {
        "pages": [
            {
                "page_index": 0,
                "width_pt": 1000.0,
                "height_pt": 500.0,
                "lines": [],
                "texts": [],
            }
        ]
    }
    issues = [
        {
            "issue_id": "ISS-1",
            "rule_card_id": "RC-CORRIDOR-WIDTH",
            "severity": "error",
            "page_index": 0,
            "bbox": [100.0, 50.0, 300.0, 150.0],
        },
        {
            "issue_id": "ISS-2",
            "rule_card_id": "RC-DOOR-WIDTH",
            "severity": "warning",
            "page_index": 1,
            "bbox": [100.0, 50.0, 300.0, 150.0],
        },
    ]

    view = build_issue_focus_view(issues, primitives)

    assert view["available"] is True
    assert view["omitted_count"] == 1
    focus = view["items"]["ISS-1"]
    assert focus["x_pct"] == 10.0
    assert focus["y_pct"] == 10.0
    assert focus["w_pct"] == 20.0
    assert focus["h_pct"] == 20.0
    assert focus["rule_card_id"] == "RC-CORRIDOR-WIDTH"


def test_build_issue_focus_view_maps_issue_bbox_on_own_page() -> None:
    primitives = {
        "pages": [
            {
                "page_index": 0,
                "width_pt": 1000.0,
                "height_pt": 500.0,
                "lines": [],
                "texts": [],
            },
            {
                "page_index": 1,
                "width_pt": 2000.0,
                "height_pt": 1000.0,
                "lines": [],
                "texts": [],
            },
        ]
    }
    issues = [
        {
            "issue_id": "ISS-2",
            "rule_card_id": "RC-DOOR-WIDTH",
            "severity": "warning",
            "page_index": 1,
            "bbox": [200.0, 100.0, 600.0, 300.0],
        }
    ]

    view = build_issue_focus_view(issues, primitives)

    assert view["available"] is True
    assert view["page_count"] == 2
    assert view["omitted_count"] == 0
    assert view["non_preview_page_count"] == 1
    focus = view["items"]["ISS-2"]
    assert focus["page_index"] == 1
    assert focus["page_number"] == 2
    assert focus["page_width_pt"] == 2000.0
    assert focus["page_height_pt"] == 1000.0
    assert focus["preview_layer_supported"] is False
    assert focus["x_pct"] == 10.0
    assert focus["y_pct"] == 10.0
    assert focus["w_pct"] == 20.0
    assert focus["h_pct"] == 20.0


def test_build_issue_focus_view_marks_non_first_page_preview_when_pages_exist() -> None:
    primitives = {
        "pages": [
            {"page_index": 0, "width_pt": 1000.0, "height_pt": 500.0},
            {"page_index": 1, "width_pt": 2000.0, "height_pt": 1000.0},
        ]
    }
    preview_pages = {
        "layers": {
            "source": [
                {"page_index": 0, "src": "source_preview.png"},
                {"page_index": 1, "src": "source_preview_page_2.png"},
            ],
            "annotated": [
                {"page_index": 0, "src": "annotated_preview.png"},
                {"page_index": 1, "src": "annotated_preview_page_2.png"},
            ],
            "overlay": [{"page_index": 0, "src": "entity_overlay.png"}],
        }
    }
    issues = [
        {
            "issue_id": "ISS-2",
            "rule_card_id": "RC-DOOR-WIDTH",
            "severity": "warning",
            "page_index": 1,
            "bbox": [200.0, 100.0, 600.0, 300.0],
        }
    ]

    view = build_issue_focus_view(issues, primitives, preview_pages=preview_pages)

    assert view["non_preview_page_count"] == 0
    focus = view["items"]["ISS-2"]
    assert focus["preview_layer_supported"] is True
    assert focus["preview_layers"] == ["source", "annotated"]


def test_build_issue_focus_view_tracks_unmapped_page_issue() -> None:
    primitives = {
        "pages": [
            {
                "page_index": 0,
                "width_pt": 1000.0,
                "height_pt": 500.0,
                "lines": [],
                "texts": [],
            }
        ]
    }
    issues = [
        {
            "issue_id": "ISS-9",
            "rule_card_id": "RC-UNKNOWN",
            "severity": "error",
            "page_index": 9,
            "bbox": [100.0, 50.0, 300.0, 150.0],
        }
    ]

    view = build_issue_focus_view(issues, primitives)

    assert view["available"] is False
    assert view["items"] == {}
    assert view["omitted_count"] == 1
    assert view["omitted_items"] == {
        "ISS-9": {
            "issue_id": "ISS-9",
            "page_index": 9,
            "reason": "missing_page_dimensions",
        }
    }


def test_build_issue_focus_view_degrades_without_page_dimensions() -> None:
    view = build_issue_focus_view([], {"pages": []})

    assert view["available"] is False
    assert view["items"] == {}
    assert view["warning_text"] == "缺少第一页尺寸, 无法定位图面。"
