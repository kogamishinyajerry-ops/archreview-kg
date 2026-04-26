from __future__ import annotations

import pytest

from archkg.graph.builder import EntityGraph
from archkg.knowledge.loader import load_rules, load_standards
from archkg.rules.engine import (
    RuleCompileError,
    compile_expression,
    evaluate,
    evaluate_expression,
)
from archkg.schemas import Corridor, Door, Room


def test_compile_rejects_function_call() -> None:
    with pytest.raises(RuleCompileError):
        compile_expression("len(min_width_m) > 1", ["min_width_m"])


def test_compile_rejects_unknown_name() -> None:
    with pytest.raises(RuleCompileError):
        compile_expression("rogue >= 1", ["min_width_m"])


def test_compile_rejects_attribute_access() -> None:
    with pytest.raises(RuleCompileError):
        compile_expression("foo.bar >= 1", ["foo"])


def test_evaluate_simple_pass_and_fail() -> None:
    tree = compile_expression("min_width_m >= 1.20", ["min_width_m"])
    assert evaluate_expression(tree, {"min_width_m": 1.5}) is True
    assert evaluate_expression(tree, {"min_width_m": 1.05}) is False


def test_evaluate_none_short_circuits_to_false() -> None:
    tree = compile_expression("min_width_m >= 1.20", ["min_width_m"])
    assert evaluate_expression(tree, {"min_width_m": None}) is False


def test_evaluate_division_by_zero_does_not_crash_demo() -> None:
    """Codex-derived regression: a rule that divides by zero must NOT take down review."""
    tree = compile_expression("a / b > 0.5", ["a", "b"])
    assert evaluate_expression(tree, {"a": 5.0, "b": 0.0}) is False


def test_evaluate_value_error_is_caught() -> None:
    tree = compile_expression("a + b", ["a", "b"])
    # mixing str + int raises TypeError, but covers the broadened except
    assert evaluate_expression(tree, {"a": "x", "b": 1}) is False


def test_evaluate_against_synthetic_graph_flags_corridor_door_bedroom() -> None:
    standards = load_standards()
    rules = load_rules(standards=standards)

    rooms = [
        Room(
            id="room-bed",
            page_index=0,
            bbox=(0, 0, 200, 200),
            polygon=[(0, 0), (200, 0), (200, 200), (0, 200)],
            label="bedroom",
            area_m2=4.0,  # FAIL: < 5
        ),
        Room(
            id="room-living",
            page_index=0,
            bbox=(200, 0, 500, 200),
            polygon=[(200, 0), (500, 0), (500, 200), (200, 200)],
            label="living",
            area_m2=15.0,  # not a bedroom -> rule should not fire
        ),
    ]
    doors = [
        Door(
            id="door-narrow",
            page_index=0,
            bbox=(95, 195, 145, 205),
            width_m=0.85,  # FAIL: < 0.90
        ),
        Door(
            id="door-ok",
            page_index=0,
            bbox=(395, 195, 445, 205),
            width_m=0.95,  # pass
        ),
    ]
    corridors = [
        Corridor(
            id="corridor-1",
            page_index=0,
            bbox=(0, 200, 500, 252),
            polygon=[(0, 200), (500, 200), (500, 252), (0, 252)],
            min_width_m=1.05,  # FAIL: < 1.20
        )
    ]

    graph = EntityGraph(
        source_pdf="x.pdf",
        points_per_meter=50.0,
        page_index=0,
        page_width_pt=500,
        page_height_pt=400,
        rooms=rooms,
        doors=doors,
        corridors=corridors,
        dimensions=[],
    )

    result = evaluate(graph, rules, standards)
    issues = result.issues
    # No project_meta means entity-level rules all run; project-level rules skip
    # for lack of context (Phase 11-B addition).
    skipped_ids = {s.rule_id for s in result.skipped}
    # All project-scope rules skip without --project-meta context.
    project_rule_ids = {
        "RC-ELEVATOR-REQUIRED", "RC-EVAC-STAIR-TYPE-33M", "RC-REFUGE-LAYER-100M",
        "RC-CLOSED-STAIRWELL-21M", "RC-ACCESSIBLE-RESIDENTIAL-7F",
        "RC-ENTRANCE-PLATFORM-WIDTH-7F",
        # Phase 11-C Path B: Codex-drafted, human-validated.
        "RC-ELEVATOR-BEDROOM-ADJACENCY", "RC-WHEELCHAIR-PASSAGE-WIDTH-7F",
        "RC-DOOR-TO-EXIT-40M",
    }
    assert skipped_ids == project_rule_ids
    rule_ids = sorted(i.rule_card_id for i in issues)
    assert rule_ids == sorted(["RC-CORRIDOR-WIDTH", "RC-DOOR-WIDTH", "RC-BEDROOM-AREA"])

    by_rule = {i.rule_card_id: i for i in issues}
    assert by_rule["RC-CORRIDOR-WIDTH"].evidence.measured_value == pytest.approx(1.05)
    assert by_rule["RC-CORRIDOR-WIDTH"].evidence.threshold_value == pytest.approx(1.20)
    assert by_rule["RC-DOOR-WIDTH"].evidence.measured_value == pytest.approx(0.85)
    assert by_rule["RC-BEDROOM-AREA"].entity_ids == ["room-bed"]
    assert by_rule["RC-BEDROOM-AREA"].evidence.measured_value == pytest.approx(4.0)


def test_evaluate_skips_all_rules_for_industrial_project() -> None:
    """End-to-end Phase 9 check: an industrial project_meta should turn every
    residential-tagged rule into a SkippedRule, with zero issues fired."""
    from archkg.knowledge.loader import load_rules, load_standards
    from archkg.schemas import ProjectMeta

    standards = load_standards()
    rules = load_rules(standards=standards)
    meta = ProjectMeta(project_id="P-IND", building_type="industrial", height_class="多层")
    # Empty graph is fine — we only care that *no rule fires* and *all rules are skipped*.
    graph = EntityGraph(
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
    result = evaluate(graph, rules, standards, project_meta=meta)
    assert result.issues == []
    assert {s.rule_id for s in result.skipped} == {r.id for r in rules}
    for s in result.skipped:
        assert "工业建筑" in s.reason


def test_rule_test_cases_match_engine_decision() -> None:
    """Each rule's declared test_cases must agree with the live engine evaluation."""
    standards = load_standards()
    rules = load_rules(standards=standards)
    for rule in rules:
        tree = compile_expression(rule.logic_expression, rule.inputs)
        for tc in rule.test_cases:
            env = {k: tc.entity.get(k) for k in rule.inputs}
            actual = evaluate_expression(tree, env)
            assert actual is tc.expect_pass, (
                f"rule {rule.id} test '{tc.name}': expected {tc.expect_pass}, got {actual}"
            )
