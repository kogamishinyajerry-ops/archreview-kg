"""Tests for archkg.kg.recognition_quality (M5.E.1)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from archkg.kg import KGStore, add_feedback, ingest_run, per_rule_quality
from archkg.kg.recognition_quality import PerRuleStats, _load_expected_counts


def _seed_run(tmp_path: Path) -> tuple[Path, Path, list[int]]:
    """Build a tmp KG with one run, 4 issues of RC-A and 2 of RC-B."""
    db = tmp_path / "kg.db"
    run_dir = tmp_path / "demo_run"
    run_dir.mkdir()
    issues = []
    for i in range(4):
        issues.append(
            {
                "issue_id": f"A-{i}",
                "rule_card_id": "RC-A",
                "standard_clause_id": "S-1.1",
                "entity_ids": [],
                "page_index": 0,
                "severity": "error",
                "message": "a",
            }
        )
    for i in range(2):
        issues.append(
            {
                "issue_id": f"B-{i}",
                "rule_card_id": "RC-B",
                "standard_clause_id": "S-2.1",
                "entity_ids": [],
                "page_index": 0,
                "severity": "warning",
                "message": "b",
            }
        )
    (run_dir / "issues.json").write_text(json.dumps(issues), encoding="utf-8")
    with KGStore(db) as store:
        ingest_run(store, run_dir=run_dir, project_slug="demo")
        ids = [int(r["id"]) for r in store._conn.execute("SELECT id FROM issue ORDER BY id").fetchall()]
    return db, tmp_path, ids


def test_no_feedback_recall_and_precision_are_none(tmp_path: Path) -> None:
    db, repo, _ = _seed_run(tmp_path)
    rep = per_rule_quality(db_path=db, repo=repo)
    assert rep["status"] == "ok"
    rules = {r["rule_id"]: r for r in rep["rules"]}
    assert rules["RC-A"]["precision"] is None
    assert rules["RC-B"]["precision"] is None
    assert rep["weighted_precision"] is None
    assert rep["weighted_recall"] is None


def test_precision_from_feedback(tmp_path: Path) -> None:
    db, repo, ids = _seed_run(tmp_path)
    with KGStore(db, create=False) as store:
        # 3 confirm + 1 reject on RC-A → precision = 0.75
        for i in range(3):
            add_feedback(store, issue_id=ids[i], reviewer_id="r", event_type="confirm")
        add_feedback(store, issue_id=ids[3], reviewer_id="r", event_type="reject")
        # 2 confirm on RC-B → precision = 1.0
        add_feedback(store, issue_id=ids[4], reviewer_id="r", event_type="confirm")
        add_feedback(store, issue_id=ids[5], reviewer_id="r", event_type="confirm")
    rep = per_rule_quality(db_path=db, repo=repo)
    rules = {r["rule_id"]: r for r in rep["rules"]}
    assert rules["RC-A"]["precision"] == pytest.approx(0.75)
    assert rules["RC-B"]["precision"] == pytest.approx(1.0)
    # Weighted by sample size: RC-A samples=4, RC-B samples=2 → (0.75*4 + 1.0*2) / 6 = 0.833
    assert rep["weighted_precision"] == pytest.approx((0.75 * 4 + 1.0 * 2) / 6, abs=1e-3)


def test_recall_from_expected_inventory(tmp_path: Path) -> None:
    db, repo, ids = _seed_run(tmp_path)
    # Plant an expected file under benchmark dir
    bench = repo / "samples" / "understanding_benchmarks" / "synth"
    bench.mkdir(parents=True)
    (bench / "case_expected.json").write_text(
        json.dumps({"expected_rule_counts": {"RC-A": 5, "RC-B": 2}}),
        encoding="utf-8",
    )
    # 3 confirms on RC-A
    with KGStore(db, create=False) as store:
        for i in range(3):
            add_feedback(store, issue_id=ids[i], reviewer_id="r", event_type="confirm")
    rep = per_rule_quality(db_path=db, repo=repo)
    rules = {r["rule_id"]: r for r in rep["rules"]}
    # Detected 4, expected 5 → FN = 1; tp = 3 → recall = 3 / (3+1) = 0.75
    assert rules["RC-A"]["expected"] == 5
    assert rules["RC-A"]["recall"] == pytest.approx(0.75)


def test_per_rule_stats_dataclass_to_dict() -> None:
    s = PerRuleStats(
        rule_id="X",
        tp=3,
        fp=1,
        detected=4,
        expected=5,
        precision=0.75,
        recall=0.6,
        sample_size=4,
    )
    d = s.to_dict()
    assert d["rule_id"] == "X"
    assert d["precision"] == 0.75
    assert d["recall"] == 0.6
    assert d["sample_size"] == 4


def test_load_expected_counts_empty(tmp_path: Path) -> None:
    counts = _load_expected_counts(tmp_path / "missing_repo")
    assert counts == {}


def test_no_db_returns_empty_rules(tmp_path: Path) -> None:
    rep = per_rule_quality(db_path=tmp_path / "nope.db", repo=tmp_path)
    assert rep["status"] == "no_kg_db"
    assert rep["rules"] == []
