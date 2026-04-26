"""Production-readiness classifier for rule cards.

Phase 18-A motivation: v1.0 reached 30/30 standards coverage, but "rules
defined" ≠ "rules fire on real PDFs". Each rule needs upstream data the
graph builder may or may not produce. Without a structured view, users
can mistake the 100% coverage milestone for end-to-end auto-review,
which it isn't.

This module classifies every loaded rule into one of five tiers:

  AUTODETECTABLE       — entity-level rule whose inputs are all schema
                         fields the current graph builder produces. The
                         rule will fire (or correctly not-fire) on any
                         PDF the builder can parse.
  PARTIAL_AUTODETECT   — entity-level rule that depends on entity.properties
                         keys the current builder leaves empty. The
                         rule's logic is correct, but it will never fire
                         until a builder pass populates the property
                         (e.g. Room.properties.net_height_m via section-
                         view OCR or schedule binding).
  PROJECT_META_DRIVEN  — applies_to=Project, severity≠info. Fires when
                         ProjectMeta carries the relevant fields (floors,
                         height_m, fire_class, total_units, ...).
  REMINDER_BY_DESIGN   — severity=info reminder (entity- or project-level).
                         By design surfaces a manual-check item; the
                         engine isn't asserting a hard violation.
  STAIR_PENDING        — applies_to=Stair, but the current graph builder
                         doesn't produce Stair entities. The rule and
                         engine wiring are in place; needs a Phase 18+
                         PDF stair-detection pass to start firing.

The classifier is the source of truth for the README "what works today"
section, the `archkg clause readiness` CLI, and any downstream readiness
audits.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

from archkg.schemas import RuleCard

ReadinessTier = Literal[
    "AUTODETECTABLE",
    "PARTIAL_AUTODETECT",
    "PROJECT_META_DRIVEN",
    "REMINDER_BY_DESIGN",
    "STAIR_PENDING",
]


@dataclass(frozen=True)
class BuilderCapabilities:
    """What the graph builder actually produces today.

    Entity types absent from `entity_types` are not built at all (see
    Phase 15: Stair is in schema and engine but not builder). For each
    built entity, `entity_fields` lists the schema fields the builder
    can populate end-to-end (auto-detected from PDF or bound from
    dimension text). Anything else lives under `entity.properties` and
    the builder leaves it empty until a future PDF pass fills it in.
    """

    entity_types: frozenset[str]
    # MappingProxyType makes entity_fields read-only at runtime. dataclass
    # frozen=True alone only stops attribute reassignment, not in-place
    # mutation of a contained dict (Codex P18-A R1 Low finding).
    entity_fields: Mapping[str, frozenset[str]]


# As-of v1.0 (Phase 17). When the builder gains a new pass, update this
# dataclass and the classifier output adjusts automatically.
DEFAULT_CAPABILITIES = BuilderCapabilities(
    entity_types=frozenset({"Room", "Door", "Corridor", "Dimension", "Wall"}),
    entity_fields=MappingProxyType({
        "Room": frozenset({"id", "polygon", "bbox", "area_m2", "label"}),
        "Door": frozenset({"id", "bbox", "width_m", "connects"}),
        "Corridor": frozenset({"id", "polygon", "bbox", "min_width_m"}),
        "Wall": frozenset({"id", "p0", "p1", "thickness_m", "bbox"}),
        # Stair is in the schema and engine but not the builder.
        "Stair": frozenset(),
    }),
)


@dataclass(frozen=True)
class ReadinessFinding:
    rule_id: str
    tier: ReadinessTier
    applies_to: str
    severity: str
    needs_properties: tuple[str, ...] = ()  # populated for PARTIAL_AUTODETECT
    reason: str = ""


def _effective_severity(rule: RuleCard) -> str:
    """Severity engine will stamp at issue-emit time."""
    if rule.severity is not None:
        return rule.severity
    return "info" if rule.applies_to == "Project" else "error"


def classify(rule: RuleCard, capabilities: BuilderCapabilities = DEFAULT_CAPABILITIES) -> ReadinessFinding:
    severity = _effective_severity(rule)

    # Stair gating dominates everything else: the rule cannot fire at all
    # without the entity. Stair reminders are still STAIR_PENDING because
    # they need at least one Stair entity to anchor against.
    if rule.applies_to == "Stair" and (
        "Stair" not in capabilities.entity_types
        or not capabilities.entity_fields.get("Stair")
    ):
        return ReadinessFinding(
            rule_id=rule.id,
            tier="STAIR_PENDING",
            applies_to=rule.applies_to,
            severity=severity,
            reason="graph builder does not yet produce Stair entities; needs Phase 18+ PDF stair detection",
        )

    if severity == "info":
        return ReadinessFinding(
            rule_id=rule.id,
            tier="REMINDER_BY_DESIGN",
            applies_to=rule.applies_to,
            severity=severity,
            reason="rule surfaces a manual-check reminder rather than asserting a hard violation",
        )

    if rule.applies_to == "Project":
        return ReadinessFinding(
            rule_id=rule.id,
            tier="PROJECT_META_DRIVEN",
            applies_to=rule.applies_to,
            severity=severity,
            reason="fires from ProjectMeta inputs; needs --project-meta in `archkg review`",
        )

    schema_fields = capabilities.entity_fields.get(rule.applies_to, frozenset())
    needs_properties = tuple(k for k in rule.inputs if k not in schema_fields)
    if needs_properties:
        return ReadinessFinding(
            rule_id=rule.id,
            tier="PARTIAL_AUTODETECT",
            applies_to=rule.applies_to,
            severity=severity,
            needs_properties=needs_properties,
            reason=(
                f"depends on {rule.applies_to}.properties[{', '.join(needs_properties)}] which "
                f"the current builder does not populate"
            ),
        )

    return ReadinessFinding(
        rule_id=rule.id,
        tier="AUTODETECTABLE",
        applies_to=rule.applies_to,
        severity=severity,
        reason="all inputs are schema fields the graph builder produces",
    )


def classify_all(rules: list[RuleCard], capabilities: BuilderCapabilities = DEFAULT_CAPABILITIES) -> list[ReadinessFinding]:
    return [classify(r, capabilities) for r in rules]


def summarise(findings: list[ReadinessFinding]) -> dict[ReadinessTier, int]:
    """Count rules per tier."""
    counts: dict[ReadinessTier, int] = {
        "AUTODETECTABLE": 0,
        "PARTIAL_AUTODETECT": 0,
        "PROJECT_META_DRIVEN": 0,
        "REMINDER_BY_DESIGN": 0,
        "STAIR_PENDING": 0,
    }
    for f in findings:
        counts[f.tier] = counts.get(f.tier, 0) + 1
    return counts
