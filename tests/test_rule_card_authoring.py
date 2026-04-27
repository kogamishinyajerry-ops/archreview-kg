from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from archkg.cli.main import app
from archkg.knowledge.loader import load_standards
from archkg.knowledge.rule_authoring import author_rule_card_draft, write_rule_card_draft
from archkg.schemas.rule_draft import RuleCardDraft


def _clause(clause_id: str):
    return next(c for c in load_standards() if c.id == clause_id)


def test_rule_card_draft_status_is_draft_only() -> None:
    clause = _clause("GB50096-5.7.2")
    draft = author_rule_card_draft(clause)

    assert draft.status == "draft"
    assert draft.schema_version == "rule_card_draft.v1"

    payload = draft.model_dump(mode="json")
    payload["status"] = "active"
    with pytest.raises(ValidationError):
        RuleCardDraft.model_validate(payload)


def test_author_rule_card_draft_records_threshold_inputs_and_review_boundary() -> None:
    draft = author_rule_card_draft(_clause("GB50096-5.7.2"))

    assert draft.source_clause.id == "GB50096-5.7.2"
    assert draft.extracted_threshold.value == 1.2
    assert draft.extracted_threshold.op == ">="
    assert draft.extracted_threshold.unit == "m"
    assert draft.proposed_applies_to == "Corridor"
    assert draft.required_inputs == ["min_width_m"]
    assert draft.proposed_logic_expression == "min_width_m >= 1.20"
    assert draft.proposed_tests
    assert any(test.expect_pass is False for test in draft.proposed_tests)
    assert "human review" in draft.review_gate.lower()


def test_author_rule_card_draft_records_ambiguous_source_evidence() -> None:
    draft = author_rule_card_draft(_clause("GB50096-5.3.1"))

    assert draft.status == "draft"
    assert draft.ambiguity_notes
    assert any("multiple numeric thresholds" in note for note in draft.ambiguity_notes)
    assert "rule_split_or_branching" in draft.missing_evidence


def test_write_rule_card_draft_round_trips(tmp_path: Path) -> None:
    draft = author_rule_card_draft(_clause("GB50096-5.7.2"))
    out = write_rule_card_draft(draft, tmp_path / "draft.json")

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["status"] == "draft"
    assert payload["source_clause"]["id"] == "GB50096-5.7.2"
    assert RuleCardDraft.model_validate(payload) == draft


def test_rule_card_draft_cli_writes_artifact_without_mutating_active_rules(
    tmp_path: Path,
) -> None:
    active_rules = Path("archkg/knowledge/data/rule_cards.yaml")
    before = active_rules.read_text(encoding="utf-8")
    out = tmp_path / "draft.json"

    result = CliRunner().invoke(
        app,
        [
            "rule-card",
            "draft",
            "--clause-id",
            "GB50096-5.7.2",
            "-o",
            str(out),
        ],
        catch_exceptions=False,
    )

    assert result.exit_code == 0, result.output
    assert "draft written" in result.output
    assert out.exists()
    assert active_rules.read_text(encoding="utf-8") == before
    assert not (tmp_path / "rule_cards.yaml").exists()
