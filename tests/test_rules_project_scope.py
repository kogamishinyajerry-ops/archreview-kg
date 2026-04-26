"""Tests for Phase 11-B project-scope rules (applies_to: Project)."""

from __future__ import annotations

import pytest

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


def test_low_rise_residential_passes_threshold_gated_project_rules() -> None:
    """6 floors / 14m residential — below the 6.4.1 / 33m / 100m thresholds.

    Threshold-gated rules (elevator, evac-stair, refuge, accessibility-7F)
    must NOT fire. Phase 13 full adds reminder cards that gate purely on
    building_type and always fire for residential — those are excluded
    from this regression because they are by-design reminders, not
    threshold checks.
    """
    standards = load_standards()
    rules = load_rules(standards=standards)
    meta = _residential_meta(floors=6, height_m=14.0)
    result = evaluate(_empty_graph(), rules, standards, project_meta=meta)
    threshold_gated_ids = {
        "RC-ELEVATOR-REQUIRED", "RC-EVAC-STAIR-TYPE-33M", "RC-CLOSED-STAIRWELL-21M",
        "RC-REFUGE-LAYER-100M", "RC-ACCESSIBLE-RESIDENTIAL-7F",
        "RC-ENTRANCE-PLATFORM-WIDTH-7F", "RC-ELEVATOR-BEDROOM-ADJACENCY",
        "RC-WHEELCHAIR-PASSAGE-WIDTH-7F", "RC-DOOR-TO-EXIT-40M-LOW-MULTI-AB",
    }
    threshold_fires = [
        i for i in result.issues if i.rule_card_id in threshold_gated_ids
    ]
    assert threshold_fires == [], (
        f"threshold-gated rules false-fired on low-rise residential: "
        f"{[i.rule_card_id for i in threshold_fires]}"
    )


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


@pytest.mark.parametrize(
    ("height_m", "expected_fires"),
    [
        # Boundaries Codex flagged in the P11-C nit. evaluate() against a 多层
        # residential meta — applicability filter only excludes the 超高层-only
        # refuge-layer rule.
        (20.9, set()),  # below 21 — open stair allowed, no project-level fires
        (21.0, set()),  # exactly 21 — clause says "不大于 21" allows open stair
        (21.1, {"RC-CLOSED-STAIRWELL-21M"}),  # just above 21 — closed required
        (33.0, {"RC-CLOSED-STAIRWELL-21M"}),  # exactly 33 — still in the closed band
        (33.1, {"RC-EVAC-STAIR-TYPE-33M"}),  # just above 33 — smoke-proof required
    ],
)
def test_stairwell_band_boundaries(height_m: float, expected_fires: set[str]) -> None:
    """Codex P11-C nit: explicit ±1 boundary regression around 21.0 / 33.0 m."""
    standards = load_standards()
    rules = load_rules(standards=standards)
    # Use a residential meta tall enough for the elevator + accessibility rules
    # to fire too — we filter those out below so the band test stays focused.
    meta = ProjectMeta(
        project_id="P-BOUND",
        building_type="residential",
        height_class="多层" if height_m <= 33 else "高层",
        floors=8,
        height_m=height_m,
    )
    result = evaluate(_empty_graph(), rules, standards, project_meta=meta)
    stair_fires = {
        i.rule_card_id for i in result.issues
        if i.rule_card_id in {"RC-CLOSED-STAIRWELL-21M", "RC-EVAC-STAIR-TYPE-33M"}
    }
    assert stair_fires == expected_fires, (
        f"height_m={height_m}: expected stair fires {expected_fires}, got {stair_fires}"
    )


def test_unset_optional_meta_fields_no_op_gracefully() -> None:
    """Rules that gate on floors/height_m must use `is None` checks so unset
    optional fields don't false-positive. Reminder cards that gate on
    building_type fire by design and are out of scope for this regression."""
    standards = load_standards()
    rules = load_rules(standards=standards)
    meta = ProjectMeta(
        project_id="P-MIN",
        building_type="residential",
        height_class="多层",
        # No floors, no height_m
    )
    result = evaluate(_empty_graph(), rules, standards, project_meta=meta)
    threshold_gated_ids = {
        "RC-ELEVATOR-REQUIRED", "RC-EVAC-STAIR-TYPE-33M", "RC-CLOSED-STAIRWELL-21M",
        "RC-REFUGE-LAYER-100M", "RC-ACCESSIBLE-RESIDENTIAL-7F",
        "RC-ENTRANCE-PLATFORM-WIDTH-7F", "RC-ELEVATOR-BEDROOM-ADJACENCY",
        "RC-WHEELCHAIR-PASSAGE-WIDTH-7F", "RC-DOOR-TO-EXIT-40M-LOW-MULTI-AB",
    }
    threshold_fires = [
        i for i in result.issues if i.rule_card_id in threshold_gated_ids
    ]
    assert threshold_fires == [], (
        f"threshold-gated rules false-fired on unset optional meta: "
        f"{[i.rule_card_id for i in threshold_fires]}"
    )
