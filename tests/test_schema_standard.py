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
