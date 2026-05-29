from __future__ import annotations

import json
from pathlib import Path
from typing import Any

KIND_LABELS = {
    "design_region": "设计区",
    "title_block": "标题栏",
    "schedule": "表格/排表",
    "legend": "图例/说明",
}


def load_sheet_region_candidate_view(out_dir: Path, *, limit: int = 8) -> dict[str, Any]:
    path = out_dir / "sheet_region_candidates.json"
    if not path.exists():
        return _missing_view("sheet_region_candidates.json missing")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return _missing_view(f"could not read sheet_region_candidates.json: {exc}")
    if not isinstance(raw, dict):
        return _missing_view("sheet_region_candidates.json is not an object")
    return build_sheet_region_candidate_view(
        raw,
        limit=limit,
        overlay_available=(path.parent / "sheet_region_candidates_overlay.png").exists(),
    )


def build_sheet_region_candidate_view(
    payload: dict[str, Any],
    *,
    limit: int = 8,
    overlay_available: bool = False,
) -> dict[str, Any]:
    pages = payload.get("pages")
    page_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    excluded_rows: list[dict[str, Any]] = []
    if isinstance(pages, list):
        for page in pages:
            if not isinstance(page, dict):
                continue
            page_index = _int(page.get("page_index"))
            candidates = _list_of_dicts(page.get("candidates"))
            excluded_texts = _list_of_dicts(page.get("excluded_texts"))
            page_rows.append(
                {
                    "page_index": page_index,
                    "candidate_count": len(candidates),
                    "excluded_text_count": len(excluded_texts),
                }
            )
            for candidate in candidates:
                candidate_rows.append(_candidate_row(page_index, candidate))
            for text in excluded_texts:
                excluded_rows.append(_excluded_row(page_index, text))

    return {
        "available": True,
        "schema_version": _string(payload.get("schema_version")) or "unknown",
        "artifact_name": "sheet_region_candidates.json",
        "overlay_available": overlay_available,
        "overlay_name": "sheet_region_candidates_overlay.png",
        "applied_region": _region_text(payload.get("applied_region")),
        "pages": page_rows,
        "candidates": candidate_rows[:limit],
        "candidate_total": len(candidate_rows),
        "excluded_texts": excluded_rows[:limit],
        "excluded_text_total": len(excluded_rows),
        "omitted_candidate_count": max(0, len(candidate_rows) - limit),
        "omitted_excluded_count": max(0, len(excluded_rows) - limit),
        "warning_text": "候选区域不自动裁剪; 只有显式传入 --sheet-region 才会改变 primitives/graph.",
        "unavailable_reason": "",
    }


def _missing_view(reason: str) -> dict[str, Any]:
    return {
        "available": False,
        "schema_version": "missing",
        "artifact_name": "sheet_region_candidates.json",
        "overlay_available": False,
        "overlay_name": "sheet_region_candidates_overlay.png",
        "applied_region": "—",
        "pages": [],
        "candidates": [],
        "candidate_total": 0,
        "excluded_texts": [],
        "excluded_text_total": 0,
        "omitted_candidate_count": 0,
        "omitted_excluded_count": 0,
        "warning_text": "候选区域暂无数据; 缺失 candidate artifact 不代表已裁剪或已确认.",
        "unavailable_reason": reason,
    }


def _candidate_row(page_index: int, candidate: dict[str, Any]) -> dict[str, Any]:
    kind = _string(candidate.get("kind")) or "unknown"
    confidence = _float(candidate.get("confidence"))
    return {
        "page_index": page_index,
        "kind": kind,
        "kind_label": KIND_LABELS.get(kind, kind),
        "region": _region_text(candidate.get("region")),
        "copy_region": _copy_region(candidate.get("region")),
        "confidence_pct": confidence * 100.0,
        "reason": _string(candidate.get("reason")) or "—",
    }


def _excluded_row(page_index: int, text: dict[str, Any]) -> dict[str, Any]:
    return {
        "page_index": page_index,
        "text": _string(text.get("text")) or "—",
        "region": _region_text(text.get("bbox")),
        "reason": _string(text.get("reason")) or "—",
    }


def _list_of_dicts(raw: object) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    return [dict(item) for item in raw if isinstance(item, dict)]


def _region_text(raw: object) -> str:
    values = _region_values(raw)
    if values is None:
        return "—"
    return ",".join(f"{value:.1f}" for value in values)


def _copy_region(raw: object) -> str:
    values = _region_values(raw)
    if values is None:
        return ""
    return ",".join(_compact_number(value) for value in values)


def _region_values(raw: object) -> tuple[float, float, float, float] | None:
    if not isinstance(raw, list | tuple) or len(raw) != 4:
        return None
    values: list[float] = []
    for item in raw:
        if not isinstance(item, int | float):
            return None
        values.append(float(item))
    return (values[0], values[1], values[2], values[3])


def _compact_number(value: float) -> str:
    if value.is_integer():
        return str(int(value))
    return f"{value:.1f}".rstrip("0").rstrip(".")


def _string(raw: object) -> str:
    return raw if isinstance(raw, str) else ""


def _int(raw: object) -> int:
    if isinstance(raw, bool):
        return int(raw)
    if isinstance(raw, int):
        return raw
    return 0


def _float(raw: object) -> float:
    if isinstance(raw, bool):
        return float(raw)
    if isinstance(raw, int | float):
        return float(raw)
    return 0.0
