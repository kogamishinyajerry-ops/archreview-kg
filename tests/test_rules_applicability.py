from __future__ import annotations

from archkg.knowledge.loader import load_rules, load_standards
from archkg.rules.applicability import (
    is_clause_applicable,
    is_rule_applicable,
    skip_reason,
)
from archkg.schemas import ProjectMeta


def _residential_meta() -> ProjectMeta:
    return ProjectMeta(
        project_id="P-RES",
        building_type="residential",
        height_class="多层",
    )


def _industrial_meta() -> ProjectMeta:
    return ProjectMeta(
        project_id="P-IND",
        building_type="industrial",
        height_class="多层",
    )


def _di_ceng_meta() -> ProjectMeta:
    """Height class 低层 — excludes the 多层/高层-only elevator clause."""
    return ProjectMeta(
        project_id="P-LOW",
        building_type="residential",
        height_class="低层",
    )


def test_clause_applicable_when_meta_is_none() -> None:
    standards = load_standards()
    for c in standards:
        assert is_clause_applicable(c, None) is True


def test_clause_skipped_when_building_type_mismatches() -> None:
    standards = load_standards()
    by_id = {c.id: c for c in standards}
    industrial = _industrial_meta()
    # Every residential-only clause should NOT apply to an industrial project
    residential_only = [c for c in standards if list(c.applies_to_building_type) == ["residential"]]
    assert residential_only, "fixture sanity"
    for c in residential_only:
        assert is_clause_applicable(c, industrial) is False
    # The shared residential+public clause GB50016-5.5.30 still does NOT apply to industrial
    assert is_clause_applicable(by_id["GB50016-5.5.30"], industrial) is False


def test_clause_skipped_when_height_class_mismatches() -> None:
    standards = load_standards()
    by_id = {c.id: c for c in standards}
    elevator = by_id["GB50096-6.4.1"]
    # 低层 is excluded from the elevator clause's applies_to_height_class
    assert is_clause_applicable(elevator, _di_ceng_meta()) is False
    # 多层 is included
    assert is_clause_applicable(elevator, _residential_meta()) is True


def test_rule_applicable_when_meta_is_none() -> None:
    standards = load_standards()
    rules = load_rules(standards=standards)
    by_id = {c.id: c for c in standards}
    for r in rules:
        assert is_rule_applicable(r, None, by_id) is True


def test_all_rules_skipped_for_industrial_project() -> None:
    """Phase 8 ships only residential-tagged clauses, so an industrial
    project should skip every existing rule. Demonstrates the filter end-to-end."""
    standards = load_standards()
    rules = load_rules(standards=standards)
    by_id = {c.id: c for c in standards}
    meta = _industrial_meta()
    skipped = [r for r in rules if not is_rule_applicable(r, meta, by_id)]
    assert {r.id for r in skipped} == {r.id for r in rules}


def test_residential_project_applies_all_existing_rules() -> None:
    standards = load_standards()
    rules = load_rules(standards=standards)
    by_id = {c.id: c for c in standards}
    meta = _residential_meta()
    for r in rules:
        assert is_rule_applicable(r, meta, by_id) is True


def test_skip_reason_uses_zh_cn_labels() -> None:
    """Codex P9 nit: skip_reason should render zh-CN labels, not raw enum tokens."""
    standards = load_standards()
    rules = load_rules(standards=standards)
    by_id = {c.id: c for c in standards}
    rule = next(r for r in rules if r.id == "RC-CORRIDOR-WIDTH")
    reason = skip_reason(rule, _industrial_meta(), by_id)
    assert "GB50096-5.7.2" in reason
    assert "居住建筑" in reason, f"expected zh-CN label, got: {reason}"
    assert "工业建筑" in reason, f"expected zh-CN label, got: {reason}"
    # Schema literals should NOT leak through to the reviewer-facing string
    assert "residential" not in reason
    assert "industrial" not in reason
