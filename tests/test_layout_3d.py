from __future__ import annotations

import json
from pathlib import Path

import trimesh

from archkg.graph.builder import EntityGraph
from archkg.graph.sheet_graphs import SheetGraphEntry, SheetGraphsReport
from archkg.layout_3d import (
    build_layout_3d,
    export_layout_3d_glb,
    render_layout_3d_summary_markdown,
    write_layout_3d,
)
from archkg.schemas import Corridor, Dimension, Door, Room, Stair
from archkg.viewer.layout_3d import load_layout_3d_view


def test_layout_3d_prefers_sheet_graphs_and_records_assumptions() -> None:
    report = build_layout_3d(sheet_graphs=_sheet_graphs())

    assert report.schema_version == "layout_3d.v1"
    assert report.model_status == "partial"
    assert report.source_artifact == "sheet_graphs.json"
    assert report.source_sheet_ids == ["page-0"]
    assert report.scale_basis["points_per_meter"] == 50.0
    assert report.blocked_reasons == []

    object_types = {obj.object_type for obj in report.objects}
    assert {
        "floor_slab",
        "room_volume",
        "corridor_volume",
        "wall",
        "door_opening",
        "stair_placeholder",
        "dimension_anchor",
    }.issubset(object_types)
    assert report.summary["room_volume_count"] == 1
    assert report.summary["door_opening_count"] == 1
    assert report.summary["wall_count"] == 8

    assumption_fields = {item.field for item in report.assumptions}
    assert {
        "floor_slab.thickness_m",
        "wall.height_m",
        "wall.thickness_m",
        "door_opening.height_m",
        "stair_placeholder.height_m",
    }.issubset(assumption_fields)

    wall = next(obj for obj in report.objects if obj.object_type == "wall")
    assert wall.source_page_index == 0
    assert wall.source_sheet_id == "page-0"
    assert wall.assumption_ids


def test_layout_3d_falls_back_to_entity_graph_when_sheet_graphs_missing() -> None:
    report = build_layout_3d(entity_graph=_entity_graph())

    assert report.model_status == "partial"
    assert report.source_artifact == "entity_graph.json"
    assert report.source_sheet_ids == ["page-0"]
    assert "sheet_graphs_missing_or_empty" in report.blocked_reasons
    object_count = report.summary["object_count"]
    assert isinstance(object_count, int)
    assert object_count > 0


def test_layout_3d_builds_window_openings_from_explicit_graph_evidence() -> None:
    report = build_layout_3d(entity_graph=_entity_graph_with_window())

    assert report.model_status == "partial"
    assert report.summary["door_opening_count"] == 1
    assert report.summary["window_opening_count"] == 1
    assert report.summary["wall_count"] == 8
    assert "window_opening.height_m" in {item.field for item in report.assumptions}

    door = next(obj for obj in report.objects if obj.object_type == "door_opening")
    window = next(obj for obj in report.objects if obj.object_type == "window_opening")
    assert door.object_id.startswith("page-0-door-opening-door-2")
    assert window.object_id.startswith("page-0-window-opening-window-1")
    assert door.source_entity_id == "door-2"
    assert window.source_entity_id == "window-1"
    assert door.properties["connects"] == ["room-1", "corridor-1"]
    assert window.properties["opening_kind"] == "window"
    assert window.properties["connects"] == ["room-1", "corridor-1"]
    assert door.properties["opening_semantic"] == {
        "kind": "door_opening",
        "explicit": False,
        "source_property": "entity_type",
        "source_value": "Door",
    }
    assert window.properties["opening_semantic"] == {
        "kind": "window_opening",
        "explicit": True,
        "source_property": "opening_kind",
        "source_value": "window",
    }

    window_assumption = next(
        item for item in report.assumptions if item.field == "window_opening.height_m"
    )
    assert window.object_id in window_assumption.applies_to_object_ids

    summary = render_layout_3d_summary_markdown(report)
    assert "## Opening Semantics" in summary
    assert "`window_opening` | 1 | explicit graph evidence only" in summary
    assert "`door_opening` | 1 | graph Door entity default" in summary


def test_layout_3d_records_explicit_opening_measurements_without_height_assumptions() -> None:
    report = build_layout_3d(entity_graph=_entity_graph_with_measured_openings())

    door = next(obj for obj in report.objects if obj.object_type == "door_opening")
    window = next(obj for obj in report.objects if obj.object_type == "window_opening")

    assert door.height_m == 2.2
    assert door.dimensions_m["height_m"] == 2.2
    assert door.properties["opening_measurement"] == {
        "width_m": {
            "value": 0.92,
            "unit": "m",
            "explicit": True,
            "source_property": "Door.width_m",
        },
        "height_m": {
            "value": 2.2,
            "unit": "m",
            "explicit": True,
            "source_property": "Door.properties.height_m",
        },
        "sill_height_m": {
            "value": 0.0,
            "unit": "m",
            "explicit": True,
            "source_property": "Door.properties.sill_height_m",
        },
    }

    assert window.height_m == 1.1
    assert window.dimensions_m["height_m"] == 1.1
    assert window.properties["opening_measurement"] == {
        "width_m": {
            "value": 1.2,
            "unit": "m",
            "explicit": True,
            "source_property": "Door.width_m",
        },
        "height_m": {
            "value": 1.1,
            "unit": "m",
            "explicit": True,
            "source_property": "Door.properties.height_m",
        },
        "sill_height_m": {
            "value": 0.85,
            "unit": "m",
            "explicit": True,
            "source_property": "Door.properties.sill_height_m",
        },
        "head_height_m": {
            "value": 1.95,
            "unit": "m",
            "explicit": True,
            "source_property": "Door.properties.head_height_m",
        },
    }

    height_assumptions = {
        item.field: item.applies_to_object_ids
        for item in report.assumptions
        if item.field in {"door_opening.height_m", "window_opening.height_m"}
    }
    assert door.object_id not in height_assumptions.get("door_opening.height_m", [])
    assert window.object_id not in height_assumptions.get("window_opening.height_m", [])

    assert report.summary["opening_measured_width_count"] == 2
    assert report.summary["opening_measured_height_count"] == 2
    assert report.summary["opening_measured_sill_height_count"] == 2
    assert report.summary["opening_measured_head_height_count"] == 1

    summary = render_layout_3d_summary_markdown(report)
    assert "## Opening Measurements" in summary
    assert "`width_m` | 2 | explicit `Door.width_m` only" in summary
    assert "`height_m` | 2 | explicit `Door.properties.height_m` only" in summary
    assert "`sill_height_m` | 2 | explicit `Door.properties.sill_height_m` only" in summary
    assert "`head_height_m` | 1 | explicit `Door.properties.head_height_m` only" in summary


def test_layout_3d_records_explicit_opening_host_wall_provenance() -> None:
    report = build_layout_3d(entity_graph=_entity_graph_with_opening_host_provenance())

    door = next(obj for obj in report.objects if obj.object_type == "door_opening")
    window = next(obj for obj in report.objects if obj.object_type == "window_opening")

    assert door.properties["opening_host"] == {
        "host_wall_id": "wall-1",
        "source_property": "Door.properties.opening_host_wall_id",
        "explicit": True,
        "source_segment_property": "Door.properties.opening_host_wall_segment",
        "source_segment": {
            "p0": [0.0, 0.0],
            "p1": [0.0, 1.5],
        },
    }
    assert window.properties["opening_host"] == {
        "host_wall_id": "wall-2",
        "source_property": "Door.properties.opening_host_wall_id",
        "explicit": True,
        "source_segment_property": "Door.properties.opening_host_wall_segment",
        "source_segment": {
            "p0": [1.0, 0.0],
            "p1": [1.0, 2.5],
        },
    }
    assert report.summary["opening_host_wall_count"] == 2
    assert report.summary["opening_host_segment_count"] == 2


def test_layout_3d_no_opening_host_wall_provenance_without_explicit_host_fields() -> None:
    report = build_layout_3d(entity_graph=_entity_graph_with_window())

    for obj in report.objects:
        if obj.object_type not in {"door_opening", "window_opening"}:
            continue
        assert "opening_host" not in obj.properties


def test_layout_3d_blocks_without_graph_geometry() -> None:
    report = build_layout_3d(entity_graph=_empty_graph())

    assert report.model_status == "blocked"
    assert report.source_artifact == "entity_graph.json"
    assert report.objects == []
    assert "no_layout_entities_available" in report.blocked_reasons


def test_layout_3d_writes_json_summary_and_exportable_glb(tmp_path: Path) -> None:
    report = build_layout_3d(sheet_graphs=_sheet_graphs())

    json_path = write_layout_3d(report, tmp_path / "layout_3d.json")
    summary = render_layout_3d_summary_markdown(report)
    glb_path = export_layout_3d_glb(report, tmp_path / "layout_3d.glb")

    payload = json.loads(json_path.read_text("utf-8"))
    assert payload["schema_version"] == "layout_3d.v1"
    assert "默认值只用于 3D 辅助可视化" in summary
    assert glb_path.exists()
    assert glb_path.stat().st_size > 1024

    scene = trimesh.load(glb_path, force="scene")
    assert isinstance(scene, trimesh.Scene)
    mesh_object_count = report.summary["mesh_object_count"]
    assert isinstance(mesh_object_count, int)
    assert len(scene.geometry) >= mesh_object_count


def test_layout_3d_view_loader_reports_available_and_missing(tmp_path: Path) -> None:
    missing = load_layout_3d_view(tmp_path)
    assert missing["available"] is False
    assert "layout_3d.json 暂无数据" in missing["warning_text"]

    report = build_layout_3d(sheet_graphs=_sheet_graphs())
    write_layout_3d(report, tmp_path / "layout_3d.json")
    (tmp_path / "layout_3d.glb").write_bytes(b"glb")
    (tmp_path / "layout_3d_summary.md").write_text(
        render_layout_3d_summary_markdown(report),
        encoding="utf-8",
    )

    view = load_layout_3d_view(tmp_path)
    assert view["available"] is True
    assert view["model_status"] == "partial"
    assert view["object_count"] == report.summary["object_count"]
    assert view["glb_available"] is True
    assert view["summary_available"] is True


def test_layout_3d_view_loader_exposes_opening_semantic_provenance(tmp_path: Path) -> None:
    report = build_layout_3d(entity_graph=_entity_graph_with_window())
    write_layout_3d(report, tmp_path / "layout_3d.json")

    view = load_layout_3d_view(tmp_path)

    assert view["opening_semantics"]["door_opening_count"] == 1
    assert view["opening_semantics"]["window_opening_count"] == 1
    assert view["opening_semantics"]["boundary_warning"] == (
        "window_opening is shown only when explicit graph evidence marks the opening as a window."
    )
    samples = view["opening_semantics"]["samples"]
    assert {
        "object_id": "page-0-window-opening-window-1",
        "object_type": "window_opening",
        "source_entity_id": "window-1",
        "kind": "window_opening",
        "explicit": True,
        "source_property": "opening_kind",
        "source_value": "window",
    } in samples


def test_layout_3d_view_loader_exposes_opening_measurement_provenance(tmp_path: Path) -> None:
    report = build_layout_3d(entity_graph=_entity_graph_with_measured_openings())
    write_layout_3d(report, tmp_path / "layout_3d.json")

    view = load_layout_3d_view(tmp_path)

    measurements = view["opening_measurements"]
    assert measurements["explicit_width_count"] == 2
    assert measurements["explicit_height_count"] == 2
    assert measurements["explicit_sill_height_count"] == 2
    assert measurements["explicit_head_height_count"] == 1
    assert measurements["boundary_warning"] == (
        "Opening measurements are shown only from explicit graph evidence fields and remain preview-only."
    )
    assert {
        "object_id": "page-0-window-opening-window-1",
        "object_type": "window_opening",
        "source_entity_id": "window-1",
        "field": "height_m",
        "value": 1.1,
        "unit": "m",
        "explicit": True,
        "source_property": "Door.properties.height_m",
    } in measurements["samples"]


def test_layout_3d_view_loader_exposes_opening_host_wall_provenance(tmp_path: Path) -> None:
    report = build_layout_3d(entity_graph=_entity_graph_with_opening_host_provenance())
    write_layout_3d(report, tmp_path / "layout_3d.json")

    view = load_layout_3d_view(tmp_path)

    hosts = view["opening_wall_hosts"]
    assert hosts["explicit_host_wall_count"] == 2
    assert hosts["explicit_host_segment_count"] == 2
    assert hosts["boundary_warning"] == (
        "Opening host-wall provenance is shown only when the graph provides explicit host wall "
        "or source-segment evidence."
    )
    assert {
        "object_id": "page-0-door-opening-door-2",
        "object_type": "door_opening",
        "source_entity_id": "door-2",
        "host_wall_id": "wall-1",
        "source_property": "Door.properties.opening_host_wall_id",
        "source_segment": {
            "p0": [0.0, 0.0],
            "p1": [0.0, 1.5],
        },
        "explicit": True,
        "source_segment_property": "Door.properties.opening_host_wall_segment",
    } in hosts["samples"]


def _sheet_graphs() -> SheetGraphsReport:
    graph = _entity_graph()
    return SheetGraphsReport(
        source_pdf=graph.source_pdf,
        graph_count=1,
        confidence_floor=0.5,
        graphs=[
            SheetGraphEntry(
                page_index=0,
                classification_confidence=0.93,
                component_counts={
                    "rooms": len(graph.rooms),
                    "doors": len(graph.doors),
                    "corridors": len(graph.corridors),
                    "stairs": len(graph.stairs),
                    "dimensions": len(graph.dimensions),
                },
                graph=graph,
            )
        ],
        skipped_pages=[],
    )


def _entity_graph() -> EntityGraph:
    return EntityGraph(
        source_pdf="synthetic.pdf",
        points_per_meter=50.0,
        page_index=0,
        page_width_pt=400.0,
        page_height_pt=260.0,
        rooms=[
            Room(
                id="room-1",
                page_index=0,
                bbox=(0.0, 0.0, 200.0, 150.0),
                polygon=[
                    (0.0, 0.0),
                    (200.0, 0.0),
                    (200.0, 150.0),
                    (0.0, 150.0),
                    (0.0, 0.0),
                ],
                area_m2=12.0,
                label="bedroom",
            )
        ],
        doors=[
            Door(
                id="door-1",
                page_index=0,
                bbox=(92.0, -4.0, 138.0, 5.0),
                width_m=0.92,
                connects=("room-1", "corridor-1"),
            )
        ],
        corridors=[
            Corridor(
                id="corridor-1",
                page_index=0,
                bbox=(0.0, 150.0, 200.0, 210.0),
                polygon=[
                    (0.0, 150.0),
                    (200.0, 150.0),
                    (200.0, 210.0),
                    (0.0, 210.0),
                    (0.0, 150.0),
                ],
                min_width_m=1.2,
            )
        ],
        dimensions=[
            Dimension(
                id="dim-1",
                page_index=0,
                bbox=(15.0, 215.0, 75.0, 235.0),
                text="4.0 m",
                value_m=4.0,
                unit="m",
            )
        ],
        stairs=[
            Stair(
                id="stair-1",
                page_index=0,
                bbox=(220.0, 20.0, 320.0, 120.0),
                tread_width_m=1.1,
            )
        ],
    )


def _empty_graph() -> EntityGraph:
    return EntityGraph(
        source_pdf="empty.pdf",
        points_per_meter=50.0,
        page_index=0,
        page_width_pt=400.0,
        page_height_pt=260.0,
        rooms=[],
        doors=[],
        corridors=[],
        dimensions=[],
        stairs=[],
    )


def _entity_graph_with_window() -> EntityGraph:
    return EntityGraph(
        source_pdf="synthetic-window.pdf",
        points_per_meter=50.0,
        page_index=0,
        page_width_pt=400.0,
        page_height_pt=260.0,
        rooms=[
            Room(
                id="room-1",
                page_index=0,
                bbox=(0.0, 0.0, 200.0, 150.0),
                polygon=[
                    (0.0, 0.0),
                    (200.0, 0.0),
                    (200.0, 150.0),
                    (0.0, 150.0),
                    (0.0, 0.0),
                ],
                area_m2=12.0,
                label="bedroom",
            )
        ],
        doors=[
            Door(
                id="window-1",
                page_index=0,
                bbox=(40.0, -6.0, 72.0, 5.0),
                width_m=0.64,
                properties={"opening_kind": "window"},
                connects=("room-1", "corridor-1"),
            ),
            Door(
                id="door-2",
                page_index=0,
                bbox=(92.0, -4.0, 138.0, 5.0),
                width_m=0.92,
                connects=("room-1", "corridor-1"),
            ),
        ],
        corridors=[
            Corridor(
                id="corridor-1",
                page_index=0,
                bbox=(0.0, 150.0, 200.0, 210.0),
                polygon=[
                    (0.0, 150.0),
                    (200.0, 150.0),
                    (200.0, 210.0),
                    (0.0, 210.0),
                    (0.0, 150.0),
                ],
            )
        ],
        dimensions=[
            Dimension(
                id="dim-1",
                page_index=0,
                bbox=(15.0, 215.0, 75.0, 235.0),
                text="4.0 m",
                value_m=4.0,
                unit="m",
            )
        ],
        stairs=[
            Stair(
                id="stair-1",
                page_index=0,
                bbox=(220.0, 20.0, 320.0, 120.0),
                tread_width_m=1.1,
            )
        ],
    )


def _entity_graph_with_measured_openings() -> EntityGraph:
    return EntityGraph(
        source_pdf="synthetic-measured-openings.pdf",
        points_per_meter=50.0,
        page_index=0,
        page_width_pt=400.0,
        page_height_pt=260.0,
        rooms=[
            Room(
                id="room-1",
                page_index=0,
                bbox=(0.0, 0.0, 200.0, 150.0),
                polygon=[
                    (0.0, 0.0),
                    (200.0, 0.0),
                    (200.0, 150.0),
                    (0.0, 150.0),
                    (0.0, 0.0),
                ],
                area_m2=12.0,
                label="bedroom",
            )
        ],
        doors=[
            Door(
                id="window-1",
                page_index=0,
                bbox=(40.0, -6.0, 100.0, 5.0),
                width_m=1.2,
                properties={
                    "opening_kind": "window",
                    "height_m": 1.1,
                    "sill_height_m": 0.85,
                    "head_height_m": 1.95,
                },
                connects=("room-1", "corridor-1"),
            ),
            Door(
                id="door-2",
                page_index=0,
                bbox=(92.0, -4.0, 138.0, 5.0),
                width_m=0.92,
                properties={"height_m": 2.2, "sill_height_m": 0.0},
                connects=("room-1", "corridor-1"),
            ),
        ],
        corridors=[
            Corridor(
                id="corridor-1",
                page_index=0,
                bbox=(0.0, 150.0, 200.0, 210.0),
                polygon=[
                    (0.0, 150.0),
                    (200.0, 150.0),
                    (200.0, 210.0),
                    (0.0, 210.0),
                    (0.0, 150.0),
                ],
            )
        ],
        dimensions=[
            Dimension(
                id="dim-1",
                page_index=0,
                bbox=(15.0, 215.0, 75.0, 235.0),
                text="4.0 m",
                value_m=4.0,
                unit="m",
            )
        ],
        stairs=[],
    )


def _entity_graph_with_opening_host_provenance() -> EntityGraph:
    return EntityGraph(
        source_pdf="synthetic-opening-host.pdf",
        points_per_meter=50.0,
        page_index=0,
        page_width_pt=400.0,
        page_height_pt=260.0,
        rooms=[
            Room(
                id="room-1",
                page_index=0,
                bbox=(0.0, 0.0, 200.0, 150.0),
                polygon=[
                    (0.0, 0.0),
                    (200.0, 0.0),
                    (200.0, 150.0),
                    (0.0, 150.0),
                    (0.0, 0.0),
                ],
                area_m2=12.0,
                label="bedroom",
            )
        ],
        doors=[
            Door(
                id="door-2",
                page_index=0,
                bbox=(92.0, -4.0, 138.0, 5.0),
                width_m=0.92,
                connects=("room-1", "corridor-1"),
                properties={
                    "opening_host_wall_id": "wall-1",
                    "opening_host_wall_segment": "0.0,0.0;0.0,1.5",
                },
            ),
            Door(
                id="window-1",
                page_index=0,
                bbox=(40.0, -6.0, 100.0, 5.0),
                width_m=1.2,
                properties={
                    "opening_kind": "window",
                    "opening_host_wall_id": "wall-2",
                    "opening_host_wall_segment": "1.0,0.0;1.0,2.5",
                },
                connects=("room-1", "corridor-1"),
            ),
        ],
        corridors=[
            Corridor(
                id="corridor-1",
                page_index=0,
                bbox=(0.0, 150.0, 200.0, 210.0),
                polygon=[
                    (0.0, 150.0),
                    (200.0, 150.0),
                    (200.0, 210.0),
                    (0.0, 210.0),
                    (0.0, 150.0),
                ],
            )
        ],
        dimensions=[
            Dimension(
                id="dim-1",
                page_index=0,
                bbox=(15.0, 215.0, 75.0, 235.0),
                text="4.0 m",
                value_m=4.0,
                unit="m",
            )
        ],
        stairs=[],
    )
