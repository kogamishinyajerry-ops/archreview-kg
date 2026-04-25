from pathlib import Path

import pytest

from archkg.knowledge.loader import (
    KnowledgeBaseError,
    load_rules,
    load_standards,
)


def test_packaged_standards_load_and_have_min_5() -> None:
    clauses = load_standards()
    assert len(clauses) >= 5
    ids = {c.id for c in clauses}
    assert "GB50096-5.7.2" in ids
    assert "GB50096-5.5.2" in ids
    assert "GB50096-5.3.1" in ids


def test_phase8_standards_library_size_and_coverage() -> None:
    clauses = load_standards()
    assert len(clauses) >= 25, "Phase 8 expanded knowledge base should ship ≥25 clauses"
    sources = {c.source for c in clauses}
    assert {"GB 50096-2011", "GB 50352-2019", "GB 50016-2014", "GB 50763-2012"} <= sources
    categories = {c.category for c in clauses}
    assert {"geometric", "fire", "accessibility", "topological"} <= categories


def test_phase8_clauses_carry_metadata() -> None:
    clauses = load_standards()
    by_id = {c.id: c for c in clauses}
    elevator = by_id["GB50096-6.4.1"]
    assert elevator.category == "topological"
    assert elevator.applies_to_height_class is not None
    assert "高层" in elevator.applies_to_height_class
    accessibility_door = by_id["GB50763-3.5.3"]
    assert accessibility_door.category == "accessibility"
    assert accessibility_door.paraphrase is True


def test_packaged_rules_load_and_have_3() -> None:
    rules = load_rules()
    ids = {r.id for r in rules}
    assert ids == {"RC-CORRIDOR-WIDTH", "RC-DOOR-WIDTH", "RC-BEDROOM-AREA"}


def test_rules_resolve_against_standards() -> None:
    standards = load_standards()
    rules = load_rules(standards=standards)
    known = {c.id for c in standards}
    for r in rules:
        for cid in r.source_clause_ids:
            assert cid in known


def test_loader_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(KnowledgeBaseError):
        load_standards(tmp_path / "nope.yaml")


def test_loader_rejects_non_list(tmp_path: Path) -> None:
    bad = tmp_path / "standards.yaml"
    bad.write_text("a: 1\nb: 2\n", encoding="utf-8")
    with pytest.raises(KnowledgeBaseError, match="must be a YAML list"):
        load_standards(bad)


def test_loader_rejects_duplicate_ids(tmp_path: Path) -> None:
    bad = tmp_path / "standards.yaml"
    bad.write_text(
        "- id: X\n  source: S\n  clause_text: t\n  unit: m\n"
        "- id: X\n  source: S\n  clause_text: t2\n  unit: m\n",
        encoding="utf-8",
    )
    with pytest.raises(KnowledgeBaseError, match="duplicate id"):
        load_standards(bad)


def test_loader_rejects_unknown_clause_reference(tmp_path: Path) -> None:
    bad = tmp_path / "rule_cards.yaml"
    bad.write_text(
        "- id: RC-X\n"
        "  source_clause_ids: [DOES-NOT-EXIST]\n"
        "  applies_to: Door\n"
        "  inputs: [width_m]\n"
        "  logic_expression: 'width_m >= 0.9'\n"
        "  output_template: x\n",
        encoding="utf-8",
    )
    standards = load_standards()
    with pytest.raises(KnowledgeBaseError, match="unknown clause"):
        load_rules(bad, standards=standards)


def test_loader_rejects_schema_violation(tmp_path: Path) -> None:
    bad = tmp_path / "rule_cards.yaml"
    bad.write_text(
        "- id: RC-X\n"
        "  source_clause_ids: []\n"  # min_length=1 violation
        "  applies_to: Door\n"
        "  inputs: [width_m]\n"
        "  logic_expression: 'width_m >= 0.9'\n"
        "  output_template: x\n",
        encoding="utf-8",
    )
    with pytest.raises(KnowledgeBaseError, match=r"invalid rule_cards\.yaml"):
        load_rules(bad)
