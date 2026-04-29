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
    assert report.blocked_reasons == ["window_openings_not_available_in_entity_graph"]

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
