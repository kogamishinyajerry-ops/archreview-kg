import pytest
from pydantic import ValidationError

from archkg.schemas import RuleCard, RuleCardTestCase


def test_rule_card_minimal_ok() -> None:
    rc = RuleCard(
        id="RC-CORRIDOR-WIDTH",
        source_clause_ids=["GB50096-7.1.1"],
        applies_to="Corridor",
        inputs=["min_width_m"],
        logic_expression="min_width_m >= 1.2",
        output_template="走廊净宽 {{min_width_m}} m 小于 1.2 m。",
        test_cases=[
            RuleCardTestCase(
                name="ok",
                entity={"min_width_m": 1.5},
                expect_pass=True,
            )
        ],
    )
    assert rc.applies_to == "Corridor"
    assert rc.test_cases[0].expect_pass is True


def test_rule_card_requires_source_clause() -> None:
    with pytest.raises(ValidationError):
        RuleCard(
            id="X",
            source_clause_ids=[],
            applies_to="Door",
            inputs=["width_m"],
            logic_expression="width_m >= 0.9",
            output_template="x",
        )


def test_rule_card_rejects_empty_expression() -> None:
    with pytest.raises(ValidationError):
        RuleCard(
            id="X",
            source_clause_ids=["c1"],
            applies_to="Door",
            inputs=["width_m"],
            logic_expression="   ",
            output_template="x",
        )
