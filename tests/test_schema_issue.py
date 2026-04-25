import pytest
from pydantic import ValidationError

from archkg.schemas import Issue, IssueEvidence


def _evidence() -> IssueEvidence:
    return IssueEvidence(
        snippet="走廊净宽 1.05 m",
        page_index=0,
        measured_value=1.05,
        threshold_value=1.2,
        unit="m",
    )


def test_issue_minimal_ok() -> None:
    i = Issue(
        issue_id="ISS-1",
        rule_card_id="RC-CORRIDOR-WIDTH",
        standard_clause_id="GB50096-7.1.1",
        entity_ids=["corridor-1"],
        bbox=(0.0, 0.0, 5.0, 1.0),
        page_index=0,
        message="走廊净宽不足。",
        evidence=_evidence(),
    )
    assert i.severity == "error"
    assert i.evidence.measured_value == 1.05


def test_issue_requires_at_least_one_entity() -> None:
    with pytest.raises(ValidationError):
        Issue(
            issue_id="x",
            rule_card_id="r",
            standard_clause_id="s",
            entity_ids=[],
            bbox=(0, 0, 1, 1),
            page_index=0,
            message="m",
            evidence=_evidence(),
        )


def test_issue_rejects_unknown_severity() -> None:
    with pytest.raises(ValidationError):
        Issue(
            issue_id="x",
            rule_card_id="r",
            standard_clause_id="s",
            entity_ids=["e"],
            bbox=(0, 0, 1, 1),
            page_index=0,
            severity="critical",  # type: ignore[arg-type]
            message="m",
            evidence=_evidence(),
        )
