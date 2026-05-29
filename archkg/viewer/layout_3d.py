"""Viewer adapter for layout_3d artifacts."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any


def load_layout_3d_view(out_dir: Path) -> dict[str, Any]:
    path = out_dir / "layout_3d.json"
    if not path.exists():
        return _missing_view("layout_3d.json missing")
    try:
        raw = json.loads(path.read_text("utf-8"))
    except Exception as exc:
        return _missing_view(f"could not read layout_3d.json: {exc}")
    if not isinstance(raw, dict):
        return _missing_view("layout_3d.json is not an object")

    summary = _mapping(raw.get("summary"))
    assumptions = [row for row in _list(raw.get("assumptions")) if isinstance(row, dict)]
    blocked_reasons = [item for item in _list(raw.get("blocked_reasons")) if isinstance(item, str)]
    objects = [row for row in _list(raw.get("objects")) if isinstance(row, dict)]
    return {
        "available": True,
        "artifact_name": "layout_3d.json",
        "schema_version": _str(raw.get("schema_version")),
        "model_status": _str(raw.get("model_status")),
        "source_artifact": _str(raw.get("source_artifact")),
        "source_sheet_ids": [item for item in _list(raw.get("source_sheet_ids")) if isinstance(item, str)],
        "scale_basis": _mapping(raw.get("scale_basis")),
        "summary": summary,
        "object_count": _int(summary.get("object_count")),
        "mesh_object_count": _int(summary.get("mesh_object_count")),
        "assumption_count": len(assumptions),
        "assumptions": assumptions[:8],
        "blocked_reasons": blocked_reasons,
        "object_samples": objects[:10],
        "opening_semantics": _opening_semantics(objects),
        "opening_measurements": _opening_measurements(objects),
        "opening_wall_hosts": _opening_wall_hosts(objects),
        "opening_provenance_consistency": _opening_provenance_consistency(objects),
        "glb_available": (out_dir / "layout_3d.glb").exists(),
        "summary_available": (out_dir / "layout_3d_summary.md").exists(),
        "warning_text": (
            "3D Layout Model 是 evidence/navigation 视图; 默认高度/厚度只用于可视化, "
            "不是规范判断或 BIM 真值。"
        ),
    }


def _missing_view(reason: str) -> dict[str, Any]:
    return {
        "available": False,
        "artifact_name": "layout_3d.json",
        "model_status": "missing",
        "source_artifact": "",
        "source_sheet_ids": [],
        "scale_basis": {},
        "summary": {},
        "object_count": 0,
        "mesh_object_count": 0,
        "assumption_count": 0,
        "assumptions": [],
        "blocked_reasons": [],
        "object_samples": [],
        "opening_semantics": _empty_opening_semantics(),
        "opening_measurements": _empty_opening_measurements(),
        "opening_wall_hosts": _empty_opening_wall_hosts(),
        "opening_provenance_consistency": _empty_opening_provenance_consistency(),
        "glb_available": False,
        "summary_available": False,
        "warning_text": (
            "layout_3d.json 暂无数据; 缺失 3D layout 不代表图纸无法审查, "
            "也不代表 2D evidence 已完整。"
        ),
        "unavailable_reason": reason,
    }


def _mapping(raw: object) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        return {}
    return {str(key): value for key, value in raw.items()}


def _opening_semantics(objects: list[dict[str, Any]]) -> dict[str, Any]:
    samples: list[dict[str, Any]] = []
    door_count = 0
    window_count = 0
    for obj in objects:
        object_type = _str(obj.get("object_type"))
        if object_type == "door_opening":
            door_count += 1
        elif object_type == "window_opening":
            window_count += 1
        else:
            continue
        properties = _mapping(obj.get("properties"))
        semantic = _mapping(properties.get("opening_semantic"))
        samples.append(
            {
                "object_id": _str(obj.get("object_id")),
                "object_type": object_type,
                "source_entity_id": _str(obj.get("source_entity_id")),
                "kind": _str(semantic.get("kind")),
                "explicit": bool(semantic.get("explicit")),
                "source_property": _str(semantic.get("source_property")),
                "source_value": semantic.get("source_value"),
            }
        )
    return {
        **_empty_opening_semantics(),
        "door_opening_count": door_count,
        "window_opening_count": window_count,
        "samples": samples[:8],
    }


def _empty_opening_semantics() -> dict[str, Any]:
    return {
        "door_opening_count": 0,
        "window_opening_count": 0,
        "samples": [],
        "boundary_warning": (
            "window_opening is shown only when explicit graph evidence marks the opening as a window."
        ),
    }


def _opening_measurements(objects: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {
        "width_m": 0,
        "height_m": 0,
        "sill_height_m": 0,
        "head_height_m": 0,
    }
    samples: list[dict[str, Any]] = []
    for obj in objects:
        object_type = _str(obj.get("object_type"))
        if object_type not in {"door_opening", "window_opening"}:
            continue
        properties = _mapping(obj.get("properties"))
        measurement = _mapping(properties.get("opening_measurement"))
        for field in counts:
            entry = _mapping(measurement.get(field))
            if entry.get("explicit") is not True:
                continue
            value = entry.get("value")
            if not isinstance(value, int | float) or isinstance(value, bool):
                continue
            counts[field] += 1
            samples.append(
                {
                    "object_id": _str(obj.get("object_id")),
                    "object_type": object_type,
                    "source_entity_id": _str(obj.get("source_entity_id")),
                    "field": field,
                    "value": float(value),
                    "unit": _str(entry.get("unit")),
                    "explicit": True,
                    "source_property": _str(entry.get("source_property")),
                }
            )
    return {
        **_empty_opening_measurements(),
        "explicit_width_count": counts["width_m"],
        "explicit_height_count": counts["height_m"],
        "explicit_sill_height_count": counts["sill_height_m"],
        "explicit_head_height_count": counts["head_height_m"],
        "samples": samples[:8],
    }


def _empty_opening_measurements() -> dict[str, Any]:
    return {
        "explicit_width_count": 0,
        "explicit_height_count": 0,
        "explicit_sill_height_count": 0,
        "explicit_head_height_count": 0,
        "samples": [],
        "boundary_warning": (
            "Opening measurements are shown only from explicit graph evidence fields and remain preview-only."
        ),
    }


def _opening_wall_hosts(objects: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {"host_wall": 0, "source_segment": 0}
    samples: list[dict[str, Any]] = []
    for obj in objects:
        object_type = _str(obj.get("object_type"))
        if object_type not in {"door_opening", "window_opening"}:
            continue
        properties = _mapping(obj.get("properties"))
        host = _mapping(properties.get("opening_host"))
        host_wall_id = host.get("host_wall_id")
        if not (isinstance(host_wall_id, str) and host_wall_id.strip()):
            continue
        counts["host_wall"] += 1
        source_segment = host.get("source_segment")
        if _mapping(source_segment):
            counts["source_segment"] += 1
        samples.append(
            {
                "object_id": _str(obj.get("object_id")),
                "object_type": object_type,
                "source_entity_id": _str(obj.get("source_entity_id")),
                "host_wall_id": host_wall_id,
                "source_property": _str(host.get("source_property")),
                "source_segment": source_segment if _mapping(source_segment) else None,
                "explicit": bool(host.get("explicit")),
                "source_segment_property": _str(host.get("source_segment_property")),
            }
        )
    return {
        "explicit_host_wall_count": counts["host_wall"],
        "explicit_host_segment_count": counts["source_segment"],
        "boundary_warning": (
            "Opening host-wall provenance is shown only when the graph provides explicit host wall "
            "or source-segment evidence."
        ),
        "samples": samples[:8],
    }


def _empty_opening_wall_hosts() -> dict[str, Any]:
    return {
        "explicit_host_wall_count": 0,
        "explicit_host_segment_count": 0,
        "samples": [],
        "boundary_warning": (
            "Opening host-wall provenance is shown only when explicit host wall or source-segment evidence exists."
        ),
    }


def _opening_provenance_consistency(objects: list[dict[str, Any]]) -> dict[str, Any]:
    opening_count = 0
    semantic_count = 0
    measurement_count = 0
    host_count = 0
    all_three_count = 0
    samples: list[dict[str, Any]] = []
    for obj in objects:
        object_type = _str(obj.get("object_type"))
        if object_type not in {"door_opening", "window_opening"}:
            continue
        opening_count += 1
        properties = _mapping(obj.get("properties"))
        has_semantic = bool(_str(_mapping(properties.get("opening_semantic")).get("kind")))
        has_measurement = _has_any_measurement(properties)
        has_host = bool(_str(_mapping(properties.get("opening_host")).get("host_wall_id")).strip())
        if has_semantic:
            semantic_count += 1
        if has_measurement:
            measurement_count += 1
        if has_host:
            host_count += 1
        if has_semantic and has_measurement and has_host:
            all_three_count += 1
        missing = []
        if not has_semantic:
            missing.append("semantic")
        if not has_measurement:
            missing.append("measurement")
        if not has_host:
            missing.append("host_wall")
        samples.append(
            {
                "object_id": _str(obj.get("object_id")),
                "object_type": object_type,
                "source_entity_id": _str(obj.get("source_entity_id")),
                "has_semantic": has_semantic,
                "has_measurement": has_measurement,
                "has_host": has_host,
                "missing_provenance": missing,
            }
        )
    return {
        **_empty_opening_provenance_consistency(),
        "opening_count": opening_count,
        "semantic_count": semantic_count,
        "measurement_count": measurement_count,
        "host_count": host_count,
        "all_three_count": all_three_count,
        "samples": samples[:8],
    }


def _has_any_measurement(properties: dict[str, Any]) -> bool:
    measurement = _mapping(properties.get("opening_measurement"))
    for entry_raw in measurement.values():
        entry = _mapping(entry_raw)
        if entry.get("explicit") is not True:
            continue
        value = entry.get("value")
        if isinstance(value, int | float) and not isinstance(value, bool):
            return True
    return False


def _empty_opening_provenance_consistency() -> dict[str, Any]:
    return {
        "opening_count": 0,
        "semantic_count": 0,
        "measurement_count": 0,
        "host_count": 0,
        "all_three_count": 0,
        "samples": [],
        "boundary_warning": (
            "Opening provenance consistency is a coverage view only; missing signals are review prompts, not failures."
        ),
    }


def _list(raw: object) -> list[Any]:
    return raw if isinstance(raw, list) else []


def _str(raw: object) -> str:
    return raw if isinstance(raw, str) else ""


def _int(raw: object) -> int:
    return raw if isinstance(raw, int) else 0


__all__ = ["load_layout_3d_view"]
