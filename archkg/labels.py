"""Reviewer-facing zh-CN labels for schema literals.

Keep schema/storage values in stable Latin tokens (residential, geometric, ...)
so logic / search / yaml diff stay readable, but render them in proper zh-CN
when they hit a reviewer's eyes (report, terminal summary, skip reasons).
"""

from __future__ import annotations

from collections.abc import Iterable

from archkg.schemas.standard import BuildingType, ClauseCategory

BUILDING_TYPE_LABEL: dict[BuildingType, str] = {
    "residential": "居住建筑",
    "public": "公共建筑",
    "industrial": "工业建筑",
}

CATEGORY_LABEL: dict[ClauseCategory, str] = {
    "geometric": "几何",
    "topological": "拓扑",
    "fire": "防火",
    "accessibility": "无障碍",
    "energy": "节能",
    "acoustic": "声学",
    "general": "通用",
}


def label_building_type(value: BuildingType) -> str:
    """Return the zh-CN reviewer label for a building-type token."""
    return BUILDING_TYPE_LABEL[value]


def label_building_types(values: Iterable[BuildingType]) -> str:
    """Slash-join multiple building-type tokens as zh-CN labels."""
    return "/".join(label_building_type(v) for v in values)


def label_category(value: ClauseCategory) -> str:
    """Return the zh-CN reviewer label for a clause category."""
    return CATEGORY_LABEL[value]
