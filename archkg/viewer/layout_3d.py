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


def _list(raw: object) -> list[Any]:
    return raw if isinstance(raw, list) else []


def _str(raw: object) -> str:
    return raw if isinstance(raw, str) else ""


def _int(raw: object) -> int:
    return raw if isinstance(raw, int) else 0


__all__ = ["load_layout_3d_view"]
