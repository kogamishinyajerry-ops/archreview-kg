"""Evidence-oriented 2.5D layout model generation.

The layout_3d artifact is a reviewer navigation aid derived from existing
2D evidence. It is not a design-grade BIM model and must keep every default
height/thickness as an explicit assumption.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from collections.abc import Mapping
from itertools import pairwise
from pathlib import Path
from typing import Any, Literal, cast

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from archkg.graph.builder import EntityGraph
from archkg.graph.sheet_graphs import SheetGraphsReport
from archkg.schemas import Corridor, Dimension, Door, Room, Stair

SCHEMA_VERSION: Literal["layout_3d.v1"] = "layout_3d.v1"

DEFAULT_FLOOR_THICKNESS_M = 0.12
DEFAULT_SPACE_HEIGHT_M = 2.8
DEFAULT_WALL_HEIGHT_M = 2.8
DEFAULT_WALL_THICKNESS_M = 0.20
DEFAULT_DOOR_HEIGHT_M = 2.10
DEFAULT_STAIR_HEIGHT_M = 3.0
DEFAULT_DIMENSION_ANCHOR_SIZE_M = 0.10

Layout3DStatus = Literal["ready", "partial", "blocked"]
Layout3DObjectType = Literal[
    "floor_slab",
    "room_volume",
    "corridor_volume",
    "wall",
    "door_opening",
    "window_opening",
    "stair_placeholder",
    "dimension_anchor",
]
OpeningMeasurementEntry = dict[str, float | str | bool]
OpeningMeasurementMap = dict[str, OpeningMeasurementEntry]
OPENING_MEASUREMENT_FIELDS = ("width_m", "height_m", "sill_height_m", "head_height_m")
OPENING_HOST_WALL_ID_KEYS = ("opening_host_wall_id", "host_wall_id")
OPENING_HOST_SEGMENT_KEYS = ("opening_host_wall_segment", "host_wall_segment")


class Layout3DAssumption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assumption_id: str
    field: str
    value: float | str | bool
    unit: str
    reason: str
    applies_to_object_ids: list[str] = Field(default_factory=list)


class Layout3DObject(BaseModel):
    model_config = ConfigDict(extra="forbid")

    object_id: str
    object_type: Layout3DObjectType
    source_entity_id: str | None = None
    source_entity_type: str | None = None
    source_page_index: int | None = Field(default=None, ge=0)
    source_sheet_id: str | None = None
    bbox_m: tuple[float, float, float, float] | None = None
    footprint: list[tuple[float, float]] = Field(default_factory=list)
    center_m: tuple[float, float, float] | None = None
    z_base_m: float = 0.0
    height_m: float = 0.0
    dimensions_m: dict[str, float] = Field(default_factory=dict)
    confidence: float = Field(1.0, ge=0.0, le=1.0)
    assumption_ids: list[str] = Field(default_factory=list)
    properties: dict[str, Any] = Field(default_factory=dict)


class Layout3DReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["layout_3d.v1"] = SCHEMA_VERSION
    model_status: Layout3DStatus
    source_artifact: str
    source_pdf: str
    source_sheet_ids: list[str] = Field(default_factory=list)
    scale_basis: dict[str, Any] = Field(default_factory=dict)
    summary: dict[str, int | str] = Field(default_factory=dict)
    objects: list[Layout3DObject] = Field(default_factory=list)
    assumptions: list[Layout3DAssumption] = Field(default_factory=list)
    blocked_reasons: list[str] = Field(default_factory=list)
    boundary_warning: str = (
        "layout_3d is an evidence/navigation model only; default values are "
        "visualization assumptions and must not be treated as compliance facts."
    )


class _GraphSource(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    graph: EntityGraph
    source_sheet_id: str
    source_artifact: str
    classification_confidence: float = 1.0


def build_layout_3d(
    *,
    sheet_graphs: SheetGraphsReport | Mapping[str, Any] | None = None,
    entity_graph: EntityGraph | Mapping[str, Any] | None = None,
) -> Layout3DReport:
    """Build a deterministic 2.5D layout model from graph evidence."""

    graph_sources, source_artifact, blocked_reasons = _select_graph_sources(
        sheet_graphs=sheet_graphs,
        entity_graph=entity_graph,
    )
    if not graph_sources:
        return Layout3DReport(
            model_status="blocked",
            source_artifact=source_artifact,
            source_pdf="",
            source_sheet_ids=[],
            scale_basis={"available": False, "reason": "no graph evidence"},
            summary=_summary([]),
            blocked_reasons=[*blocked_reasons, "no_graph_evidence_available"],
        )

    objects: list[Layout3DObject] = []
    assumption_by_id = _default_assumptions()
    source_sheet_ids = [source.source_sheet_id for source in graph_sources]

    for source in graph_sources:
        objects.extend(_objects_for_graph(source, assumption_by_id))

    if not objects:
        return Layout3DReport(
            model_status="blocked",
            source_artifact=source_artifact,
            source_pdf=graph_sources[0].graph.source_pdf,
            source_sheet_ids=source_sheet_ids,
            scale_basis=_scale_basis(graph_sources[0].graph),
            summary=_summary(objects),
            blocked_reasons=[*blocked_reasons, "no_layout_entities_available"],
        )

    blocked = list(blocked_reasons)
    assumptions = [
        assumption
        for assumption in assumption_by_id.values()
        if assumption.applies_to_object_ids
    ]
    status: Layout3DStatus = "partial" if assumptions or blocked else "ready"
    return Layout3DReport(
        model_status=status,
        source_artifact=source_artifact,
        source_pdf=graph_sources[0].graph.source_pdf,
        source_sheet_ids=source_sheet_ids,
        scale_basis=_scale_basis(graph_sources[0].graph),
        summary=_summary(objects),
        objects=objects,
        assumptions=assumptions,
        blocked_reasons=blocked,
    )


def write_layout_3d(report: Layout3DReport, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return out_path


def render_layout_3d_summary_markdown(report: Layout3DReport) -> str:
    lines = [
        "# 3D Layout Evidence",
        "",
        f"Status: `{report.model_status}`",
        f"Source artifact: `{report.source_artifact}`",
        f"Source sheets: `{', '.join(report.source_sheet_ids) or 'none'}`",
        "",
        "> 默认值只用于 3D 辅助可视化, 不是审查结论、BIM 真值或规范判断输入。",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|---|---:|",
    ]
    for key, value in report.summary.items():
        lines.append(f"| `{key}` | {value} |")
    lines.extend(
        [
            "",
            "## Opening Semantics",
            "",
            "| Type | Count | Boundary |",
            "|---|---:|---|",
            (
                f"| `door_opening` | {report.summary.get('door_opening_count', 0)} | "
                "graph Door entity default |"
            ),
            (
                f"| `window_opening` | {report.summary.get('window_opening_count', 0)} | "
                "explicit graph evidence only |"
            ),
            "",
            "> Opening semantics are reviewer navigation evidence only; they do not carve wall voids or create compliance findings.",
            "",
            "## Opening Measurements",
            "",
            "| Field | Explicit Count | Boundary |",
            "|---|---:|---|",
            (
                f"| `width_m` | {report.summary.get('opening_measured_width_count', 0)} | "
                "explicit `Door.width_m` only |"
            ),
            (
                f"| `height_m` | {report.summary.get('opening_measured_height_count', 0)} | "
                "explicit `Door.properties.height_m` only |"
            ),
            (
                f"| `sill_height_m` | {report.summary.get('opening_measured_sill_height_count', 0)} | "
                "explicit `Door.properties.sill_height_m` only |"
            ),
            (
                f"| `head_height_m` | {report.summary.get('opening_measured_head_height_count', 0)} | "
                "explicit `Door.properties.head_height_m` only |"
            ),
            "",
            "> Opening measurements are preview provenance only; missing fields continue to use explicit visualization assumptions.",
            "",
            "## Opening Host Wall Provenance",
            "",
            "| Field | Explicit Count | Boundary |",
            "|---|---:|---|",
            (
                f"| `host_wall_id` | {report.summary.get('opening_host_wall_count', 0)} | "
                "explicit `Door.properties.opening_host_wall_id` only |"
            ),
            (
                f"| `host_wall_segment` | {report.summary.get('opening_host_segment_count', 0)} | "
                "explicit `Door.properties.opening_host_wall_segment` only |"
            ),
            "",
            "> Opening host-wall provenance is navigation metadata only; it does not imply boolean wall carving or compliance input.",
        ]
    )
    lines.extend(["", "## Assumptions", ""])
    if report.assumptions:
        for assumption in report.assumptions:
            lines.append(
                f"- `{assumption.field}` = `{assumption.value}` {assumption.unit}: "
                f"{assumption.reason} ({len(assumption.applies_to_object_ids)} object(s))"
            )
    else:
        lines.append("None")
    lines.extend(["", "## Blocked / Not Modeled", ""])
    if report.blocked_reasons:
        lines.extend(f"- `{reason}`" for reason in report.blocked_reasons)
    else:
        lines.append("None")
    lines.append("")
    return "\n".join(lines)


def write_layout_3d_summary(report: Layout3DReport, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_layout_3d_summary_markdown(report), encoding="utf-8")
    return out_path


def export_layout_3d_glb(report: Layout3DReport, out_path: Path) -> Path:
    """Export a simple GLB visualization using trimesh."""

    import trimesh

    out_path.parent.mkdir(parents=True, exist_ok=True)
    scene = trimesh.Scene()
    for obj in report.objects:
        mesh = _mesh_for_object(obj)
        if mesh is None:
            continue
        _apply_vertex_color(mesh, _rgba_for_type(obj.object_type))
        scene.add_geometry(mesh, geom_name=obj.object_id, node_name=obj.object_id)
    if not scene.geometry:
        # Keep a valid GLB artifact for blocked/empty cases.
        mesh = trimesh.creation.box(extents=(0.1, 0.1, 0.1))
        _apply_vertex_color(mesh, (160, 160, 160, 140))
        scene.add_geometry(mesh, geom_name="layout_3d_empty", node_name="layout_3d_empty")
    scene_any = cast(Any, scene)
    exported = scene_any.export(file_type="glb")
    if not isinstance(exported, bytes):
        exported = bytes(exported)
    out_path.write_bytes(exported)
    return out_path


def _select_graph_sources(
    *,
    sheet_graphs: SheetGraphsReport | Mapping[str, Any] | None,
    entity_graph: EntityGraph | Mapping[str, Any] | None,
) -> tuple[list[_GraphSource], str, list[str]]:
    sheet_report = _coerce_sheet_graphs(sheet_graphs)
    if sheet_report is not None and sheet_report.graphs:
        return (
            [
                _GraphSource(
                    graph=entry.graph,
                    source_sheet_id=f"page-{entry.page_index}",
                    source_artifact="sheet_graphs.json",
                    classification_confidence=entry.classification_confidence,
                )
                for entry in sheet_report.graphs
            ],
            "sheet_graphs.json",
            [],
        )
    graph = _coerce_entity_graph(entity_graph)
    if graph is not None:
        return (
            [
                _GraphSource(
                    graph=graph,
                    source_sheet_id=f"page-{graph.page_index}",
                    source_artifact="entity_graph.json",
                )
            ],
            "entity_graph.json",
            ["sheet_graphs_missing_or_empty"],
        )
    return [], "none", ["sheet_graphs_missing_or_empty", "entity_graph_missing"]


def _coerce_sheet_graphs(
    raw: SheetGraphsReport | Mapping[str, Any] | None,
) -> SheetGraphsReport | None:
    if raw is None:
        return None
    if isinstance(raw, SheetGraphsReport):
        return raw
    try:
        return SheetGraphsReport.model_validate(raw)
    except Exception:
        return None


def _coerce_entity_graph(raw: EntityGraph | Mapping[str, Any] | None) -> EntityGraph | None:
    if raw is None:
        return None
    if isinstance(raw, EntityGraph):
        return raw
    try:
        return EntityGraph.model_validate(raw)
    except Exception:
        return None


def _objects_for_graph(
    source: _GraphSource,
    assumptions: dict[str, Layout3DAssumption],
) -> list[Layout3DObject]:
    graph = source.graph
    objects: list[Layout3DObject] = []
    layout_entities: list[Room | Corridor | Door | Stair | Dimension] = [
        *graph.rooms,
        *graph.corridors,
        *graph.doors,
        *graph.stairs,
        *graph.dimensions,
    ]
    if not layout_entities:
        return []

    slab = _floor_slab(source, layout_entities)
    _apply_assumption(slab, assumptions["A-FLOOR-SLAB-THICKNESS"])
    objects.append(slab)
    for room in graph.rooms:
        obj = _space_object(
            room,
            source,
            object_type="room_volume",
            height_m=DEFAULT_SPACE_HEIGHT_M,
        )
        _apply_assumption(obj, assumptions["A-ROOM-VOLUME-HEIGHT"])
        objects.append(obj)
        objects.extend(_wall_objects_for_polygon(room, source, assumptions))
    for corridor in graph.corridors:
        obj = _space_object(
            corridor,
            source,
            object_type="corridor_volume",
            height_m=DEFAULT_SPACE_HEIGHT_M,
        )
        _apply_assumption(obj, assumptions["A-ROOM-VOLUME-HEIGHT"])
        objects.append(obj)
        objects.extend(_wall_objects_for_polygon(corridor, source, assumptions))
    for door in graph.doors:
        if _is_explicit_window_opening(door):
            obj = _window_opening_object(door, source)
            if not _has_explicit_opening_measurement(obj, "height_m"):
                _apply_assumption(obj, assumptions["A-WINDOW-OPENING-HEIGHT"])
        else:
            obj = _door_object(door, source)
            if not _has_explicit_opening_measurement(obj, "height_m"):
                _apply_assumption(obj, assumptions["A-DOOR-OPENING-HEIGHT"])
        if "thickness_m" in obj.dimensions_m:
            _apply_assumption(obj, assumptions["A-WALL-THICKNESS"])
        objects.append(obj)
    for stair in graph.stairs:
        obj = _stair_object(stair, source)
        _apply_assumption(obj, assumptions["A-STAIR-PLACEHOLDER-HEIGHT"])
        objects.append(obj)
    for dim in graph.dimensions:
        objects.append(_dimension_anchor_object(dim, source))
    return objects


def _floor_slab(
    source: _GraphSource,
    entities: list[Room | Corridor | Door | Stair | Dimension],
) -> Layout3DObject:
    graph = source.graph
    boxes = [entity.bbox for entity in entities]
    x0 = min(box[0] for box in boxes) / graph.points_per_meter
    y0 = min(box[1] for box in boxes) / graph.points_per_meter
    x1 = max(box[2] for box in boxes) / graph.points_per_meter
    y1 = max(box[3] for box in boxes) / graph.points_per_meter
    return Layout3DObject(
        object_id=f"{source.source_sheet_id}-floor-slab",
        object_type="floor_slab",
        source_page_index=graph.page_index,
        source_sheet_id=source.source_sheet_id,
        bbox_m=(x0, y0, x1, y1),
        footprint=[(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)],
        center_m=((x0 + x1) / 2, (y0 + y1) / 2, -DEFAULT_FLOOR_THICKNESS_M / 2),
        z_base_m=-DEFAULT_FLOOR_THICKNESS_M,
        height_m=DEFAULT_FLOOR_THICKNESS_M,
        dimensions_m={
            "width_m": max(x1 - x0, 0.0),
            "depth_m": max(y1 - y0, 0.0),
            "thickness_m": DEFAULT_FLOOR_THICKNESS_M,
        },
        confidence=source.classification_confidence,
        properties={"derived_from": "layout_entity_bounds"},
    )


def _space_object(
    entity: Room | Corridor,
    source: _GraphSource,
    *,
    object_type: Literal["room_volume", "corridor_volume"],
    height_m: float,
) -> Layout3DObject:
    graph = source.graph
    footprint = _polygon_m(entity.polygon, graph.points_per_meter)
    bbox_m = _bbox_m(entity.bbox, graph.points_per_meter)
    x0, y0, x1, y1 = bbox_m
    properties: dict[str, Any] = {}
    if isinstance(entity, Room):
        properties.update({"label": entity.label or "", "area_m2": entity.area_m2})
    if isinstance(entity, Corridor):
        properties.update({"min_width_m": entity.min_width_m})
    return Layout3DObject(
        object_id=f"{source.source_sheet_id}-{object_type}-{entity.id}",
        object_type=object_type,
        source_entity_id=entity.id,
        source_entity_type=entity.type,
        source_page_index=entity.page_index,
        source_sheet_id=source.source_sheet_id,
        bbox_m=bbox_m,
        footprint=footprint,
        center_m=((x0 + x1) / 2, (y0 + y1) / 2, height_m / 2),
        z_base_m=0.0,
        height_m=height_m,
        dimensions_m={
            "width_m": max(x1 - x0, 0.0),
            "depth_m": max(y1 - y0, 0.0),
            "height_m": height_m,
        },
        confidence=entity.confidence,
        properties=properties,
    )


def _wall_objects_for_polygon(
    entity: Room | Corridor,
    source: _GraphSource,
    assumptions: dict[str, Layout3DAssumption],
) -> list[Layout3DObject]:
    graph = source.graph
    points = _polygon_m(entity.polygon, graph.points_per_meter)
    objects: list[Layout3DObject] = []
    for index, (p0, p1) in enumerate(pairwise(points)):
        length = _distance(p0, p1)
        if length <= 0:
            continue
        obj = Layout3DObject(
            object_id=f"{source.source_sheet_id}-wall-{entity.id}-{index:02d}",
            object_type="wall",
            source_entity_id=entity.id,
            source_entity_type=entity.type,
            source_page_index=entity.page_index,
            source_sheet_id=source.source_sheet_id,
            footprint=[p0, p1],
            center_m=((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2, DEFAULT_WALL_HEIGHT_M / 2),
            z_base_m=0.0,
            height_m=DEFAULT_WALL_HEIGHT_M,
            dimensions_m={
                "length_m": length,
                "height_m": DEFAULT_WALL_HEIGHT_M,
                "thickness_m": DEFAULT_WALL_THICKNESS_M,
            },
            confidence=entity.confidence,
            properties={
                "p0_m": list(p0),
                "p1_m": list(p1),
                "derived_from": "space_boundary",
            },
        )
        _apply_assumption(obj, assumptions["A-WALL-HEIGHT"])
        _apply_assumption(obj, assumptions["A-WALL-THICKNESS"])
        objects.append(obj)
    return objects


def _door_object(door: Door, source: _GraphSource) -> Layout3DObject:
    bbox_m = _bbox_m(door.bbox, source.graph.points_per_meter)
    x0, y0, x1, y1 = bbox_m
    width = door.width_m or max(x1 - x0, y1 - y0)
    measurement = _opening_measurement_evidence(door)
    height = _measurement_value(measurement, "height_m") or DEFAULT_DOOR_HEIGHT_M
    properties: dict[str, Any] = {
        "connects": [door.connects[0], door.connects[1]],
        "opening_semantic": _opening_semantic_evidence(door),
    }
    if measurement:
        properties["opening_measurement"] = measurement
    host_provenance = _opening_host_wall_provenance(door)
    if host_provenance:
        properties["opening_host"] = host_provenance
    return Layout3DObject(
        object_id=f"{source.source_sheet_id}-door-opening-{door.id}",
        object_type="door_opening",
        source_entity_id=door.id,
        source_entity_type=door.type,
        source_page_index=door.page_index,
        source_sheet_id=source.source_sheet_id,
        bbox_m=bbox_m,
        footprint=[(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)],
        center_m=((x0 + x1) / 2, (y0 + y1) / 2, height / 2),
        z_base_m=0.0,
        height_m=height,
        dimensions_m={
            "width_m": width,
            "height_m": height,
            "thickness_m": DEFAULT_WALL_THICKNESS_M,
        },
        confidence=door.confidence,
        properties=properties,
    )


def _is_explicit_window_opening(door: Door) -> bool:
    return _opening_semantic_evidence(door)["kind"] == "window_opening"


def _opening_semantic_evidence(door: Door) -> dict[str, str | bool]:
    opening_kind = door.properties.get("opening_kind")
    if isinstance(opening_kind, str) and opening_kind.strip().lower() in {
        "window",
        "window_opening",
    }:
        return {
            "kind": "window_opening",
            "explicit": True,
            "source_property": "opening_kind",
            "source_value": opening_kind,
        }
    if door.properties.get("is_window") is True:
        return {
            "kind": "window_opening",
            "explicit": True,
            "source_property": "is_window",
            "source_value": True,
        }
    return {
        "kind": "door_opening",
        "explicit": False,
        "source_property": "entity_type",
        "source_value": door.type,
    }


def _opening_measurement_evidence(door: Door) -> OpeningMeasurementMap:
    measurement: OpeningMeasurementMap = {}
    width = _finite_measurement(door.width_m, allow_zero=False)
    if width is not None:
        measurement["width_m"] = _measurement_entry(width, "Door.width_m")
    for field in ("height_m", "sill_height_m", "head_height_m"):
        value = _finite_measurement(
            door.properties.get(field),
            allow_zero=field == "sill_height_m",
        )
        if value is not None:
            measurement[field] = _measurement_entry(value, f"Door.properties.{field}")
    return measurement


def _measurement_entry(value: float, source_property: str) -> OpeningMeasurementEntry:
    return {
        "value": value,
        "unit": "m",
        "explicit": True,
        "source_property": source_property,
    }


def _opening_host_wall_provenance(door: Door) -> dict[str, Any]:
    host_wall_id, host_property = _first_property_str(door.properties, OPENING_HOST_WALL_ID_KEYS)
    if host_wall_id is None:
        return {}
    source_property = f"Door.properties.{host_property}"
    provenance: dict[str, Any] = {
        "host_wall_id": host_wall_id,
        "source_property": source_property,
        "explicit": True,
    }
    segment = _opening_host_wall_segment(door.properties)
    if segment is not None:
        provenance["source_segment"] = segment
        provenance["source_segment_property"] = _source_property_for_host_segment(door.properties)
    return provenance


def _first_property_str(
    raw_properties: dict[str, float | int | str | bool],
    candidates: tuple[str, ...],
) -> tuple[str | None, str]:
    for candidate in candidates:
        raw = raw_properties.get(candidate)
        if isinstance(raw, str) and raw.strip():
            return raw.strip(), candidate
    return None, ""


def _source_property_for_host_segment(raw_properties: dict[str, float | int | str | bool]) -> str:
    for candidate in OPENING_HOST_SEGMENT_KEYS:
        if candidate in raw_properties and isinstance(raw_properties.get(candidate), (dict, list, tuple)):
            return f"Door.properties.{candidate}"
    return "Door.properties.opening_host_wall_segment"


def _opening_host_wall_segment(
    raw_properties: dict[str, float | int | str | bool],
) -> dict[str, list[float]] | None:
    segment_property = _first_property_mapping(raw_properties, OPENING_HOST_SEGMENT_KEYS)
    if segment_property is None:
        return None
    return segment_property


def _first_property_mapping(
    raw_properties: dict[str, float | int | str | bool],
    candidates: tuple[str, ...],
) -> dict[str, list[float]] | None:
    for candidate in candidates:
        raw = raw_properties.get(candidate)
        parsed = _normalize_host_segment(raw)
        if parsed is not None:
            return parsed
    return None


def _normalize_host_segment(raw: object) -> dict[str, list[float]] | None:
    if isinstance(raw, Mapping):
        p0_raw = raw.get("p0")
        p1_raw = raw.get("p1")
    elif (
        isinstance(raw, (list, tuple))
        and len(raw) == 2
        and isinstance(raw[0], (list, tuple))
        and isinstance(raw[1], (list, tuple))
    ):
        p0_raw, p1_raw = raw
    elif isinstance(raw, str):
        raw_points = raw.split(";", maxsplit=1)
        if len(raw_points) != 2:
            return None
        p0_raw = _parse_host_segment_point(raw_points[0])
        p1_raw = _parse_host_segment_point(raw_points[1])
        if p0_raw is None or p1_raw is None:
            return None
    else:
        return None

    p0 = _point_as_floats(p0_raw)
    p1 = _point_as_floats(p1_raw)
    if p0 is None or p1 is None:
        return None
    return {"p0": p0, "p1": p1}


def _point_as_floats(raw: object) -> list[float] | None:
    if not (isinstance(raw, (list, tuple)) and len(raw) == 2):
        return None
    point = []
    for value in raw:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        if not math.isfinite(float(value)):
            return None
        point.append(float(value))
    return point


def _parse_host_segment_point(raw: str) -> tuple[float, float] | None:
    parts = [part.strip() for part in raw.split(",", maxsplit=2)]
    if len(parts) != 2:
        return None
    try:
        return (float(parts[0]), float(parts[1]))
    except ValueError:
        return None


def _measurement_value(measurement: OpeningMeasurementMap, field: str) -> float | None:
    entry = measurement.get(field)
    if entry is None:
        return None
    return _finite_measurement(entry.get("value"), allow_zero=True)


def _finite_measurement(raw: object, *, allow_zero: bool) -> float | None:
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return None
    value = float(raw)
    if not math.isfinite(value):
        return None
    if allow_zero:
        return value if value >= 0 else None
    return value if value > 0 else None


def _has_explicit_opening_measurement(obj: Layout3DObject, field: str) -> bool:
    measurement = obj.properties.get("opening_measurement")
    if not isinstance(measurement, Mapping):
        return False
    entry = measurement.get(field)
    if not isinstance(entry, Mapping):
        return False
    return entry.get("explicit") is True and _finite_measurement(
        entry.get("value"),
        allow_zero=True,
    ) is not None


def _window_opening_object(door: Door, source: _GraphSource) -> Layout3DObject:
    bbox_m = _bbox_m(door.bbox, source.graph.points_per_meter)
    x0, y0, x1, y1 = bbox_m
    width = door.width_m or max(x1 - x0, y1 - y0)
    measurement = _opening_measurement_evidence(door)
    height = _measurement_value(measurement, "height_m") or DEFAULT_DOOR_HEIGHT_M
    properties: dict[str, Any] = {
        "connects": [door.connects[0], door.connects[1]],
        "source_door_id": door.id,
        "opening_kind": "window",
        "opening_semantic": _opening_semantic_evidence(door),
    }
    if measurement:
        properties["opening_measurement"] = measurement
    host_provenance = _opening_host_wall_provenance(door)
    if host_provenance:
        properties["opening_host"] = host_provenance
    return Layout3DObject(
        object_id=f"{source.source_sheet_id}-window-opening-{door.id}",
        object_type="window_opening",
        source_entity_id=door.id,
        source_entity_type=door.type,
        source_page_index=door.page_index,
        source_sheet_id=source.source_sheet_id,
        bbox_m=bbox_m,
        footprint=[(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)],
        center_m=((x0 + x1) / 2, (y0 + y1) / 2, height / 2),
        z_base_m=0.0,
        height_m=height,
        dimensions_m={
            "width_m": width,
            "height_m": height,
            "thickness_m": DEFAULT_WALL_THICKNESS_M,
        },
        confidence=door.confidence,
        properties=properties,
    )


def _stair_object(stair: Stair, source: _GraphSource) -> Layout3DObject:
    bbox_m = _bbox_m(stair.bbox, source.graph.points_per_meter)
    x0, y0, x1, y1 = bbox_m
    return Layout3DObject(
        object_id=f"{source.source_sheet_id}-stair-placeholder-{stair.id}",
        object_type="stair_placeholder",
        source_entity_id=stair.id,
        source_entity_type=stair.type,
        source_page_index=stair.page_index,
        source_sheet_id=source.source_sheet_id,
        bbox_m=bbox_m,
        footprint=[(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)],
        center_m=((x0 + x1) / 2, (y0 + y1) / 2, DEFAULT_STAIR_HEIGHT_M / 2),
        z_base_m=0.0,
        height_m=DEFAULT_STAIR_HEIGHT_M,
        dimensions_m={
            "width_m": max(x1 - x0, 0.0),
            "depth_m": max(y1 - y0, 0.0),
            "height_m": DEFAULT_STAIR_HEIGHT_M,
        },
        confidence=stair.confidence,
        properties={"tread_width_m": stair.tread_width_m, "riser_height_m": stair.riser_height_m},
    )


def _dimension_anchor_object(dim: Dimension, source: _GraphSource) -> Layout3DObject:
    bbox_m = _bbox_m(dim.bbox, source.graph.points_per_meter)
    x0, y0, x1, y1 = bbox_m
    return Layout3DObject(
        object_id=f"{source.source_sheet_id}-dimension-anchor-{dim.id}",
        object_type="dimension_anchor",
        source_entity_id=dim.id,
        source_entity_type=dim.type,
        source_page_index=dim.page_index,
        source_sheet_id=source.source_sheet_id,
        bbox_m=bbox_m,
        center_m=((x0 + x1) / 2, (y0 + y1) / 2, DEFAULT_DIMENSION_ANCHOR_SIZE_M / 2),
        z_base_m=0.0,
        height_m=DEFAULT_DIMENSION_ANCHOR_SIZE_M,
        dimensions_m={
            "width_m": DEFAULT_DIMENSION_ANCHOR_SIZE_M,
            "depth_m": DEFAULT_DIMENSION_ANCHOR_SIZE_M,
            "height_m": DEFAULT_DIMENSION_ANCHOR_SIZE_M,
        },
        confidence=dim.confidence,
        properties={"text": dim.text, "value_m": dim.value_m, "unit": dim.unit},
    )


def _default_assumptions() -> dict[str, Layout3DAssumption]:
    return {
        "A-FLOOR-SLAB-THICKNESS": Layout3DAssumption(
            assumption_id="A-FLOOR-SLAB-THICKNESS",
            field="floor_slab.thickness_m",
            value=DEFAULT_FLOOR_THICKNESS_M,
            unit="m",
            reason="floor slab thickness is not extracted from 2D plan evidence",
        ),
        "A-ROOM-VOLUME-HEIGHT": Layout3DAssumption(
            assumption_id="A-ROOM-VOLUME-HEIGHT",
            field="room_volume.height_m",
            value=DEFAULT_SPACE_HEIGHT_M,
            unit="m",
            reason="space height is not extracted from the plan graph",
        ),
        "A-WALL-HEIGHT": Layout3DAssumption(
            assumption_id="A-WALL-HEIGHT",
            field="wall.height_m",
            value=DEFAULT_WALL_HEIGHT_M,
            unit="m",
            reason="wall height is not available in the 2D graph",
        ),
        "A-WALL-THICKNESS": Layout3DAssumption(
            assumption_id="A-WALL-THICKNESS",
            field="wall.thickness_m",
            value=DEFAULT_WALL_THICKNESS_M,
            unit="m",
            reason="wall thickness is not available in the 2D graph",
        ),
        "A-DOOR-OPENING-HEIGHT": Layout3DAssumption(
            assumption_id="A-DOOR-OPENING-HEIGHT",
            field="door_opening.height_m",
            value=DEFAULT_DOOR_HEIGHT_M,
            unit="m",
            reason="door opening height is not extracted from current evidence",
        ),
        "A-WINDOW-OPENING-HEIGHT": Layout3DAssumption(
            assumption_id="A-WINDOW-OPENING-HEIGHT",
            field="window_opening.height_m",
            value=DEFAULT_DOOR_HEIGHT_M,
            unit="m",
            reason="window opening height is not extracted from current evidence",
        ),
        "A-STAIR-PLACEHOLDER-HEIGHT": Layout3DAssumption(
            assumption_id="A-STAIR-PLACEHOLDER-HEIGHT",
            field="stair_placeholder.height_m",
            value=DEFAULT_STAIR_HEIGHT_M,
            unit="m",
            reason="stair vertical extent is not extracted from current evidence",
        ),
    }


def _apply_assumption(obj: Layout3DObject, assumption: Layout3DAssumption) -> None:
    if assumption.assumption_id not in obj.assumption_ids:
        obj.assumption_ids.append(assumption.assumption_id)
    if obj.object_id not in assumption.applies_to_object_ids:
        assumption.applies_to_object_ids.append(obj.object_id)


def _scale_basis(graph: EntityGraph) -> dict[str, Any]:
    return {
        "available": graph.points_per_meter > 0,
        "points_per_meter": graph.points_per_meter,
        "unit": "meter",
        "source": "EntityGraph.points_per_meter",
    }


def _summary(objects: list[Layout3DObject]) -> dict[str, int | str]:
    counter = Counter(obj.object_type for obj in objects)
    opening_measurements = _opening_measurement_counts(objects)
    opening_host_counts = _opening_host_counts(objects)
    return {
        "object_count": len(objects),
        "mesh_object_count": len([obj for obj in objects if _has_mesh(obj)]),
        "floor_slab_count": int(counter.get("floor_slab", 0)),
        "room_volume_count": int(counter.get("room_volume", 0)),
        "corridor_volume_count": int(counter.get("corridor_volume", 0)),
        "wall_count": int(counter.get("wall", 0)),
        "door_opening_count": int(counter.get("door_opening", 0)),
        "window_opening_count": int(counter.get("window_opening", 0)),
        "stair_placeholder_count": int(counter.get("stair_placeholder", 0)),
        "dimension_anchor_count": int(counter.get("dimension_anchor", 0)),
        "opening_measured_width_count": opening_measurements["width_m"],
        "opening_measured_height_count": opening_measurements["height_m"],
        "opening_measured_sill_height_count": opening_measurements["sill_height_m"],
        "opening_measured_head_height_count": opening_measurements["head_height_m"],
        "opening_host_wall_count": opening_host_counts["host_wall"],
        "opening_host_segment_count": opening_host_counts["host_segment"],
    }


def _opening_measurement_counts(objects: list[Layout3DObject]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for obj in objects:
        if obj.object_type not in {"door_opening", "window_opening"}:
            continue
        for field in OPENING_MEASUREMENT_FIELDS:
            if _has_explicit_opening_measurement(obj, field):
                counts[field] += 1
    return counts


def _opening_host_counts(objects: list[Layout3DObject]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for obj in objects:
        if obj.object_type not in {"door_opening", "window_opening"}:
            continue
        raw_host = obj.properties.get("opening_host")
        host: dict[str, Any] = raw_host if isinstance(raw_host, dict) else {}
        if _has_opening_host(host):
            counts["host_wall"] += 1
            if isinstance(host.get("source_segment"), Mapping):
                counts["host_segment"] += 1
    return {"host_wall": int(counts["host_wall"]), "host_segment": int(counts["host_segment"])}


def _has_opening_host(host: dict[str, Any]) -> bool:
    host_wall_id = host.get("host_wall_id")
    return isinstance(host_wall_id, str) and bool(host_wall_id.strip())


def _bbox_m(
    bbox: tuple[float, float, float, float],
    ppm: float,
) -> tuple[float, float, float, float]:
    return (
        float(bbox[0]) / ppm,
        float(bbox[1]) / ppm,
        float(bbox[2]) / ppm,
        float(bbox[3]) / ppm,
    )


def _polygon_m(points: list[tuple[float, float]], ppm: float) -> list[tuple[float, float]]:
    return [(float(x) / ppm, float(y) / ppm) for x, y in points]


def _distance(p0: tuple[float, float], p1: tuple[float, float]) -> float:
    return math.hypot(p1[0] - p0[0], p1[1] - p0[1])


def _has_mesh(obj: Layout3DObject) -> bool:
    return obj.center_m is not None or bool(obj.footprint)


def _mesh_for_object(obj: Layout3DObject) -> Any | None:
    import trimesh

    if obj.object_type == "wall":
        return _wall_mesh(obj)
    if obj.center_m is None:
        return None
    width = max(obj.dimensions_m.get("width_m", 0.0), DEFAULT_DIMENSION_ANCHOR_SIZE_M)
    depth = max(obj.dimensions_m.get("depth_m", 0.0), DEFAULT_DIMENSION_ANCHOR_SIZE_M)
    height = max(obj.height_m, DEFAULT_DIMENSION_ANCHOR_SIZE_M)
    transform = np.eye(4)
    transform[:3, 3] = np.array(obj.center_m)
    return trimesh.creation.box(extents=(width, depth, height), transform=transform)


def _wall_mesh(obj: Layout3DObject) -> Any | None:
    import trimesh

    p0_raw = obj.properties.get("p0_m")
    p1_raw = obj.properties.get("p1_m")
    if not (
        isinstance(p0_raw, list)
        and len(p0_raw) == 2
        and isinstance(p1_raw, list)
        and len(p1_raw) == 2
    ):
        return None
    p0 = (float(p0_raw[0]), float(p0_raw[1]))
    p1 = (float(p1_raw[0]), float(p1_raw[1]))
    length = max(_distance(p0, p1), DEFAULT_DIMENSION_ANCHOR_SIZE_M)
    thickness = max(obj.dimensions_m.get("thickness_m", DEFAULT_WALL_THICKNESS_M), 0.02)
    height = max(obj.height_m, DEFAULT_DIMENSION_ANCHOR_SIZE_M)
    cx = (p0[0] + p1[0]) / 2
    cy = (p0[1] + p1[1]) / 2
    angle = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
    rotation_matrix = cast(Any, trimesh.transformations.rotation_matrix)
    transform = rotation_matrix(angle, (0, 0, 1))
    transform[:3, 3] = np.array([cx, cy, height / 2])
    return trimesh.creation.box(extents=(length, thickness, height), transform=transform)


def _rgba_for_type(obj_type: Layout3DObjectType) -> tuple[int, int, int, int]:
    return {
        "floor_slab": (180, 190, 205, 130),
        "room_volume": (80, 150, 255, 70),
        "corridor_volume": (80, 210, 170, 75),
        "wall": (82, 92, 115, 230),
        "door_opening": (245, 175, 64, 210),
        "window_opening": (96, 205, 255, 180),
        "stair_placeholder": (170, 110, 245, 190),
        "dimension_anchor": (255, 95, 95, 220),
    }[obj_type]


def _apply_vertex_color(mesh: Any, rgba: tuple[int, int, int, int]) -> None:
    mesh.visual.vertex_colors = np.tile(np.array(rgba, dtype=np.uint8), (len(mesh.vertices), 1))


__all__ = [
    "Layout3DAssumption",
    "Layout3DObject",
    "Layout3DReport",
    "build_layout_3d",
    "export_layout_3d_glb",
    "render_layout_3d_summary_markdown",
    "write_layout_3d",
    "write_layout_3d_summary",
]
