"""Tests for Phase 11-B project-scope rules (applies_to: Project)."""

from __future__ import annotations

from archkg.graph.builder import EntityGraph
from archkg.knowledge.loader import load_rules, load_standards
from archkg.rules.engine import evaluate
from archkg.schemas import ProjectMeta


def _empty_graph() -> EntityGraph:
    return EntityGraph(
        source_pdf="x.pdf",
        points_per_meter=50.0,
        page_index=0,
        page_width_pt=500,
        page_height_pt=400,
        rooms=[],
        doors=[],
        corridors=[],
        dimensions=[],
    )


def _residential_meta(*, floors: int | None = 6, height_m: float | None = 18.0, height_class: str = "多层") -> ProjectMeta:
    return ProjectMeta(
        project_id="P-TEST",
        building_type="residential",
        height_class=height_class,  # type: ignore[arg-type]
        floors=floors,
        height_m=height_m,
    )


def test_project_rules_skip_without_meta() -> None:
    """Without a ProjectMeta, all 3 project-scope rules are skipped with a clear reason."""
    standards = load_standards()
    rules = load_rules(standards=standards)
    result = evaluate(_empty_graph(), rules, standards, project_meta=None)
    skipped_ids = {s.rule_id for s in result.skipped}
    assert {"RC-ELEVATOR-REQUIRED", "RC-EVAC-STAIR-TYPE-33M", "RC-REFUGE-LAYER-100M"} <= skipped_ids
    project_skips = [s for s in result.skipped if s.rule_id.startswith("RC-ELEVATOR") or s.rule_id.startswith("RC-EVAC") or s.rule_id.startswith("RC-REFUGE")]
    for s in project_skips:
        assert "project-meta" in s.reason or "项目" in s.reason


def test_low_rise_residential_passes_all_project_rules() -> None:
    """6 floors / 14m residential project — below both 6.4.1 triggers and below
    the 33m / 100m fire thresholds — produces zero project-level issues."""
    standards = load_standards()
    rules = load_rules(standards=standards)
    meta = _residential_meta(floors=6, height_m=14.0)
    result = evaluate(_empty_graph(), rules, standards, project_meta=meta)
    project_issues = [i for i in result.issues if i.bbox is None]
    assert project_issues == [], f"unexpected: {[i.message for i in project_issues]}"


def test_seven_floor_residential_triggers_elevator_rule() -> None:
    standards = load_standards()
    rules = load_rules(standards=standards)
    meta = _residential_meta(floors=7, height_m=20.0)
    result = evaluate(_empty_graph(), rules, standards, project_meta=meta)
    elevator_issues = [i for i in result.issues if i.rule_card_id == "RC-ELEVATOR-REQUIRED"]
    assert len(elevator_issues) == 1
    iss = elevator_issues[0]
    assert iss.bbox is None
    assert iss.entity_ids == ["project:P-TEST"]
    assert iss.severity == "info"
    assert iss.standard_clause_id == "GB50096-6.4.1"
    assert "GB 50096-6.4.1" in iss.message


def test_height_above_16m_triggers_elevator_even_with_few_floors() -> None:
    """The 6.4.1 rule has two triggers; the 16 m one fires even when floors<7."""
    standards = load_standards()
    rules = load_rules(standards=standards)
    meta = _residential_meta(floors=5, height_m=17.5)
    result = evaluate(_empty_graph(), rules, standards, project_meta=meta)
    elevator_issues = [i for i in result.issues if i.rule_card_id == "RC-ELEVATOR-REQUIRED"]
    assert len(elevator_issues) == 1


def test_high_rise_triggers_evac_stair_rule() -> None:
    """Height > 33 m fires the 防烟楼梯间 reminder."""
    standards = load_standards()
    rules = load_rules(standards=standards)
    meta = _residential_meta(floors=12, height_m=35.0, height_class="中高层")
    result = evaluate(_empty_graph(), rules, standards, project_meta=meta)
    stair_issues = [i for i in result.issues if i.rule_card_id == "RC-EVAC-STAIR-TYPE-33M"]
    assert len(stair_issues) == 1
    assert "GB 50016-5.5.27" in stair_issues[0].message


def test_super_high_rise_triggers_refuge_layer_rule() -> None:
    """Height > 100 m fires the refuge-layer reminder.

    Note: RC-REFUGE-LAYER-100M only applies to 超高层 per its source clause's
    applies_to_height_class. 多层 / 高层 projects skip this rule before it
    even reaches the eval — so the project meta height_class must be 超高层
    for the rule to fire."""
    standards = load_standards()
    rules = load_rules(standards=standards)
    meta = _residential_meta(floors=35, height_m=120.0, height_class="超高层")
    result = evaluate(_empty_graph(), rules, standards, project_meta=meta)
    refuge_issues = [i for i in result.issues if i.rule_card_id == "RC-REFUGE-LAYER-100M"]
    assert len(refuge_issues) == 1
    assert "GB 50016-5.5.31" in refuge_issues[0].message


def test_layered_skip_refuge_layer_for_non_super_high_rise() -> None:
    """Codex P11-B nit: regression for the Phase-9-applicability + Phase-11-B
    interaction. RC-REFUGE-LAYER-100M's source clause GB50016-5.5.31 is
    超高层-only. For a 多层 residential project, the rule must land in
    result.skipped, NOT fire as an issue, even though the project-rule
    eval path would otherwise emit one for height_m > 100."""
    standards = load_standards()
    rules = load_rules(standards=standards)
    meta = _residential_meta(floors=12, height_m=120.0, height_class="多层")
    result = evaluate(_empty_graph(), rules, standards, project_meta=meta)
    refuge_in_issues = [i for i in result.issues if i.rule_card_id == "RC-REFUGE-LAYER-100M"]
    refuge_in_skipped = [s for s in result.skipped if s.rule_id == "RC-REFUGE-LAYER-100M"]
    assert refuge_in_issues == [], "Phase 9 applicability should pre-empt Phase 11-B eval"
    assert len(refuge_in_skipped) == 1
    assert "超高层" in refuge_in_skipped[0].reason


def test_unset_optional_meta_fields_no_op_gracefully() -> None:
    """Rules use `is None` checks so unset floors/height_m don't false-positive."""
    standards = load_standards()
    rules = load_rules(standards=standards)
    meta = ProjectMeta(
        project_id="P-MIN",
        building_type="residential",
        height_class="多层",
        # No floors, no height_m
    )
    result = evaluate(_empty_graph(), rules, standards, project_meta=meta)
    project_issues = [i for i in result.issues if i.bbox is None]
    assert project_issues == []
