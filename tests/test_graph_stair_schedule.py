"""Integration tests for apply_stair_schedule (Phase 18-C)."""

from __future__ import annotations

from pathlib import Path

import pytest

from archkg.graph.builder import EntityGraph, build_graph
from archkg.graph.stair_schedule import (
    StairScheduleApplyError,
    apply_stair_schedule,
)
from archkg.ingest.primitive_extractor import extract
from archkg.knowledge.loader import load_rules, load_standards
from archkg.rules.engine import evaluate
from archkg.schemas import (
    Stair,
    StairSchedule,
    StairScheduleEntry,
)


def _empty_graph(stairs: list[Stair] | None = None) -> EntityGraph:
    return EntityGraph(
        source_pdf="test.pdf",
        points_per_meter=50.0,
        page_index=0,
        page_width_pt=500.0,
        page_height_pt=500.0,
        rooms=[],
        doors=[],
        corridors=[],
        dimensions=[],
        stairs=stairs or [],
    )


def test_materializes_one_stair_per_entry() -> None:
    schedule = StairSchedule(
        project_id="X",
        entries=[
            StairScheduleEntry(
                stair_id="s1", tread_width_m=0.26, handrail_height_m=0.95
            ),
            StairScheduleEntry(stair_id="s2", riser_height_m=0.16),
        ],
    )

    result = apply_stair_schedule(_empty_graph(), schedule)

    assert {s.id for s in result.graph.stairs} == {"s1", "s2"}
    assert result.materialized == {0: "s1", 1: "s2"}
    assert result.conflicted == []


def test_promotes_property_metrics_to_entity_properties() -> None:
    schedule = StairSchedule(
        project_id="X",
        entries=[
            StairScheduleEntry(
                stair_id="s1",
                tread_width_m=0.24,
                flight_width_m=0.95,
                handrail_height_m=0.85,
                well_width_m=0.14,
            )
        ],
    )

    result = apply_stair_schedule(_empty_graph(), schedule)

    s = result.graph.stairs[0]
    # Schema fields land directly on the entity.
    assert s.tread_width_m == 0.24
    # Engine-fallback fields land in properties.
    assert s.properties == {
        "flight_width_m": 0.95,
        "handrail_height_m": 0.85,
        "well_width_m": 0.14,
    }


def test_stair_id_conflict_preserves_builder_geometry() -> None:
    """Codex P18-C R1 P1: builder is authoritative for fields it set;
    schedule must not overwrite a field the builder already populated."""
    existing = Stair(
        id="s1",
        page_index=0,
        bbox=(10.0, 10.0, 100.0, 100.0),
        tread_width_m=0.30,
    )
    schedule = StairSchedule(
        project_id="X",
        entries=[StairScheduleEntry(stair_id="s1", tread_width_m=0.20)],
    )

    result = apply_stair_schedule(_empty_graph(stairs=[existing]), schedule)

    assert result.conflicted == [0]
    assert result.materialized == {}
    # Existing stair retained — no new entity appended.
    assert len(result.graph.stairs) == 1
    # Builder-set value (0.30) is preserved, not overwritten by schedule (0.20).
    assert result.graph.stairs[0].tread_width_m == 0.30
    # Geometry untouched.
    assert result.graph.stairs[0].bbox == (10.0, 10.0, 100.0, 100.0)


def test_stair_id_conflict_merges_metrics_into_none_fields() -> None:
    """When the existing stair has a None metric, schedule fills it in."""
    existing = Stair(
        id="s1",
        page_index=0,
        bbox=(10.0, 10.0, 100.0, 100.0),
        tread_width_m=0.30,  # builder-set
        riser_height_m=None,  # builder didn't extract
        properties={"flight_width_m": 1.20},  # builder-set
    )
    schedule = StairSchedule(
        project_id="X",
        entries=[
            StairScheduleEntry(
                stair_id="s1",
                tread_width_m=0.20,  # ignored — existing not None
                riser_height_m=0.16,  # filled — existing None
                flight_width_m=0.95,  # ignored — existing not None
                handrail_height_m=0.92,  # filled — existing missing
            )
        ],
    )

    result = apply_stair_schedule(_empty_graph(stairs=[existing]), schedule)

    s = result.graph.stairs[0]
    # Builder-set fields preserved.
    assert s.tread_width_m == 0.30
    assert s.properties["flight_width_m"] == 1.20
    assert s.bbox == (10.0, 10.0, 100.0, 100.0)
    # None / missing fields filled from schedule.
    assert s.riser_height_m == 0.16
    assert s.properties["handrail_height_m"] == 0.92


def test_repeated_stair_id_rows_accumulate_metrics() -> None:
    """Codex P18-C R2 P1: multiple schedule rows targeting the same
    builder-sourced stair must accumulate metrics. Each row's merge
    runs against the current running state, not the original stair.
    """
    existing = Stair(
        id="s1",
        page_index=0,
        bbox=(10.0, 10.0, 100.0, 100.0),
        tread_width_m=0.26,  # builder-set; later rows must not overwrite
    )
    schedule = StairSchedule(
        project_id="X",
        entries=[
            # Row A: fills riser_height_m (existing was None).
            StairScheduleEntry(stair_id="s1", riser_height_m=0.16),
            # Row B: tries to overwrite tread (no-op) and fills well_width_m.
            StairScheduleEntry(stair_id="s1", tread_width_m=0.20, well_width_m=0.10),
            # Row C: fills handrail_height_m (still missing).
            StairScheduleEntry(stair_id="s1", handrail_height_m=0.90),
        ],
    )

    result = apply_stair_schedule(_empty_graph(stairs=[existing]), schedule)

    assert result.conflicted == [0, 1, 2]
    assert result.materialized == {}
    assert len(result.graph.stairs) == 1
    s = result.graph.stairs[0]
    # Builder-set value preserved across all rows.
    assert s.tread_width_m == 0.26
    # Each subsequent row contributed its own missing-field fill,
    # without losing previous accumulations.
    assert s.riser_height_m == 0.16
    assert s.properties["well_width_m"] == 0.10
    assert s.properties["handrail_height_m"] == 0.90


def test_page_index_out_of_range_raises() -> None:
    """Codex P18-C R1 P0: page_index validated against single-page graph."""
    schedule = StairSchedule(
        project_id="X",
        entries=[
            StairScheduleEntry(stair_id="s1", page_index=99, tread_width_m=0.26),
        ],
    )
    with pytest.raises(StairScheduleApplyError, match="page_index=99"):
        apply_stair_schedule(_empty_graph(), schedule)


def test_empty_metric_entry_recorded_separately() -> None:
    schedule = StairSchedule(
        project_id="X",
        entries=[StairScheduleEntry(stair_id="s1")],
    )

    result = apply_stair_schedule(_empty_graph(), schedule)

    assert result.materialized == {0: "s1"}
    assert result.empty_metric_entries == [0]
    # Stair is created but every metric is None — engine short-circuits.
    s = result.graph.stairs[0]
    assert s.tread_width_m is None
    assert s.properties == {}


def test_does_not_mutate_input_graph() -> None:
    g = _empty_graph()
    schedule = StairSchedule(
        project_id="X",
        entries=[StairScheduleEntry(stair_id="s1", tread_width_m=0.26)],
    )

    apply_stair_schedule(g, schedule)

    assert g.stairs == [], "input graph must not be mutated"


def test_placeholder_bbox_marks_uncertain() -> None:
    schedule = StairSchedule(
        project_id="X",
        entries=[StairScheduleEntry(stair_id="s1", tread_width_m=0.26)],
    )

    result = apply_stair_schedule(_empty_graph(), schedule)

    s = result.graph.stairs[0]
    assert s.bbox == (0.0, 0.0, 0.0, 0.0)
    assert s.confidence == 0.0
    assert s.uncertain is True


def test_schedule_sourced_stair_issues_have_no_bbox(sample_pdf: Path) -> None:
    """Codex P18-C R1 P0: schedule-only stairs must not produce drawn
    bboxes on the annotated PDF. Engine must emit bbox=None for entities
    with zero-area placeholder geometry, otherwise the annotator stacks
    every stair-rule label at the page origin.
    """
    primitives = extract(sample_pdf, points_per_meter=50.0)
    graph = build_graph(primitives)
    standards = load_standards()
    rules = load_rules(standards=standards)

    from archkg.knowledge.stair_schedule import load_stair_schedule
    from archkg.schemas import ProjectMeta

    sample_dir = Path(__file__).parent.parent / "samples"
    schedule = load_stair_schedule(sample_dir / "stair_schedule_demo.yaml")
    augmented = apply_stair_schedule(graph, schedule).graph

    meta = ProjectMeta(
        project_id="DEMO-001",
        building_type="residential",
        height_class="多层",
        floors=6,
    )

    result = evaluate(augmented, rules, standards, project_meta=meta)
    stair_issues = [i for i in result.issues if i.rule_card_id.startswith("RC-STAIR-")]
    # All 5 stair-on-entity issues come from the schedule-sourced stair
    # whose bbox is the placeholder (0,0,0,0). Engine must convert that
    # to None so the annotator's project-level skip path handles them.
    schedule_sourced = [
        i for i in stair_issues if i.entity_ids and i.entity_ids[0] == "stair-1"
    ]
    assert len(schedule_sourced) == 5
    assert all(i.bbox is None for i in schedule_sourced), (
        "schedule-sourced stair issues must carry bbox=None so the annotator skips them"
    )


def test_demo_schedule_unlocks_all_five_stair_rules(sample_pdf: Path) -> None:
    """Lock-in: feeding the packaged demo stair schedule into the demo PDF
    must cause exactly the 5 STAIR_PENDING rule cards to fire on top of
    the baseline. Regression guard for the v1.0.3 ship claim.
    """
    primitives = extract(sample_pdf, points_per_meter=50.0)
    graph = build_graph(primitives)
    standards = load_standards()
    rules = load_rules(standards=standards)

    from archkg.knowledge.stair_schedule import load_stair_schedule
    from archkg.schemas import ProjectMeta

    sample_dir = Path(__file__).parent.parent / "samples"
    schedule = load_stair_schedule(sample_dir / "stair_schedule_demo.yaml")
    augmented = apply_stair_schedule(graph, schedule).graph

    meta = ProjectMeta(
        project_id="DEMO-001",
        building_type="residential",
        height_class="多层",
        floors=6,
    )

    baseline = evaluate(graph, rules, standards, project_meta=meta)
    enriched = evaluate(augmented, rules, standards, project_meta=meta)

    expected_stair = {
        "RC-STAIR-FLIGHT-WIDTH-1.10",
        "RC-STAIR-TREAD-WIDTH-0.26",
        "RC-STAIR-RISER-HEIGHT-0.175",
        "RC-STAIR-HANDRAIL-0.90",
        "RC-STAIR-WELL-WIDTH-0.11",
    }

    new_ids = {i.rule_card_id for i in enriched.issues} - {
        i.rule_card_id for i in baseline.issues
    }
    assert new_ids == expected_stair

    # Lock the count too: each stair rule fires exactly once on the
    # one schedule entry, not multiple times.
    delta = len(enriched.issues) - len(baseline.issues)
    assert delta == len(expected_stair), (
        f"expected exactly {len(expected_stair)} new issues from stair schedule, got {delta}"
    )

    from collections import Counter
    counts = Counter(
        i.rule_card_id for i in enriched.issues if i.rule_card_id in expected_stair
    )
    assert all(v == 1 for v in counts.values()), (
        f"each stair rule should fire exactly once, got {dict(counts)}"
    )
