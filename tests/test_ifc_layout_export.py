from __future__ import annotations

import json
import sys
import types
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from archkg.cli.main import app
from archkg.graph.builder import EntityGraph
from archkg.layout_3d import build_layout_3d, write_layout_3d
from archkg.schemas import Corridor, Dimension, Door, Room, Stair


def test_ifc_export_layout_cli_with_fake_dependency_writes_preview_artifacts(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _install_fake_ifcopenshell_modules(monkeypatch)
    layout_path = write_layout_3d(
        build_layout_3d(entity_graph=_entity_graph()),
        tmp_path / "layout_3d.json",
    )
    ifc_path = tmp_path / "layout.ifc"
    ifc_path.write_text("STALE IFC", encoding="utf-8")
    report_path = tmp_path / "layout_ifc_export.json"
    markdown_path = tmp_path / "layout_ifc_export.md"

    result = CliRunner().invoke(
        app,
        [
            "ifc",
            "export-layout",
            "--layout",
            str(layout_path),
            "--out",
            str(ifc_path),
            "--report",
            str(report_path),
            "--markdown",
            str(markdown_path),
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.output
    assert "layout_ifc_export.v1" in result.output
    assert "status=exported" in result.output
    assert ifc_path.read_text("utf-8").startswith("IFC_FAKE")
    assert markdown_path.exists()

    report = json.loads(report_path.read_text("utf-8"))
    assert report["schema_version"] == "layout_ifc_export.v1"
    assert report["status"] == "exported"
    assert report["source_layout_path"] == str(layout_path)
    assert report["source_schema_version"] == "layout_3d.v1"
    assert report["output_ifc_path"] == str(ifc_path)
    assert report["object_count"] > 0
    assert report["exported_counts"]["wall"] == 8
    assert report["exported_counts"]["floor_slab"] == 1
    assert report["exported_counts"]["room_volume"] == 1
    assert report["exported_counts"]["door_opening"] == 1
    assert report["exported_counts"]["stair_placeholder"] == 1
    assert report["skipped_counts"]["dimension_anchor"] == 1
    assert report["assumptions_count"] >= 1
    assert "not a review-grade BIM" in report["boundary_warning"]


def test_ifc_export_layout_cli_with_fake_dependency_tracks_opening_provenance_metadata(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _install_fake_ifcopenshell_modules(monkeypatch)
    layout_path = write_layout_3d(
        build_layout_3d(entity_graph=_entity_graph_with_opening_provenance()),
        tmp_path / "layout_3d.json",
    )
    ifc_path = tmp_path / "layout.ifc"
    report_path = tmp_path / "layout_ifc_export.json"
    markdown_path = tmp_path / "layout_ifc_export.md"

    result = CliRunner().invoke(
        app,
        [
            "ifc",
            "export-layout",
            "--layout",
            str(layout_path),
            "--out",
            str(ifc_path),
            "--report",
            str(report_path),
            "--markdown",
            str(markdown_path),
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.output
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["opening_provenance"] == {
        "opening_count": 2,
        "semantic_count": 2,
        "measurement_count": 2,
        "host_count": 2,
        "all_three_count": 2,
    }
    assert markdown_path.exists()
    markdown = markdown_path.read_text("utf-8")
    assert "## Opening Provenance Coverage" in markdown
    assert "`semantic` | 2" in markdown
    assert "`measurement` | 2" in markdown
    assert "`host_wall` | 2" in markdown
    assert "`all_three` | 2" in markdown


def test_ifc_export_layout_cli_with_fake_dependency_tracks_window_opening_counts(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _install_fake_ifcopenshell_modules(monkeypatch)
    layout_path = write_layout_3d(
        build_layout_3d(entity_graph=_entity_graph_with_window()),
        tmp_path / "layout_3d.json",
    )
    ifc_path = tmp_path / "layout.ifc"
    report_path = tmp_path / "layout_ifc_export.json"

    result = CliRunner().invoke(
        app,
        [
            "ifc",
            "export-layout",
            "--layout",
            str(layout_path),
            "--out",
            str(ifc_path),
            "--report",
            str(report_path),
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.output
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "exported"
    assert report["exported_counts"]["window_opening"] == 1
    assert report["exported_counts"]["door_opening"] == 1
    assert report["exported_counts"]["wall"] == 8


def test_ifc_export_layout_cli_real_ifcopenshell_smoke(tmp_path: Path) -> None:
    pytest.importorskip("ifcopenshell")
    layout_path = write_layout_3d(
        build_layout_3d(entity_graph=_entity_graph_with_window()),
        tmp_path / "layout_3d.json",
    )
    ifc_path = tmp_path / "layout.ifc"
    report_path = tmp_path / "layout_ifc_export.json"

    result = CliRunner().invoke(
        app,
        [
            "ifc",
            "export-layout",
            "--layout",
            str(layout_path),
            "--out",
            str(ifc_path),
            "--report",
            str(report_path),
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.output
    assert ifc_path.exists()
    assert ifc_path.stat().st_size > 32
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["status"] == "exported"
    assert report["exported_counts"]["window_opening"] == 1




def test_ifc_export_layout_cli_writes_dependency_missing_report(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from archkg.ifc import layout_exporter

    def missing_import(name: str) -> Any:
        if name.startswith("ifcopenshell"):
            raise ModuleNotFoundError(name)
        return __import__(name)

    monkeypatch.setattr(layout_exporter.importlib, "import_module", missing_import)
    layout_path = write_layout_3d(
        build_layout_3d(entity_graph=_entity_graph()),
        tmp_path / "layout_3d.json",
    )
    ifc_path = tmp_path / "layout.ifc"
    report_path = tmp_path / "layout_ifc_export.json"
    markdown_path = tmp_path / "layout_ifc_export.md"

    result = CliRunner().invoke(
        app,
        [
            "ifc",
            "export-layout",
            "--layout",
            str(layout_path),
            "--out",
            str(ifc_path),
            "--report",
            str(report_path),
            "--markdown",
            str(markdown_path),
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 1
    assert "optional dependency" in result.output
    assert "ifcopenshell" in result.output
    assert not ifc_path.exists()
    report = json.loads(report_path.read_text("utf-8"))
    assert report["status"] == "dependency_missing"
    assert report["output_ifc_path"] == str(ifc_path)
    assert report["object_count"] > 0
    assert markdown_path.exists()


def test_ifc_export_layout_cli_blocks_blocked_layout_without_ifc(
    tmp_path: Path,
) -> None:
    layout_path = tmp_path / "layout_3d.json"
    layout_path.write_text(
        json.dumps(
            {
                "schema_version": "layout_3d.v1",
                "model_status": "blocked",
                "source_artifact": "entity_graph.json",
                "source_pdf": "empty.pdf",
                "source_sheet_ids": ["page-0"],
                "scale_basis": {"available": False},
                "summary": {"object_count": 0},
                "objects": [],
                "assumptions": [],
                "blocked_reasons": ["no_layout_entities_available"],
            }
        ),
        encoding="utf-8",
    )
    ifc_path = tmp_path / "layout.ifc"
    ifc_path.write_text("STALE IFC", encoding="utf-8")
    report_path = tmp_path / "layout_ifc_export.json"

    result = CliRunner().invoke(
        app,
        [
            "ifc",
            "export-layout",
            "--layout",
            str(layout_path),
            "--out",
            str(ifc_path),
            "--report",
            str(report_path),
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 1
    assert "blocked" in result.output
    assert not ifc_path.exists()
    report = json.loads(report_path.read_text("utf-8"))
    assert report["status"] == "blocked"
    assert "no_layout_entities_available" in " ".join(report["warnings"])


def _install_fake_ifcopenshell_modules(monkeypatch) -> None:
    ifcopenshell = types.ModuleType("ifcopenshell")
    api_module = types.ModuleType("ifcopenshell.api")
    project_module = types.ModuleType("ifcopenshell.api.project")
    root_module = types.ModuleType("ifcopenshell.api.root")
    unit_module = types.ModuleType("ifcopenshell.api.unit")
    context_module = types.ModuleType("ifcopenshell.api.context")
    aggregate_module = types.ModuleType("ifcopenshell.api.aggregate")
    spatial_module = types.ModuleType("ifcopenshell.api.spatial")
    geometry_module = types.ModuleType("ifcopenshell.api.geometry")

    class FakeEntity:
        def __init__(self, ifc_class: str, name: str | None = None) -> None:
            self.ifc_class = ifc_class
            self.Name = name or ifc_class

    class FakeModel:
        def __init__(self) -> None:
            self.entities: list[FakeEntity] = []
            self.geometry_calls: list[str] = []

        def write(self, path: str) -> None:
            Path(path).write_text(
                "IFC_FAKE\n"
                + "\n".join(entity.ifc_class for entity in self.entities),
                encoding="utf-8",
            )

    def create_file() -> FakeModel:
        return FakeModel()

    def create_entity(model: FakeModel, ifc_class: str, name: str | None = None, **_kwargs: Any) -> FakeEntity:
        entity = FakeEntity(ifc_class, name)
        model.entities.append(entity)
        return entity

    def noop(*_args: Any, **_kwargs: Any) -> None:
        return None

    def add_context(model: FakeModel, **kwargs: Any) -> FakeEntity:
        return create_entity(
            model,
            "IfcGeometricRepresentationContext",
            kwargs.get("context_identifier") or kwargs.get("context_type"),
        )

    def representation(model: FakeModel, **kwargs: Any) -> FakeEntity:
        model.geometry_calls.append(str(kwargs.get("product") or kwargs.get("element") or "geometry"))
        return FakeEntity("IfcShapeRepresentation", "Body")

    project_module.create_file = create_file  # type: ignore[attr-defined]
    root_module.create_entity = create_entity  # type: ignore[attr-defined]
    unit_module.assign_unit = noop  # type: ignore[attr-defined]
    context_module.add_context = add_context  # type: ignore[attr-defined]
    aggregate_module.assign_object = noop  # type: ignore[attr-defined]
    spatial_module.assign_container = noop  # type: ignore[attr-defined]
    geometry_module.edit_object_placement = noop  # type: ignore[attr-defined]
    geometry_module.create_2pt_wall = representation  # type: ignore[attr-defined]
    geometry_module.add_slab_representation = representation  # type: ignore[attr-defined]
    geometry_module.assign_representation = noop  # type: ignore[attr-defined]

    ifcopenshell.api = api_module  # type: ignore[attr-defined]
    api_module.project = project_module  # type: ignore[attr-defined]
    api_module.root = root_module  # type: ignore[attr-defined]
    api_module.unit = unit_module  # type: ignore[attr-defined]
    api_module.context = context_module  # type: ignore[attr-defined]
    api_module.aggregate = aggregate_module  # type: ignore[attr-defined]
    api_module.spatial = spatial_module  # type: ignore[attr-defined]
    api_module.geometry = geometry_module  # type: ignore[attr-defined]

    for name, module in {
        "ifcopenshell": ifcopenshell,
        "ifcopenshell.api": api_module,
        "ifcopenshell.api.project": project_module,
        "ifcopenshell.api.root": root_module,
        "ifcopenshell.api.unit": unit_module,
        "ifcopenshell.api.context": context_module,
        "ifcopenshell.api.aggregate": aggregate_module,
        "ifcopenshell.api.spatial": spatial_module,
        "ifcopenshell.api.geometry": geometry_module,
    }.items():
        monkeypatch.setitem(sys.modules, name, module)


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
            )
        ],
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


def _entity_graph_with_opening_provenance() -> EntityGraph:
    return EntityGraph(
        source_pdf="synthetic-opening-provenance-ifc.pdf",
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
                    "height_m": 2.05,
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
                    "height_m": 1.2,
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
        stairs=[
            Stair(
                id="stair-1",
                page_index=0,
                bbox=(220.0, 20.0, 320.0, 120.0),
                tread_width_m=1.1,
            )
        ],
    )
