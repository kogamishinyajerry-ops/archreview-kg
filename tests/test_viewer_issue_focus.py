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


def test_build_issue_focus_view_degrades_without_page_dimensions() -> None:
    view = build_issue_focus_view([], {"pages": []})

    assert view["available"] is False
    assert view["items"] == {}
    assert view["warning_text"] == "缺少第一页尺寸, 无法定位图面。"
