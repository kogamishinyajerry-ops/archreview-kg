import pytest
from pydantic import ValidationError

from archkg.schemas import StandardClause


def test_standard_clause_minimal_ok() -> None:
    c = StandardClause(
        id="GB50096-7.1.1",
        source="GB 50096-2011",
        clause_text="住宅套内入户门净宽不应小于 0.90 m。",
        unit="m",
        threshold_value=0.9,
        threshold_op=">=",
    )
    assert c.threshold_value == 0.9
    assert c.threshold_op == ">="


def test_standard_clause_rejects_extra_field() -> None:
    with pytest.raises(ValidationError):
        StandardClause(
            id="X",
            source="Y",
            clause_text="z",
            unit="m",
            unknown_field="boom",  # type: ignore[call-arg]
        )


def test_standard_clause_rejects_bad_op() -> None:
    with pytest.raises(ValidationError):
        StandardClause(
            id="X",
            source="Y",
            clause_text="z",
            unit="m",
            threshold_value=1.0,
            threshold_op="~=",  # type: ignore[arg-type]
        )


def test_standard_clause_phase8_defaults() -> None:
    """Pre-Phase 8 yaml entries (no metadata) must still validate to residential/geometric."""
    c = StandardClause(
        id="LEGACY-1",
        source="GB 50096-2011",
        clause_text="x",
        unit="m",
    )
    assert c.category == "geometric"
    assert c.applies_to_building_type == ("residential",)
    assert c.applies_to_height_class is None
    assert c.version is None
    assert c.supersedes is None
    assert c.paraphrase is False


def test_standard_clause_accepts_phase8_metadata() -> None:
    c = StandardClause(
        id="GB50016-5.5.13",
        source="GB 50016-2014",
        version="2014",
        category="fire",
        applies_to_building_type=("residential", "public"),
        applies_to_height_class=("高层", "超高层"),
        supersedes="GB50016-2006-5.4.1",
        paraphrase=True,
        clause_text="高层建筑安全出口数量不应少于 2 个。",
        unit="count",
        threshold_value=2.0,
        threshold_op=">=",
    )
    assert c.category == "fire"
    assert "public" in c.applies_to_building_type
    assert c.applies_to_height_class == ("高层", "超高层")
    assert c.paraphrase is True


def test_standard_clause_rejects_empty_building_type() -> None:
    with pytest.raises(ValidationError):
        StandardClause(
            id="X",
            source="Y",
            clause_text="z",
            unit="m",
            applies_to_building_type=(),
        )


def test_standard_clause_rejects_unknown_category() -> None:
    with pytest.raises(ValidationError):
        StandardClause(
            id="X",
            source="Y",
            clause_text="z",
            unit="m",
            category="bogus",  # type: ignore[arg-type]
        )
