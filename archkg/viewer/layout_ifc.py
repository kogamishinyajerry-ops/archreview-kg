"""Viewer adapter for optional layout IFC export artifacts."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any


def load_layout_ifc_view(out_dir: Path) -> dict[str, Any]:
    report_path = out_dir / "layout_ifc_export.json"
    if not report_path.exists():
        return _missing_view("layout_ifc_export.json missing", out_dir)
    try:
        raw = json.loads(report_path.read_text("utf-8"))
    except Exception as exc:
        return _missing_view(f"could not read layout_ifc_export.json: {exc}", out_dir)
    if not isinstance(raw, dict):
        return _missing_view("layout_ifc_export.json is not an object", out_dir)

    exported_counts = _int_mapping(raw.get("exported_counts"))
    skipped_counts = _int_mapping(raw.get("skipped_counts"))
    warnings = [item for item in _list(raw.get("warnings")) if isinstance(item, str)]
    return {
        "available": True,
        "artifact_name": "layout_ifc_export.json",
        "schema_version": _str(raw.get("schema_version")),
        "status": _str(raw.get("status")),
        "source_layout_path": _str(raw.get("source_layout_path")),
        "source_schema_version": _str(raw.get("source_schema_version")),
        "output_ifc_path": _str(raw.get("output_ifc_path")),
        "object_count": _int(raw.get("object_count")),
        "exported_counts": exported_counts,
        "skipped_counts": skipped_counts,
        "exported_total": sum(exported_counts.values()),
        "skipped_total": sum(skipped_counts.values()),
        "assumptions_count": _int(raw.get("assumptions_count")),
        "warnings": warnings,
        "boundary_warning": _str(raw.get("boundary_warning")),
        "ifc_available": (out_dir / "layout.ifc").exists(),
        "markdown_available": (out_dir / "layout_ifc_export.md").exists(),
        "warning_text": (
            "IFC preview is optional evidence derived from layout_3d.json; "
            "it is not a review-grade BIM model or compliance conclusion."
        ),
    }


def _missing_view(reason: str, out_dir: Path) -> dict[str, Any]:
    return {
        "available": False,
        "artifact_name": "layout_ifc_export.json",
        "schema_version": "",
        "status": "not_exported",
        "source_layout_path": "",
        "source_schema_version": "",
        "output_ifc_path": "",
        "object_count": 0,
        "exported_counts": {},
        "skipped_counts": {},
        "exported_total": 0,
        "skipped_total": 0,
        "assumptions_count": 0,
        "warnings": [],
        "boundary_warning": (
            "IFC preview is optional evidence derived from layout_3d.json; "
            "it is not a review-grade BIM model or compliance conclusion."
        ),
        "ifc_available": (out_dir / "layout.ifc").exists(),
        "markdown_available": (out_dir / "layout_ifc_export.md").exists(),
        "warning_text": (
            "layout.ifc has not been exported. This is an optional preview lane, "
            "not a review blocker."
        ),
        "unavailable_reason": reason,
    }


def _int_mapping(raw: object) -> dict[str, int]:
    if not isinstance(raw, Mapping):
        return {}
    out: dict[str, int] = {}
    for key, value in raw.items():
        if isinstance(value, int):
            out[str(key)] = value
    return out


def _list(raw: object) -> list[Any]:
    return raw if isinstance(raw, list) else []


def _str(raw: object) -> str:
    return raw if isinstance(raw, str) else ""


def _int(raw: object) -> int:
    return raw if isinstance(raw, int) else 0


__all__ = ["load_layout_ifc_view"]
