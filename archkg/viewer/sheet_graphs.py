from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_sheet_graphs_view(out_dir: Path, *, limit: int = 8) -> dict[str, Any]:
    path = out_dir / "sheet_graphs.json"
    if not path.exists():
        return _missing_view("sheet_graphs.json missing")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return _missing_view(f"could not read sheet_graphs.json: {exc}")
    if not isinstance(raw, dict):
        return _missing_view("sheet_graphs.json is not an object")
    return build_sheet_graphs_view(raw, limit=limit)


def build_sheet_graphs_view(payload: dict[str, Any], *, limit: int = 8) -> dict[str, Any]:
    graphs = _list_of_dicts(payload.get("graphs"))
    skipped = _list_of_dicts(payload.get("skipped_pages"))
    graph_rows = [_graph_row(row) for row in graphs]
    skipped_rows = [_skipped_row(row) for row in skipped]
    return {
        "available": True,
        "schema_version": _string(payload.get("schema_version")) or "unknown",
        "artifact_name": "sheet_graphs.json",
        "graph_count": _int(payload.get("graph_count")),
        "confidence_floor_pct": _float(payload.get("confidence_floor")) * 100.0,
        "graphs": graph_rows[:limit],
        "skipped_pages": skipped_rows[:limit],
        "omitted_graph_count": max(0, len(graph_rows) - limit),
        "omitted_skipped_count": max(0, len(skipped_rows) - limit),
        "warning_text": (
            "Sheet graphs are per-plan evidence outputs; P39-01 does not aggregate "
            "multi-plan compliance issues into the primary rule-engine result."
        ),
        "unavailable_reason": "",
    }


def _missing_view(reason: str) -> dict[str, Any]:
    return {
        "available": False,
        "schema_version": "missing",
        "artifact_name": "sheet_graphs.json",
        "graph_count": 0,
        "confidence_floor_pct": 0.0,
        "graphs": [],
        "skipped_pages": [],
        "omitted_graph_count": 0,
        "omitted_skipped_count": 0,
        "warning_text": "sheet_graphs.json 暂无数据; 缺失多页 graph 不代表没有其他 plan sheet.",
        "unavailable_reason": reason,
    }


def _graph_row(row: dict[str, Any]) -> dict[str, Any]:
    graph = row.get("graph") if isinstance(row.get("graph"), dict) else {}
    counts = row.get("component_counts") if isinstance(row.get("component_counts"), dict) else {}
    return {
        "page_index": _int(row.get("page_index")),
        "confidence_pct": _float(row.get("classification_confidence")) * 100.0,
        "rooms": _int(counts.get("rooms")) if isinstance(counts, dict) else 0,
        "doors": _int(counts.get("doors")) if isinstance(counts, dict) else 0,
        "corridors": _int(counts.get("corridors")) if isinstance(counts, dict) else 0,
        "stairs": _int(counts.get("stairs")) if isinstance(counts, dict) else 0,
        "dimensions": _int(counts.get("dimensions")) if isinstance(counts, dict) else 0,
        "graph_page_index": _int(graph.get("page_index")) if isinstance(graph, dict) else 0,
    }


def _skipped_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "page_index": _int(row.get("page_index")),
        "sheet_type": _string(row.get("sheet_type")) or "unknown",
        "confidence_pct": _float(row.get("confidence")) * 100.0,
        "reason": _string(row.get("reason")) or "—",
    }


def _list_of_dicts(raw: object) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    return [dict(item) for item in raw if isinstance(item, dict)]


def _string(raw: object) -> str:
    return raw if isinstance(raw, str) else ""


def _int(raw: object) -> int:
    if isinstance(raw, bool):
        return int(raw)
    if isinstance(raw, int):
        return raw
    if isinstance(raw, float):
        return int(raw)
    return 0


def _float(raw: object) -> float:
    if isinstance(raw, int | float):
        return float(raw)
    return 0.0
