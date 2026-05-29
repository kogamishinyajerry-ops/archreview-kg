from __future__ import annotations

import importlib
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from archkg.layout_3d import Layout3DObject, Layout3DReport

SCHEMA_VERSION: Literal["layout_ifc_export.v1"] = "layout_ifc_export.v1"
BOUNDARY_WARNING = (
    "layout.ifc is a preview artifact derived from layout_3d evidence; "
    "it is not a review-grade BIM model and must not be used as a compliance input."
)

LayoutIfcExportStatus = Literal["exported", "dependency_missing", "blocked", "failed"]


class LayoutIfcDependencyError(RuntimeError):
    pass


class LayoutIfcExportReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["layout_ifc_export.v1"] = SCHEMA_VERSION
    status: LayoutIfcExportStatus
    source_layout_path: str
    source_schema_version: str
    output_ifc_path: str
    object_count: int = Field(..., ge=0)
    exported_counts: dict[str, int] = Field(default_factory=dict)
    skipped_counts: dict[str, int] = Field(default_factory=dict)
    assumptions_count: int = Field(..., ge=0)
    opening_provenance: dict[str, int] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    boundary_warning: str = BOUNDARY_WARNING


@dataclass(frozen=True)
class _IfcDeps:
    project: Any
    root: Any
    unit: Any
    context: Any
    aggregate: Any
    spatial: Any
    geometry: Any


def export_layout_ifc(
    *,
    layout_path: Path,
    ifc_path: Path,
    report_path: Path | None = None,
    markdown_path: Path | None = None,
) -> LayoutIfcExportReport:
    layout = _load_layout(layout_path)
    if layout.model_status == "blocked":
        _remove_stale_ifc(ifc_path)
        report = _report(
            status="blocked",
            layout_path=layout_path,
            layout=layout,
            ifc_path=ifc_path,
            warnings=[
                "layout_3d model_status is blocked",
                *layout.blocked_reasons,
            ],
        )
        _write_optional_reports(report, report_path, markdown_path)
        return report

    try:
        deps = _load_dependencies()
    except LayoutIfcDependencyError as exc:
        _remove_stale_ifc(ifc_path)
        report = _report(
            status="dependency_missing",
            layout_path=layout_path,
            layout=layout,
            ifc_path=ifc_path,
            warnings=[str(exc)],
        )
        _write_optional_reports(report, report_path, markdown_path)
        return report

    try:
        exported_counts, skipped_counts = _write_ifc(layout, ifc_path, deps)
    except Exception as exc:
        _remove_stale_ifc(ifc_path)
        report = _report(
            status="failed",
            layout_path=layout_path,
            layout=layout,
            ifc_path=ifc_path,
            warnings=[f"layout IFC export failed: {exc}"],
        )
        _write_optional_reports(report, report_path, markdown_path)
        return report

    report = _report(
        status="exported",
        layout_path=layout_path,
        layout=layout,
        ifc_path=ifc_path,
        exported_counts=dict(exported_counts),
        skipped_counts=dict(skipped_counts),
        warnings=[
            "IFC export is preview-only; door and stair objects are placeholders.",
            "Boolean wall voids, staircase voids, multi-floor stacking, and compliance semantics are not exported.",
        ],
    )
    _write_optional_reports(report, report_path, markdown_path)
    return report


def write_layout_ifc_export_json(report: LayoutIfcExportReport, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def render_layout_ifc_export_markdown(report: LayoutIfcExportReport) -> str:
    lines = [
        "# Layout IFC Export",
        "",
        f"Status: `{report.status}`",
        f"Source layout: `{report.source_layout_path}`",
        f"Output IFC: `{report.output_ifc_path}`",
        "",
        "> IFC preview is not a review-grade BIM model or compliance conclusion.",
        "",
        "## Counts",
        "",
        "| Type | Exported | Skipped |",
        "|---|---:|---:|",
    ]
    keys = sorted(set(report.exported_counts) | set(report.skipped_counts))
    if keys:
        for key in keys:
            lines.append(
                f"| `{key}` | {report.exported_counts.get(key, 0)} | "
                f"{report.skipped_counts.get(key, 0)} |"
            )
    else:
        lines.append("| none | 0 | 0 |")
    lines.extend(["", "## Warnings", ""])
    if report.warnings:
        lines.extend(f"- {warning}" for warning in report.warnings)
    else:
        lines.append("None")
    lines.extend(["", "## Opening Provenance Coverage (preview)", ""])
    lines.extend(
        [
            "| Signal | Count |",
            "|---|---:|",
            (
                f"| `semantic` | {report.opening_provenance.get('semantic_count', 0)} |"
            ),
            (
                f"| `measurement` | {report.opening_provenance.get('measurement_count', 0)} |"
            ),
            (
                f"| `host_wall` | {report.opening_provenance.get('host_count', 0)} |"
            ),
            (
                f"| `all_three` | {report.opening_provenance.get('all_three_count', 0)} |"
            ),
            "",
            "> Opening provenance coverage is preview-only metadata for reviewer orientation and does not change rule or compliance results.",
        ]
    )
    lines.append("")
    return "\n".join(lines)


def write_layout_ifc_export_markdown(report: LayoutIfcExportReport, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_layout_ifc_export_markdown(report), encoding="utf-8")
    return path


def _load_layout(path: Path) -> Layout3DReport:
    raw = json.loads(path.read_text("utf-8"))
    return Layout3DReport.model_validate(raw)


def _write_optional_reports(
    report: LayoutIfcExportReport,
    report_path: Path | None,
    markdown_path: Path | None,
) -> None:
    if report_path is not None:
        write_layout_ifc_export_json(report, report_path)
    if markdown_path is not None:
        write_layout_ifc_export_markdown(report, markdown_path)


def _remove_stale_ifc(path: Path) -> None:
    if path.exists() and path.is_file():
        path.unlink()


def _report(
    *,
    status: LayoutIfcExportStatus,
    layout_path: Path,
    layout: Layout3DReport,
    ifc_path: Path,
    exported_counts: dict[str, int] | None = None,
    skipped_counts: dict[str, int] | None = None,
    warnings: list[str] | None = None,
) -> LayoutIfcExportReport:
    return LayoutIfcExportReport(
        status=status,
        source_layout_path=str(layout_path),
        source_schema_version=layout.schema_version,
        output_ifc_path=str(ifc_path),
        object_count=len(layout.objects),
        exported_counts=exported_counts or {},
        skipped_counts=skipped_counts or {},
        assumptions_count=len(layout.assumptions),
        opening_provenance=_opening_provenance_from_layout(layout),
        warnings=warnings or [],
    )


def _load_dependencies() -> _IfcDeps:
    try:
        importlib.import_module("ifcopenshell")
        project = importlib.import_module("ifcopenshell.api.project")
        root = importlib.import_module("ifcopenshell.api.root")
        unit = importlib.import_module("ifcopenshell.api.unit")
        context = importlib.import_module("ifcopenshell.api.context")
        aggregate = importlib.import_module("ifcopenshell.api.aggregate")
        spatial = importlib.import_module("ifcopenshell.api.spatial")
        geometry = importlib.import_module("ifcopenshell.api.geometry")
    except ModuleNotFoundError as exc:
        raise LayoutIfcDependencyError(
            "Layout IFC export requires optional dependency `ifcopenshell`. "
            "Install the openBIM stack to enable `archkg ifc export-layout`; "
            "PDF review and layout_3d GLB export remain available without it."
        ) from exc
    required = (
        (project, "create_file"),
        (root, "create_entity"),
        (unit, "assign_unit"),
        (context, "add_context"),
        (aggregate, "assign_object"),
        (spatial, "assign_container"),
        (geometry, "edit_object_placement"),
    )
    for module, attr in required:
        if not hasattr(module, attr):
            raise LayoutIfcDependencyError(
                "Layout IFC export found optional IfcOpenShell modules but "
                f"their API is missing `{module.__name__}.{attr}`."
            )
    return _IfcDeps(
        project=project,
        root=root,
        unit=unit,
        context=context,
        aggregate=aggregate,
        spatial=spatial,
        geometry=geometry,
    )


def _write_ifc(
    layout: Layout3DReport,
    ifc_path: Path,
    deps: _IfcDeps,
) -> tuple[Counter[str], Counter[str]]:
    ifc_path.parent.mkdir(parents=True, exist_ok=True)
    model = deps.project.create_file()
    project = deps.root.create_entity(
        model,
        ifc_class="IfcProject",
        name="ArchReview-KG Layout IFC Preview",
    )
    deps.unit.assign_unit(model)
    model_context = deps.context.add_context(model, context_type="Model")
    body_context = deps.context.add_context(
        model,
        context_type="Model",
        context_identifier="Body",
        target_view="MODEL_VIEW",
        parent=model_context,
    )
    site = deps.root.create_entity(model, ifc_class="IfcSite", name="ArchReview-KG Site")
    building = deps.root.create_entity(model, ifc_class="IfcBuilding", name="Layout Building")
    storey = deps.root.create_entity(model, ifc_class="IfcBuildingStorey", name="Ground Floor")
    deps.aggregate.assign_object(model, relating_object=project, products=[site])
    deps.aggregate.assign_object(model, relating_object=site, products=[building])
    deps.aggregate.assign_object(model, relating_object=building, products=[storey])

    exported: Counter[str] = Counter()
    skipped: Counter[str] = Counter()
    for obj in layout.objects:
        if obj.object_type == "dimension_anchor":
            skipped[obj.object_type] += 1
            continue
        ifc_class = _ifc_class_for_object(obj)
        if ifc_class is None:
            skipped[obj.object_type] += 1
            continue
        element = deps.root.create_entity(model, ifc_class=ifc_class, name=obj.object_id)
        deps.geometry.edit_object_placement(model, product=element)
        _assign_geometry(model, element, obj, body_context, deps)
        deps.spatial.assign_container(model, relating_structure=storey, products=[element])
        exported[obj.object_type] += 1

    model.write(str(ifc_path))
    return exported, skipped


def _opening_provenance_from_layout(layout: Layout3DReport) -> dict[str, int]:
    summary = layout.summary or {}
    return {
        "opening_count": int(summary.get("door_opening_count", 0))
        + int(summary.get("window_opening_count", 0)),
        "semantic_count": int(summary.get("opening_provenance_semantic_count", 0)),
        "measurement_count": int(summary.get("opening_provenance_measurement_count", 0)),
        "host_count": int(summary.get("opening_provenance_host_count", 0)),
        "all_three_count": int(summary.get("opening_provenance_all_three_count", 0)),
    }


def _ifc_class_for_object(obj: Layout3DObject) -> str | None:
    return {
        "floor_slab": "IfcSlab",
        "room_volume": "IfcSpace",
        "corridor_volume": "IfcSpace",
        "wall": "IfcWall",
        "door_opening": "IfcDoor",
        "window_opening": "IfcWindow",
        "stair_placeholder": "IfcStair",
    }.get(obj.object_type)


def _assign_geometry(
    model: Any,
    element: Any,
    obj: Layout3DObject,
    body_context: Any,
    deps: _IfcDeps,
) -> None:
    representation: Any | None = None
    if obj.object_type == "wall":
        representation = _wall_representation(model, element, obj, body_context, deps)
    elif obj.object_type == "floor_slab" and hasattr(deps.geometry, "add_slab_representation"):
        representation = deps.geometry.add_slab_representation(
            model,
            context=body_context,
            depth=max(obj.height_m, 0.01),
        )
    if representation is not None and hasattr(deps.geometry, "assign_representation"):
        deps.geometry.assign_representation(
            model,
            product=element,
            representation=representation,
        )


def _wall_representation(
    model: Any,
    element: Any,
    obj: Layout3DObject,
    body_context: Any,
    deps: _IfcDeps,
) -> Any | None:
    p0 = _point_from_property(obj, "p0_m")
    p1 = _point_from_property(obj, "p1_m")
    if p0 is None or p1 is None:
        return None
    thickness = max(obj.dimensions_m.get("thickness_m", 0.2), 0.02)
    height = max(obj.height_m, 0.01)
    if hasattr(deps.geometry, "create_2pt_wall"):
        return deps.geometry.create_2pt_wall(
            model,
            element=element,
            context=body_context,
            p1=p0,
            p2=p1,
            elevation=obj.z_base_m,
            height=height,
            thickness=thickness,
            is_si=True,
        )
    if hasattr(deps.geometry, "add_wall_representation"):
        return deps.geometry.add_wall_representation(
            model,
            context=body_context,
            length=max(obj.dimensions_m.get("length_m", 0.1), 0.1),
            height=height,
            thickness=thickness,
        )
    return None


def _point_from_property(
    obj: Layout3DObject,
    name: str,
) -> tuple[float, float] | None:
    raw = obj.properties.get(name)
    if not isinstance(raw, list) or len(raw) != 2:
        return None
    return (float(raw[0]), float(raw[1]))


__all__ = [
    "LayoutIfcDependencyError",
    "LayoutIfcExportReport",
    "export_layout_ifc",
    "render_layout_ifc_export_markdown",
    "write_layout_ifc_export_json",
    "write_layout_ifc_export_markdown",
]
