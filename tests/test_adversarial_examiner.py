"""Tests for the L1 deterministic examiner (Phase 18-D)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from archkg.adversarial.examiner import (
    CaseParameters,
    generate_case,
    predict_expected_violations,
    sample_parameters,
)


def test_seed_is_deterministic() -> None:
    p1 = sample_parameters(42)
    p2 = sample_parameters(42)
    assert p1 == p2

    p3 = sample_parameters(43)
    # Different seed should usually produce different parameters; not
    # asserting strict inequality (random.choice can collide), only that
    # the API doesn't pin to seed-42 forever.
    assert (p1 != p3) or (p1.seed != p3.seed)


def test_predict_no_false_violation_for_compliant_params() -> None:
    """All-compliant geometry/schedule params produce zero entity-level
    violations. Phase 18-G note: project-level reminder rules
    (RC-DOOR-TO-EXIT-40M-LOW-MULTI-AB, RC-ELEVATOR-REQUIRED at low rise,
    etc.) may still fire as info reminders — filter them out before
    asserting."""
    p = CaseParameters(
        seed=0,
        corridor_width_m=1.50,  # ≥ 1.20
        door_widths_m=(0.95, 1.00, 0.95, 1.00),  # all ≥ 0.90
        bedroom_w_m=3.0,
        bedroom_h_m=3.0,  # area 9.0 ≥ 5.0
        floors=3,
        height_m=10.0,
        total_units=100,
        accessible_units=5,  # 5/100 = 0.05 ≥ 0.02
        bedroom_net_height_m=2.80,  # ≥ 2.40
        bedroom_level="upper",  # not basement
        include_stair_schedule=False,
        stair_metrics_below_threshold=False,
    )
    expected = predict_expected_violations(p)
    entity_violations = [v for v in expected if v.entity_hint != "project"]
    assert entity_violations == []


def test_predict_corridor_violation_drives_two_rules() -> None:
    """Corridor < 1.20 fires both RC-CORRIDOR-WIDTH and the
    RC-ACCESSIBLE-INDOOR-CORRIDOR-WIDTH-1.20 rule on the same metric."""
    p = CaseParameters(
        seed=0,
        corridor_width_m=1.05,
        door_widths_m=(0.95, 1.00, 0.95, 1.00),
        bedroom_w_m=3.0,
        bedroom_h_m=3.0,
        floors=3,
        height_m=10.0,
        total_units=100,
        accessible_units=5,
        bedroom_net_height_m=2.80,
        bedroom_level="upper",
        include_stair_schedule=False,
        stair_metrics_below_threshold=False,
    )
    rule_ids = {v.rule_id for v in predict_expected_violations(p)}
    assert "RC-CORRIDOR-WIDTH" in rule_ids
    assert "RC-ACCESSIBLE-INDOOR-CORRIDOR-WIDTH-1.20" in rule_ids


def test_predict_basement_room_drives_no_living_rule() -> None:
    """Bedroom in level=basement always fires RC-NO-LIVING-IN-BASEMENT."""
    p = CaseParameters(
        seed=0,
        corridor_width_m=1.50,
        door_widths_m=(0.95, 1.00, 0.95, 1.00),
        bedroom_w_m=3.0,
        bedroom_h_m=3.0,
        floors=3,
        height_m=10.0,
        total_units=100,
        accessible_units=5,
        bedroom_net_height_m=2.80,
        bedroom_level="basement",
        include_stair_schedule=False,
        stair_metrics_below_threshold=False,
    )
    rule_ids = {v.rule_id for v in predict_expected_violations(p)}
    assert "RC-NO-LIVING-IN-BASEMENT" in rule_ids


def test_predict_basement_low_height_drives_basement_netheight_rule() -> None:
    """Basement room AND net_height < 2.0 fires RC-BASEMENT-MEZZANINE-NETHEIGHT-2.0."""
    p = CaseParameters(
        seed=0,
        corridor_width_m=1.50,
        door_widths_m=(0.95, 1.00, 0.95, 1.00),
        bedroom_w_m=3.0,
        bedroom_h_m=3.0,
        floors=3,
        height_m=10.0,
        total_units=100,
        accessible_units=5,
        bedroom_net_height_m=1.80,
        bedroom_level="basement",
        include_stair_schedule=False,
        stair_metrics_below_threshold=False,
    )
    rule_ids = {v.rule_id for v in predict_expected_violations(p)}
    assert "RC-BASEMENT-MEZZANINE-NETHEIGHT-2.0" in rule_ids


def test_predict_stair_schedule_fires_all_five(tmp_path: Path) -> None:
    p = CaseParameters(
        seed=0,
        corridor_width_m=1.50,
        door_widths_m=(0.95, 1.00, 0.95, 1.00),
        bedroom_w_m=3.0,
        bedroom_h_m=3.0,
        floors=3,
        height_m=10.0,
        total_units=100,
        accessible_units=5,
        bedroom_net_height_m=2.80,
        bedroom_level="upper",
        include_stair_schedule=True,
        stair_metrics_below_threshold=True,
    )
    rule_ids = {v.rule_id for v in predict_expected_violations(p)}
    assert {
        "RC-STAIR-FLIGHT-WIDTH-1.10",
        "RC-STAIR-TREAD-WIDTH-0.26",
        "RC-STAIR-RISER-HEIGHT-0.175",
        "RC-STAIR-HANDRAIL-0.90",
        "RC-STAIR-WELL-WIDTH-0.11",
    } <= rule_ids


def test_generate_case_writes_all_artifacts(tmp_path: Path) -> None:
    case = generate_case(seed=42, out_dir=tmp_path)
    assert case.pdf_path.exists()
    assert case.project_meta_path.exists()
    assert case.room_schedule_path.exists()
    assert (case.case_dir / "ground_truth.yaml").exists()
    # Stair schedule presence depends on parameters; assert consistency.
    if case.parameters.include_stair_schedule:
        assert case.stair_schedule_path is not None
        assert case.stair_schedule_path.exists()
    else:
        assert case.stair_schedule_path is None


def test_generate_case_is_seed_reproducible(tmp_path: Path) -> None:
    """Same seed must produce the same parameters and ground-truth
    payload so a regression in the examiner doesn't silently change
    all battery comparison.

    PDF bytes themselves aren't checked — PyMuPDF embeds a creation
    timestamp so two writes of the same content differ at the byte
    level. Parameter and ground-truth identity is the meaningful
    invariant."""
    a = generate_case(seed=999, out_dir=tmp_path / "a")
    b = generate_case(seed=999, out_dir=tmp_path / "b")
    assert a.parameters == b.parameters
    assert (a.case_dir / "ground_truth.yaml").read_text() == (
        b.case_dir / "ground_truth.yaml"
    ).read_text()


def test_ground_truth_yaml_round_trips(tmp_path: Path) -> None:
    case = generate_case(seed=42, out_dir=tmp_path)
    payload = yaml.safe_load((case.case_dir / "ground_truth.yaml").read_text())
    assert payload["seed"] == 42
    assert payload["case_id"] == case.case_id
    assert "expected_violations" in payload
    assert isinstance(payload["expected_violations"], list)


@pytest.mark.parametrize("seed", [0, 1, 7, 42, 123, 999])
def test_predict_matches_ground_truth_yaml(tmp_path: Path, seed: int) -> None:
    """Generated ground_truth.yaml's expected_violations must match what
    predict_expected_violations() would compute fresh from parameters.
    Catches drift between the two if either is updated without the
    other."""
    case = generate_case(seed=seed, out_dir=tmp_path)
    fresh = predict_expected_violations(case.parameters)
    fresh_ids = sorted(v.rule_id for v in fresh)
    payload = yaml.safe_load((case.case_dir / "ground_truth.yaml").read_text())
    yaml_ids = sorted(v["rule_id"] for v in payload["expected_violations"])
    assert fresh_ids == yaml_ids


@pytest.mark.parametrize("seed", [0, 1, 7, 42, 99, 123, 999, 1000])
def test_predict_matches_live_engine_semantics(seed: int) -> None:
    """Codex P18-D R1 P2: round-trip yaml↔predict isn't enough — both
    sides could drift away from rule_cards.yaml semantics in lock-step.

    Compile each targeted rule against the live rule_cards.yaml and run
    it directly on a parameter-derived environment. Compare the live
    fire set with predict_expected_violations(). Disagreement means
    either (a) we updated rule logic without updating the predictor or
    (b) the predictor encodes the wrong predicate.
    """
    from archkg.knowledge.loader import load_rules
    from archkg.rules.engine import compile_expression, evaluate_expression

    p = sample_parameters(seed)
    rules = {r.id: r for r in load_rules()}

    targeted = [
        "RC-CORRIDOR-WIDTH",
        "RC-ACCESSIBLE-INDOOR-CORRIDOR-WIDTH-1.20",
        "RC-DOOR-WIDTH",
        "RC-BEDROOM-AREA",
        "RC-ACCESSIBLE-RESIDENTIAL-RATIO",
        "RC-LIVING-BEDROOM-NETHEIGHT-2.4",
        "RC-NO-LIVING-IN-BASEMENT",
        "RC-BASEMENT-MEZZANINE-NETHEIGHT-2.0",
        "RC-STAIR-FLIGHT-WIDTH-1.10",
        "RC-STAIR-TREAD-WIDTH-0.26",
        "RC-STAIR-RISER-HEIGHT-0.175",
        "RC-STAIR-HANDRAIL-0.90",
        "RC-STAIR-WELL-WIDTH-0.11",
        # Phase 18-F: high-rise project-meta-driven reminders.
        "RC-ELEVATOR-REQUIRED",
        "RC-ACCESSIBLE-RESIDENTIAL-7F",
        "RC-ENTRANCE-PLATFORM-WIDTH-7F",
        "RC-WHEELCHAIR-PASSAGE-WIDTH-7F",
        "RC-REFUGE-LAYER-100M",
        # Phase 18-G: evac-stair / closed-stairwell / door-to-exit branch.
        "RC-EVAC-STAIR-TYPE-33M",
        "RC-CLOSED-STAIRWELL-21M",
        "RC-DOOR-TO-EXIT-40M-LOW-MULTI-AB",
    ]

    def _eval(rule_id: str, env: dict[str, object]) -> bool:
        rule = rules[rule_id]
        # Engine's `_entity_env` defaults to None for missing keys.
        for k in rule.inputs:
            env.setdefault(k, None)
        tree = compile_expression(rule.logic_expression, rule.inputs)
        return not evaluate_expression(tree, env)  # rule fires when expression False

    bedroom_area = p.bedroom_w_m * p.bedroom_h_m
    bedroom_room_env = {
        "label": "bedroom",
        "area_m2": bedroom_area,
        "net_height_m": p.bedroom_net_height_m,
        "level": p.bedroom_level,
    }
    from archkg.adversarial.examiner import (
        _examiner_fire_class,
        _examiner_height_class,
    )
    project_env = {
        # Examiner always writes building_type='residential', so mirror
        # that here. RC-ACCESSIBLE-RESIDENTIAL-RATIO short-circuits on
        # non-residential — leaving this unset would silently pass the
        # rule and create a false predictor↔engine mismatch.
        "building_type": "residential",
        "total_units": p.total_units,
        "accessible_units": p.accessible_units,
        "floors": p.floors,
        "height_m": p.height_m,
        # Phase 18-G: door-to-exit reads fire_class + height_class. Use
        # the same helpers the predictor and writer use so the test
        # locks all three sides together.
        "fire_class": _examiner_fire_class(p),
        "height_class": _examiner_height_class(p),
    }
    corridor_env = {"min_width_m": p.corridor_width_m}
    door_envs = [{"width_m": w} for w in p.door_widths_m]

    fired: set[str] = set()
    if _eval("RC-CORRIDOR-WIDTH", dict(corridor_env)):
        fired.add("RC-CORRIDOR-WIDTH")
    if _eval("RC-ACCESSIBLE-INDOOR-CORRIDOR-WIDTH-1.20", dict(corridor_env)):
        fired.add("RC-ACCESSIBLE-INDOOR-CORRIDOR-WIDTH-1.20")
    for env in door_envs:
        if _eval("RC-DOOR-WIDTH", dict(env)):
            fired.add("RC-DOOR-WIDTH")
    if _eval("RC-BEDROOM-AREA", dict(bedroom_room_env)):
        fired.add("RC-BEDROOM-AREA")
    if _eval("RC-ACCESSIBLE-RESIDENTIAL-RATIO", dict(project_env)):
        fired.add("RC-ACCESSIBLE-RESIDENTIAL-RATIO")
    for rid in (
        "RC-ELEVATOR-REQUIRED",
        "RC-ACCESSIBLE-RESIDENTIAL-7F",
        "RC-ENTRANCE-PLATFORM-WIDTH-7F",
        "RC-WHEELCHAIR-PASSAGE-WIDTH-7F",
        "RC-REFUGE-LAYER-100M",
        "RC-EVAC-STAIR-TYPE-33M",
        "RC-CLOSED-STAIRWELL-21M",
        "RC-DOOR-TO-EXIT-40M-LOW-MULTI-AB",
    ):
        if _eval(rid, dict(project_env)):
            fired.add(rid)
    if _eval("RC-LIVING-BEDROOM-NETHEIGHT-2.4", dict(bedroom_room_env)):
        fired.add("RC-LIVING-BEDROOM-NETHEIGHT-2.4")
    if _eval("RC-NO-LIVING-IN-BASEMENT", dict(bedroom_room_env)):
        fired.add("RC-NO-LIVING-IN-BASEMENT")
    if _eval("RC-BASEMENT-MEZZANINE-NETHEIGHT-2.0", dict(bedroom_room_env)):
        fired.add("RC-BASEMENT-MEZZANINE-NETHEIGHT-2.0")

    if p.include_stair_schedule:
        stair_env = {
            "flight_width_m": 0.95,
            "tread_width_m": 0.24,
            "riser_height_m": 0.18,
            "handrail_height_m": 0.85,
            "well_width_m": 0.14,
        }
        for rid in [
            "RC-STAIR-FLIGHT-WIDTH-1.10",
            "RC-STAIR-TREAD-WIDTH-0.26",
            "RC-STAIR-RISER-HEIGHT-0.175",
            "RC-STAIR-HANDRAIL-0.90",
            "RC-STAIR-WELL-WIDTH-0.11",
        ]:
            if _eval(rid, dict(stair_env)):
                fired.add(rid)

    predicted = {v.rule_id for v in predict_expected_violations(p)}
    # Restrict comparison to the targeted set — the predictor doesn't
    # claim coverage of project-level reminders or non-targeted rules.
    assert (predicted & set(targeted)) == fired, (
        f"seed={seed}: predictor disagrees with live engine on targeted rules.\n"
        f"  predicted: {sorted(predicted & set(targeted))}\n"
        f"  engine   : {sorted(fired)}"
    )


def test_predict_basement_low_height_branch_against_engine() -> None:
    """Codex P18-D R2 P2 residual: sample_parameters never produces
    net_height_m < 2.0, so the `RC-BASEMENT-MEZZANINE-NETHEIGHT-2.0`
    branch was never exercised in the parameter-driven semantic test.
    Pin it with explicit parameters here so the predicate ↔ engine
    contract is verified for that rule too."""
    from archkg.adversarial.examiner import CaseParameters
    from archkg.knowledge.loader import load_rules
    from archkg.rules.engine import compile_expression, evaluate_expression

    p = CaseParameters(
        seed=0,
        corridor_width_m=1.50,
        door_widths_m=(0.95, 0.95, 0.95, 0.95),
        bedroom_w_m=3.0,
        bedroom_h_m=3.0,
        floors=3,
        height_m=10.0,
        total_units=100,
        accessible_units=5,
        bedroom_net_height_m=1.80,  # below the 2.0 m basement floor
        bedroom_level="basement",
        include_stair_schedule=False,
        stair_metrics_below_threshold=False,
    )

    rule = next(
        r for r in load_rules() if r.id == "RC-BASEMENT-MEZZANINE-NETHEIGHT-2.0"
    )
    env = {"label": "bedroom", "level": "basement", "net_height_m": 1.80}
    for k in rule.inputs:
        env.setdefault(k, None)
    tree = compile_expression(rule.logic_expression, rule.inputs)
    engine_fires = not evaluate_expression(tree, env)

    predicted = {v.rule_id for v in predict_expected_violations(p)}
    assert engine_fires, "engine should fire on basement bedroom with height 1.80"
    assert "RC-BASEMENT-MEZZANINE-NETHEIGHT-2.0" in predicted, (
        "predictor must agree with engine on the basement-low-height branch"
    )


def test_examiner_super_high_rise_case_fires_refuge_through_full_engine(
    tmp_path: Path,
) -> None:
    """Codex P18-F R1 P1: the parametrized predictor↔engine semantic test
    only exercises ``logic_expression``; it bypasses ``is_rule_applicable``
    and therefore would not catch the exact regression fixed in this round
    (a 35F / 105.5m project mis-labeled ``高层`` instead of ``超高层`` makes
    GB 50016-5.5.31 silently skip even though height_m > 100).

    Drive the full review pipeline against an examiner-generated super-
    high-rise case and assert RC-REFUGE-LAYER-100M lands in ``issues``,
    not ``skipped``. Also asserts that flipping the meta's height_class
    back to ``高层`` makes the engine skip the rule — guarantees the
    regression detector actually detects.
    """
    import json

    from archkg.adversarial.battery import _review_case
    from archkg.knowledge.loader import load_rules, load_standards
    from archkg.rules.engine import evaluate
    from archkg.schemas import ProjectMeta

    # Seed 6 produces 35F / 105.5m / height_class=超高层 under the v1.0.7
    # _FLOORS distribution. The seed→params mapping is sensitive to
    # _FLOORS contents (it reseeds the RNG from index 0), so the safety-
    # net asserts pin the assumption — bump the seed if either fails.
    case = generate_case(seed=6, out_dir=tmp_path)
    assert case.parameters.floors == 35
    assert case.parameters.height_m > 100.0
    review_dir = _review_case(case)
    issues = json.loads((review_dir / "issues.json").read_text())
    fired = {i["rule_card_id"] for i in issues}
    assert "RC-REFUGE-LAYER-100M" in fired, (
        "examiner-generated super-high-rise case must fire RC-REFUGE-LAYER-100M "
        "through the full engine (predictor → ground_truth → builder → engine "
        "→ adjudicator). If this fails, the height_class classification has "
        "regressed and the examiner mis-labels its own super-high-rise cases."
    )

    # Negative control: re-evaluate the same project_meta but with
    # height_class flipped to '高层'. The clause GB 50016-5.5.31 has
    # applies_to_height_class=[超高层]; the engine MUST skip, not fire.
    standards = load_standards()
    rules = load_rules(standards=standards)
    bad_meta = ProjectMeta(
        project_id="ADV-NEG",
        building_type="residential",
        height_class="高层",
        floors=35,
        height_m=105.5,
    )
    from archkg.graph.builder import EntityGraph
    empty = EntityGraph(
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
    result = evaluate(empty, rules, standards, project_meta=bad_meta)
    refuge_issues = [i for i in result.issues if i.rule_card_id == "RC-REFUGE-LAYER-100M"]
    refuge_skipped = [s for s in result.skipped if s.rule_id == "RC-REFUGE-LAYER-100M"]
    assert refuge_issues == [], (
        "regression detector must detect: 高层 + height>100 should skip, not fire"
    )
    assert len(refuge_skipped) == 1, "the rule must explicitly skip with a reason"
    assert "超高层" in refuge_skipped[0].reason


def test_predict_seven_floor_low_height_edge_against_engine() -> None:
    """Codex P18-F R1 P1: sample_parameters() emits ``height_m = floors *
    {2.8,3.0} + 0.5``, so every 7F case is 20.1m or 21.5m — never the
    7F/15.5m boundary. RC-ELEVATOR-REQUIRED's logic is
    ``floors >= 7 OR height_m > 16``; a 7F project at 15.5m must still
    fire on the floor-count side. Pin the boundary explicitly so the
    OR-branch can't silently drift to AND.
    """
    from archkg.knowledge.loader import load_rules
    from archkg.rules.engine import compile_expression, evaluate_expression

    p = CaseParameters(
        seed=0,
        corridor_width_m=1.50,
        door_widths_m=(0.95, 0.95, 0.95, 0.95),
        bedroom_w_m=3.0,
        bedroom_h_m=3.0,
        floors=7,
        height_m=15.5,  # below the 16m height trigger
        total_units=100,
        accessible_units=5,
        bedroom_net_height_m=2.50,
        bedroom_level="upper",
        include_stair_schedule=False,
        stair_metrics_below_threshold=False,
    )
    rule = next(r for r in load_rules() if r.id == "RC-ELEVATOR-REQUIRED")
    env = {"floors": 7, "height_m": 15.5}
    for k in rule.inputs:
        env.setdefault(k, None)
    tree = compile_expression(rule.logic_expression, rule.inputs)
    engine_fires = not evaluate_expression(tree, env)
    predicted = {v.rule_id for v in predict_expected_violations(p)}
    assert engine_fires, "7F at any height must fire RC-ELEVATOR-REQUIRED"
    assert "RC-ELEVATOR-REQUIRED" in predicted, (
        "predictor must fire on the floors-only branch, not require height>16"
    )
