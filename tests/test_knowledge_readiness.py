"""Tests for the production-readiness classifier (Phase 18-A).

The classifier translates "30/30 rule coverage" into "what actually fires
on a real PDF today". These tests lock in:

- per-tier classification logic for each rule shape we ship,
- the packaged rules' tier distribution (so future rule additions force a
  conscious revisit of the readiness story),
- needs_properties is populated for PARTIAL_AUTODETECT only,
- the Stair gate dominates entity classification.
"""

from __future__ import annotations

import pytest

from archkg.knowledge.loader import load_rules
from archkg.knowledge.readiness import (
    DEFAULT_CAPABILITIES,
    BuilderCapabilities,
    ReadinessFinding,
    classify,
    classify_all,
    summarise,
)
from archkg.schemas import RuleCard


def _rule(
    *,
    rule_id: str = "RC-TEST",
    applies_to: str = "Room",
    inputs: list[str] | None = None,
    severity: str | None = None,
    expression: str = "area_m2 >= 5.0",
) -> RuleCard:
    return RuleCard(
        id=rule_id,
        source_clause_ids=["GB50096-5.0.0"],
        applies_to=applies_to,  # type: ignore[arg-type]
        inputs=inputs or ["area_m2"],
        logic_expression=expression,
        output_template="{rule_id}: test",
        severity=severity,  # type: ignore[arg-type]
    )


def test_autodetectable_when_all_inputs_are_schema_fields() -> None:
    rule = _rule(applies_to="Room", inputs=["area_m2"])
    finding = classify(rule)
    assert finding.tier == "AUTODETECTABLE"
    assert finding.needs_properties == ()
    assert "schema fields" in finding.reason


def test_partial_autodetect_when_input_is_unknown_property() -> None:
    rule = _rule(
        applies_to="Room",
        inputs=["net_height_m"],
        expression="net_height_m >= 2.4",
    )
    finding = classify(rule)
    assert finding.tier == "PARTIAL_AUTODETECT"
    assert finding.needs_properties == ("net_height_m",)
    assert "Room.properties[net_height_m]" in finding.reason


def test_partial_autodetect_lists_only_unknown_inputs() -> None:
    # area_m2 is a schema field; level is not — only `level` should surface.
    rule = _rule(
        applies_to="Room",
        inputs=["area_m2", "level"],
        expression="not (level == 'basement') or area_m2 >= 4.0",
    )
    finding = classify(rule)
    assert finding.tier == "PARTIAL_AUTODETECT"
    assert finding.needs_properties == ("level",)


def test_project_meta_driven_for_project_scope_with_error_severity() -> None:
    rule = _rule(
        rule_id="RC-RATIO",
        applies_to="Project",
        inputs=["total_units", "accessible_units"],
        severity="error",
        expression="accessible_units / total_units >= 0.02",
    )
    finding = classify(rule)
    assert finding.tier == "PROJECT_META_DRIVEN"
    assert finding.severity == "error"
    assert "ProjectMeta" in finding.reason


def test_project_scope_default_severity_falls_into_reminder() -> None:
    # applies_to=Project with severity=None → engine stamps 'info' →
    # REMINDER_BY_DESIGN, never PROJECT_META_DRIVEN.
    rule = _rule(applies_to="Project", inputs=["floors"], expression="floors >= 7")
    finding = classify(rule)
    assert finding.tier == "REMINDER_BY_DESIGN"
    assert finding.severity == "info"


def test_reminder_by_design_for_entity_with_info_severity() -> None:
    rule = _rule(
        applies_to="Door",
        inputs=["width_m"],
        severity="info",
        expression="width_m >= 1.0",
    )
    finding = classify(rule)
    assert finding.tier == "REMINDER_BY_DESIGN"


def test_stair_pending_dominates_even_when_inputs_match_schema() -> None:
    # Stair is in schema/engine but NOT in builder. Even if the rule's
    # inputs would be valid Stair fields, the gate fires first.
    rule = _rule(
        rule_id="RC-STAIR",
        applies_to="Stair",
        inputs=["tread_m"],
        expression="tread_m >= 0.26",
    )
    finding = classify(rule)
    assert finding.tier == "STAIR_PENDING"


def test_stair_pending_when_severity_is_info_too() -> None:
    rule = _rule(
        rule_id="RC-STAIR-REMINDER",
        applies_to="Stair",
        inputs=["flight_width_m"],
        severity="info",
        expression="flight_width_m >= 1.10",
    )
    # Stair gate dominates: even info-level stair rules can't fire without
    # a Stair entity, so they're STAIR_PENDING, not REMINDER_BY_DESIGN.
    finding = classify(rule)
    assert finding.tier == "STAIR_PENDING"


def test_stair_becomes_classifiable_when_capabilities_extend() -> None:
    extended = BuilderCapabilities(
        entity_types=DEFAULT_CAPABILITIES.entity_types | {"Stair"},
        entity_fields={
            **DEFAULT_CAPABILITIES.entity_fields,
            "Stair": frozenset({"id", "tread_m", "riser_m"}),
        },
    )
    rule = _rule(
        rule_id="RC-STAIR",
        applies_to="Stair",
        inputs=["tread_m"],
        expression="tread_m >= 0.26",
    )
    finding = classify(rule, extended)
    assert finding.tier == "AUTODETECTABLE"


def test_summarise_counts_per_tier() -> None:
    findings = [
        ReadinessFinding(rule_id="A", tier="AUTODETECTABLE", applies_to="Room", severity="error"),
        ReadinessFinding(rule_id="B", tier="AUTODETECTABLE", applies_to="Door", severity="error"),
        ReadinessFinding(rule_id="C", tier="REMINDER_BY_DESIGN", applies_to="Project", severity="info"),
    ]
    counts = summarise(findings)
    assert counts["AUTODETECTABLE"] == 2
    assert counts["REMINDER_BY_DESIGN"] == 1
    assert counts["PARTIAL_AUTODETECT"] == 0
    assert counts["PROJECT_META_DRIVEN"] == 0
    assert counts["STAIR_PENDING"] == 0


def test_packaged_rules_distribution_matches_readiness_doc() -> None:
    """Lock-in test: the README/READINESS.md numbers come from this snapshot.

    If a future rule changes the distribution, this test forces an explicit
    update to READINESS.md instead of silent drift.
    """
    rules = load_rules()
    findings = classify_all(rules)
    counts = summarise(findings)

    assert sum(counts.values()) == len(rules)
    assert counts["AUTODETECTABLE"] == 4
    assert counts["PROJECT_META_DRIVEN"] == 1
    assert counts["PARTIAL_AUTODETECT"] == 4
    assert counts["STAIR_PENDING"] == 5
    assert counts["REMINDER_BY_DESIGN"] == 18


def test_packaged_autodetectable_rules_are_the_expected_four() -> None:
    rules = load_rules()
    findings = classify_all(rules)
    auto_ids = {f.rule_id for f in findings if f.tier == "AUTODETECTABLE"}
    assert auto_ids == {
        "RC-CORRIDOR-WIDTH",
        "RC-DOOR-WIDTH",
        "RC-BEDROOM-AREA",
        "RC-ACCESSIBLE-INDOOR-CORRIDOR-WIDTH-1.20",
    }


def test_default_capabilities_entity_fields_is_immutable() -> None:
    # Codex P18-A R1 Low: dataclass(frozen=True) only stops attribute
    # reassignment, not in-place mutation of contained dict. We use
    # MappingProxyType so DEFAULT_CAPABILITIES is genuinely a read-only
    # snapshot and a stray test or caller can't drift the global classifier.
    with pytest.raises(TypeError):
        DEFAULT_CAPABILITIES.entity_fields["Room"] = frozenset({"x"})  # type: ignore[index]


def test_packaged_stair_rules_all_pending() -> None:
    rules = load_rules()
    findings = classify_all(rules)
    stair_findings = [f for f in findings if f.applies_to == "Stair"]
    assert len(stair_findings) == 5
    assert all(f.tier == "STAIR_PENDING" for f in stair_findings)
