"""Integration tests for apply_room_schedule (Phase 18-B).

Locks in the merge-into-properties contract that drives the 4
PARTIAL_AUTODETECT rule cards.
"""

from __future__ import annotations

from pathlib import Path

from archkg.graph.builder import EntityGraph, build_graph
from archkg.graph.schedule import apply_room_schedule
from archkg.ingest.primitive_extractor import extract
from archkg.knowledge.loader import load_rules, load_standards
from archkg.rules.engine import evaluate
from archkg.schemas import (
    BBox,
    Room,
    RoomSchedule,
    RoomScheduleEntry,
)


def _room(rid: str, label: str | None = None) -> Room:
    return Room(
        id=rid,
        page_index=0,
        bbox=(0.0, 0.0, 1.0, 1.0),
        polygon=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)],
        label=label,
    )


def _graph(rooms: list[Room]) -> EntityGraph:
    return EntityGraph(
        source_pdf="test.pdf",
        points_per_meter=50.0,
        page_index=0,
        page_width_pt=500.0,
        page_height_pt=500.0,
        rooms=rooms,
        doors=[],
        corridors=[],
        dimensions=[],
        stairs=[],
    )


def test_room_id_selector_applies_to_single_room() -> None:
    g = _graph([_room("room-1", "bedroom"), _room("room-2", "bedroom")])
    schedule = RoomSchedule(
        project_id="X",
        entries=[RoomScheduleEntry(room_id="room-1", net_height_m=2.30)],
    )

    result = apply_room_schedule(g, schedule)

    by_id = {r.id: r for r in result.graph.rooms}
    assert by_id["room-1"].properties == {"net_height_m": 2.30}
    assert by_id["room-2"].properties == {}
    assert result.matched == {0: ["room-1"]}
    assert result.unmatched == []


def test_label_selector_fans_out_to_all_matching_rooms() -> None:
    g = _graph(
        [
            _room("room-1", "bedroom"),
            _room("room-2", "bedroom"),
            _room("room-3", "kitchen"),
        ]
    )
    schedule = RoomSchedule(
        project_id="X",
        entries=[RoomScheduleEntry(label="bedroom", level="upper")],
    )

    result = apply_room_schedule(g, schedule)

    by_id = {r.id: r for r in result.graph.rooms}
    assert by_id["room-1"].properties == {"level": "upper"}
    assert by_id["room-2"].properties == {"level": "upper"}
    assert by_id["room-3"].properties == {}
    assert result.matched == {0: ["room-1", "room-2"]}


def test_unmatched_entry_recorded_for_audit() -> None:
    g = _graph([_room("room-1", "bedroom")])
    schedule = RoomSchedule(
        project_id="X",
        entries=[
            RoomScheduleEntry(label="kitchen", net_height_m=2.40),
            RoomScheduleEntry(room_id="room-99", level="basement"),
        ],
    )

    result = apply_room_schedule(g, schedule)

    assert result.matched == {}
    assert result.unmatched == [0, 1]


def test_empty_property_entry_recorded_separately() -> None:
    g = _graph([_room("room-1", "bedroom")])
    schedule = RoomSchedule(
        project_id="X",
        entries=[RoomScheduleEntry(label="bedroom")],
    )

    result = apply_room_schedule(g, schedule)

    # selector matched but no property data — neither violation nor audit silence.
    assert result.matched == {}
    assert result.unmatched == []
    assert result.empty_property_entries == [0]
    # Room.properties stays untouched.
    assert result.graph.rooms[0].properties == {}


def test_does_not_mutate_input_graph() -> None:
    rooms = [_room("room-1", "bedroom")]
    g = _graph(rooms)
    schedule = RoomSchedule(
        project_id="X",
        entries=[RoomScheduleEntry(label="bedroom", net_height_m=2.50)],
    )

    apply_room_schedule(g, schedule)

    assert g.rooms[0].properties == {}, "input graph must not be mutated"


def test_room_id_wins_over_label_when_both_set() -> None:
    g = _graph([_room("room-1", "bedroom"), _room("room-2", "bedroom")])
    schedule = RoomSchedule(
        project_id="X",
        entries=[
            # Both selectors set — room_id should take precedence.
            RoomScheduleEntry(room_id="room-1", label="bedroom", net_height_m=2.30),
        ],
    )

    result = apply_room_schedule(g, schedule)

    by_id = {r.id: r for r in result.graph.rooms}
    assert by_id["room-1"].properties == {"net_height_m": 2.30}
    assert by_id["room-2"].properties == {}


def test_later_entry_overwrites_earlier_property_on_same_room() -> None:
    g = _graph([_room("room-1", "bedroom")])
    schedule = RoomSchedule(
        project_id="X",
        entries=[
            RoomScheduleEntry(label="bedroom", net_height_m=2.30),
            RoomScheduleEntry(room_id="room-1", net_height_m=2.50),
        ],
    )

    result = apply_room_schedule(g, schedule)

    assert result.graph.rooms[0].properties == {"net_height_m": 2.50}


def test_demo_schedule_unlocks_all_four_partial_rules(sample_pdf: Path) -> None:
    """Lock-in: feeding the packaged demo schedule into the demo PDF must
    cause exactly the 4 PARTIAL_AUTODETECT rule cards to fire on top of
    the baseline 23 issues. Regression guard for the v1.0.2 ship claim.
    """
    primitives = extract(sample_pdf, points_per_meter=50.0)
    graph = build_graph(primitives)
    standards = load_standards()
    rules = load_rules(standards=standards)

    from archkg.knowledge.room_schedule import load_room_schedule
    from archkg.schemas import ProjectMeta

    sample_dir = Path(__file__).parent.parent / "samples"
    schedule = load_room_schedule(sample_dir / "room_schedule_demo.yaml")
    augmented = apply_room_schedule(graph, schedule).graph

    meta = ProjectMeta(
        project_id="DEMO-001",
        building_type="residential",
        height_class="多层",
        floors=6,
    )

    baseline = evaluate(graph, rules, standards, project_meta=meta)
    enriched = evaluate(augmented, rules, standards, project_meta=meta)

    expected_partial = {
        "RC-LIVING-BEDROOM-NETHEIGHT-2.4",
        "RC-PITCHED-ROOF-MAJORITY-NETHEIGHT-2.1",
        "RC-BASEMENT-MEZZANINE-NETHEIGHT-2.0",
        "RC-NO-LIVING-IN-BASEMENT",
    }

    new_ids = {i.rule_card_id for i in enriched.issues} - {
        i.rule_card_id for i in baseline.issues
    }
    assert new_ids == expected_partial

    # Codex P18-B R1 P1: lock the *count* of new issues, not just the
    # set of new ids. Without this, a regression that double-fires one
    # of the partial rules on the demo would still pass the set check.
    delta = len(enriched.issues) - len(baseline.issues)
    assert delta == len(expected_partial), (
        f"expected exactly {len(expected_partial)} new issues from schedule, got {delta}"
    )

    # And each partial rule should fire exactly once, not multiple times.
    from collections import Counter
    counts = Counter(
        i.rule_card_id for i in enriched.issues if i.rule_card_id in expected_partial
    )
    assert all(v == 1 for v in counts.values()), (
        f"each partial rule should fire exactly once, got {dict(counts)}"
    )


def test_bbox_type_is_importable_for_test_helpers() -> None:
    # sanity: BBox import from archkg.schemas works (some tests build
    # rooms via dict; this guards the public re-export).
    box: BBox = (0.0, 0.0, 1.0, 1.0)
    assert isinstance(box, tuple)
