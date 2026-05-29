from __future__ import annotations

import json
from pathlib import Path

from archkg.graph.builder import EntityGraph
from archkg.knowledge.loader import load_rules, load_standards
from archkg.knowledge.run_readiness import (
    build_rule_input_readiness,
    write_rule_input_readiness,
)
from archkg.rules.engine import evaluate
from archkg.schemas import Corridor, Door, ProjectMeta, Room, Stair


def _graph(stairs: list[Stair] | None = None) -> EntityGraph:
    return EntityGraph(
        source_pdf="fixture.pdf",
        points_per_meter=50.0,
        page_index=0,
        page_width_pt=500.0,
        page_height_pt=400.0,
        rooms=[
            Room(
                id="room-bed",
                page_index=0,
                bbox=(0.0, 0.0, 200.0, 200.0),
                polygon=[(0.0, 0.0), (200.0, 0.0), (200.0, 200.0), (0.0, 200.0)],
                area_m2=12.0,
                label="bedroom",
            )
        ],
        doors=[
            Door(
                id="door-1",
                page_index=0,
                bbox=(90.0, 195.0, 140.0, 205.0),
                width_m=0.9,
            )
        ],
        corridors=[
            Corridor(
                id="corridor-1",
                page_index=0,
                bbox=(0.0, 200.0, 500.0, 260.0),
                polygon=[(0.0, 200.0), (500.0, 200.0), (500.0, 260.0), (0.0, 260.0)],
                min_width_m=1.2,
            )
        ],
        dimensions=[],
        stairs=stairs or [],
    )


def _rules_and_standards():
    standards = load_standards()
    rules = load_rules(standards=standards)
    assert len(rules) == 32
    return rules, standards


def test_rule_input_readiness_covers_all_packaged_rule_cards() -> None:
    rules, standards = _rules_and_standards()
    graph = _graph()
    result = evaluate(graph, rules, standards, project_meta=None)

    report = build_rule_input_readiness(
        graph,
        rules,
        standards,
        project_meta=None,
        skipped=result.skipped,
    )

    assert len(report.rules) == 32
    assert {row.rule_id for row in report.rules} == {rule.id for rule in rules}
    by_rule = {row.rule_id: row for row in report.rules}
    assert by_rule["RC-CORRIDOR-WIDTH"].status == "ready"
    assert by_rule["RC-BEDROOM-AREA"].status == "ready"
    assert by_rule["RC-ELEVATOR-REQUIRED"].status == "missing_input"
    assert by_rule["RC-STAIR-TREAD-WIDTH-0.26"].status == "unsupported_entity"
    assert report.summary["ready"] >= 1
    assert report.summary["missing_input"] >= 1
    assert report.summary["unsupported_entity"] >= 1


def test_rule_input_readiness_distinguishes_applicability_skips() -> None:
    rules, standards = _rules_and_standards()
    meta = ProjectMeta(
        project_id="P-RES",
        building_type="residential",
        height_class="多层",
        floors=6,
        height_m=18.0,
    )
    graph = _graph()
    result = evaluate(graph, rules, standards, project_meta=meta)

    report = build_rule_input_readiness(
        graph,
        rules,
        standards,
        project_meta=meta,
        skipped=result.skipped,
    )

    by_rule = {row.rule_id: row for row in report.rules}
    refuge = by_rule["RC-REFUGE-LAYER-100M"]
    assert refuge.status == "not_applicable"
    assert "超高层" in refuge.reason
    elevator = by_rule["RC-ELEVATOR-REQUIRED"]
    assert elevator.status == "manual_only"
    assert elevator.available_inputs == ["floors", "height_m"]


def test_rule_input_readiness_marks_schedule_only_stairs_low_confidence() -> None:
    rules, standards = _rules_and_standards()
    stair = Stair(
        id="stair-schedule-1",
        page_index=0,
        bbox=(0.0, 0.0, 0.0, 0.0),
        confidence=0.0,
        uncertain=True,
        tread_width_m=0.24,
        riser_height_m=0.20,
        properties={
            "flight_width_m": 1.05,
            "handrail_height_m": 0.85,
            "well_width_m": 0.15,
        },
    )
    graph = _graph(stairs=[stair])
    result = evaluate(graph, rules, standards, project_meta=None)

    report = build_rule_input_readiness(
        graph,
        rules,
        standards,
        project_meta=None,
        skipped=result.skipped,
    )

    by_rule = {row.rule_id: row for row in report.rules}
    tread = by_rule["RC-STAIR-TREAD-WIDTH-0.26"]
    assert tread.status == "low_confidence"
    assert tread.low_confidence_entity_ids == ["stair-schedule-1"]
    assert tread.available_inputs == ["tread_width_m"]


def test_write_rule_input_readiness_persists_json(tmp_path: Path) -> None:
    rules, standards = _rules_and_standards()
    graph = _graph()
    result = evaluate(graph, rules, standards, project_meta=None)
    report = build_rule_input_readiness(
        graph,
        rules,
        standards,
        project_meta=None,
        skipped=result.skipped,
    )

    out = write_rule_input_readiness(report, tmp_path / "rule_input_readiness.json")

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "rule_input_readiness.v1"
    assert len(payload["rules"]) == 32
    assert payload["summary"]["missing_input"] >= 1
