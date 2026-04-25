import pytest
from pydantic import TypeAdapter, ValidationError

from archkg.schemas import Corridor, Door, Entity, Room


def test_room_ok() -> None:
    r = Room(
        id="room-1",
        page_index=0,
        bbox=(0.0, 0.0, 10.0, 8.0),
        polygon=[(0, 0), (10, 0), (10, 8), (0, 8)],
        area_m2=80.0,
        label="bedroom",
    )
    assert r.type == "Room"
    assert r.confidence == 1.0
    assert r.uncertain is False


def test_door_uncertain_low_confidence() -> None:
    d = Door(
        id="door-1",
        page_index=0,
        bbox=(1.0, 1.0, 1.9, 1.2),
        width_m=0.85,
        connects=("room-1", "room-2"),
        confidence=0.42,
        uncertain=True,
    )
    assert d.uncertain is True
    assert d.confidence < 0.6


def test_corridor_polygon_min_length() -> None:
    with pytest.raises(ValidationError):
        Corridor(
            id="c-1",
            page_index=0,
            bbox=(0, 0, 1, 1),
            polygon=[(0, 0), (1, 0)],
        )


def test_entity_discriminated_union_roundtrip() -> None:
    adapter: TypeAdapter[Entity] = TypeAdapter(Entity)
    payload = {
        "type": "Door",
        "id": "d",
        "page_index": 0,
        "bbox": [0.0, 0.0, 1.0, 1.0],
        "width_m": 0.9,
    }
    e = adapter.validate_python(payload)
    assert isinstance(e, Door)
    assert e.width_m == 0.9
