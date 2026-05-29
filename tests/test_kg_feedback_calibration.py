"""Tests for archkg.kg.feedback and archkg.kg.calibration (M5.G)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from archkg.kg import (
    KGStore,
    add_feedback,
    build_calibration_report,
    feedback_loop_synthetic_test,
    ingest_run,
    rule_priors,
)
from archkg.kg.calibration import DEFAULT_BINS, CalibrationBin
from archkg.kg.feedback import EVENT_TYPES, PRIOR_ALPHA, PRIOR_BETA, upsert_reviewer


def _seed_for_feedback(tmp_path: Path) -> tuple[Path, list[int]]:
    """Build a KG with 5 issues all under RC-CORRIDOR-WIDTH for testing."""
    db = tmp_path / "kg.db"
    run_dir = tmp_path / "demo_run"
    run_dir.mkdir()
    (run_dir / "issues.json").write_text(
        json.dumps(
            [
                {
                    "issue_id": f"ISS-{i}",
                    "rule_card_id": "RC-CORRIDOR-WIDTH",
                    "standard_clause_id": "GB50096-5.7.2",
                    "entity_ids": [],
                    "page_index": 0,
                    "severity": "error",
                    "message": f"corridor {i}",
                }
                for i in range(5)
            ]
        ),
        encoding="utf-8",
    )
    with KGStore(db) as store:
        ingest_run(store, run_dir=run_dir, project_slug="demo")
        rows = store._conn.execute("SELECT id FROM issue ORDER BY id").fetchall()
        ids = [int(r["id"]) for r in rows]
    return db, ids


def test_event_types_complete() -> None:
    assert set(EVENT_TYPES) == {"confirm", "reject", "needs_info", "resolve", "supersede", "comment"}


def test_add_feedback_inserts_and_updates_status(tmp_path: Path) -> None:
    db, issue_ids = _seed_for_feedback(tmp_path)
    with KGStore(db, create=False) as store:
        fb = add_feedback(store, issue_id=issue_ids[0], reviewer_id="r1", event_type="reject")
        assert fb > 0
        cur = store._conn.execute("SELECT status FROM issue WHERE id = ?", (issue_ids[0],))
        assert cur.fetchone()["status"] == "rejected"
        # Reviewer was upserted
        cur = store._conn.execute("SELECT COUNT(*) AS c FROM reviewer")
        assert cur.fetchone()["c"] == 1


def test_add_feedback_rejects_unknown_event_type(tmp_path: Path) -> None:
    db, issue_ids = _seed_for_feedback(tmp_path)
    with KGStore(db, create=False) as store, pytest.raises(ValueError):
        add_feedback(store, issue_id=issue_ids[0], reviewer_id="r1", event_type="bogus")


def test_rule_priors_excludes_rules_without_feedback(tmp_path: Path) -> None:
    db, issue_ids = _seed_for_feedback(tmp_path)
    with KGStore(db, create=False) as store:
        priors = rule_priors(store)
        assert priors == []
        add_feedback(store, issue_id=issue_ids[0], reviewer_id="r", event_type="reject")
        priors = rule_priors(store)
        assert len(priors) == 1
        assert priors[0].rule_id == "RC-CORRIDOR-WIDTH"


def test_beta_binomial_posterior_math(tmp_path: Path) -> None:
    db, issue_ids = _seed_for_feedback(tmp_path)
    with KGStore(db, create=False) as store:
        add_feedback(store, issue_id=issue_ids[0], reviewer_id="r", event_type="confirm")
        add_feedback(store, issue_id=issue_ids[1], reviewer_id="r", event_type="confirm")
        add_feedback(store, issue_id=issue_ids[2], reviewer_id="r", event_type="reject")
        priors = rule_priors(store)
        p = priors[0]
        assert p.confirmed == 2
        assert p.rejected == 1
        # alpha = 1 + 2 = 3; beta = 1 + 1 = 2; mean = 3/5 = 0.6
        assert p.posterior_alpha == pytest.approx(PRIOR_ALPHA + 2)
        assert p.posterior_beta == pytest.approx(PRIOR_BETA + 1)
        assert p.posterior_mean == pytest.approx(0.6)


def test_feedback_loop_synthetic_test_is_monotonic_and_predictable() -> None:
    result = feedback_loop_synthetic_test()
    assert result["monotonic"] is True
    # Prior Beta(1,1) mean=0.5; final after 3 rejects + 1 confirm → 2/6 ≈ 0.333
    assert result["final_posterior_mean"] == pytest.approx(2 / 6, abs=1e-6)
    assert result["expected_delta"] == pytest.approx(2 / 6 - 0.5, abs=1e-6)
    assert result["delta"] == pytest.approx(result["expected_delta"], abs=1e-6)


def test_calibration_no_db_returns_zero_status(tmp_path: Path) -> None:
    rep = build_calibration_report(tmp_path / "missing.db")
    assert rep["status"] == "no_kg_db"
    assert rep["bins"] == []
    assert rep["mean_abs_deviation"] is None


def test_calibration_no_feedback_returns_no_bin_status(tmp_path: Path) -> None:
    db = tmp_path / "kg.db"
    KGStore(db).close()
    rep = build_calibration_report(db)
    # Status is no_bin_with_enough_samples (empty KG, no bins reach min samples)
    assert rep["status"] == "no_bin_with_enough_samples"
    assert rep["mean_abs_deviation"] is None


def test_calibration_perfectly_calibrated_bin(tmp_path: Path) -> None:
    """Seed 20 issues all at confidence=0.9 and observe that 18/20 confirm
    yields observed precision = 0.9, matching midpoint 0.9005 → MAD ≈ 0."""

    db = tmp_path / "kg.db"
    with KGStore(db) as store:
        proj = store.upsert_project("calib")
        draw = store.upsert_drawing(project_id=proj, source_path="c.pdf")
        run = store.upsert_run(project_id=proj, drawing_id=draw, run_dir="r")
        with store._conn:
            cur = store._conn.execute(
                "INSERT INTO rule(rule_id, version) VALUES (?, ?)", ("RC-X", "1")
            )
            rule_id = int(cur.lastrowid or 0)
        issue_ids = []
        for i in range(20):
            with store._conn:
                cur = store._conn.execute(
                    "INSERT INTO issue(run_id, rule_id, source_issue_id, severity, confidence) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (run, rule_id, f"X-{i}", "error", 0.9),
                )
                issue_ids.append(int(cur.lastrowid or 0))
        for i, iid in enumerate(issue_ids):
            ev = "confirm" if i < 18 else "reject"
            add_feedback(store, issue_id=iid, reviewer_id="r", event_type=ev)

    rep = build_calibration_report(db)
    assert rep["status"] == "ok"
    target_bin = next(b for b in rep["bins"] if b["lower"] == 0.8)
    assert target_bin["sample_size"] == 20
    assert target_bin["observed_precision"] == pytest.approx(0.9)
    # midpoint of (0.8, 1.0) clipped to 1.0 ≈ 0.9; obs ≈ 0.9; abs_dev ≈ 0
    assert target_bin["abs_deviation"] < 0.05
    assert rep["mean_abs_deviation"] < 0.05


def test_calibration_miscalibrated_bin(tmp_path: Path) -> None:
    """Detector confident at 0.9 but actually correct only 30% of the time
    → large abs_dev."""

    db = tmp_path / "kg.db"
    with KGStore(db) as store:
        proj = store.upsert_project("calib")
        draw = store.upsert_drawing(project_id=proj, source_path="c.pdf")
        run = store.upsert_run(project_id=proj, drawing_id=draw, run_dir="r")
        with store._conn:
            cur = store._conn.execute(
                "INSERT INTO rule(rule_id, version) VALUES (?, ?)", ("RC-X", "1")
            )
            rule_id = int(cur.lastrowid or 0)
        issue_ids = []
        for i in range(20):
            with store._conn:
                cur = store._conn.execute(
                    "INSERT INTO issue(run_id, rule_id, source_issue_id, severity, confidence) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (run, rule_id, f"X-{i}", "error", 0.9),
                )
                issue_ids.append(int(cur.lastrowid or 0))
        for i, iid in enumerate(issue_ids):
            ev = "confirm" if i < 6 else "reject"  # 30% precision
            add_feedback(store, issue_id=iid, reviewer_id="r", event_type=ev)

    rep = build_calibration_report(db)
    assert rep["status"] == "ok"
    target_bin = next(b for b in rep["bins"] if b["lower"] == 0.8)
    assert target_bin["observed_precision"] == pytest.approx(0.3)
    # midpoint ≈ 0.9; obs = 0.3; abs_dev ≈ 0.6
    assert target_bin["abs_deviation"] > 0.5
    assert rep["mean_abs_deviation"] > 0.5


def test_upsert_reviewer_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "kg.db"
    with KGStore(db) as store:
        r1 = upsert_reviewer(store, "alice", "Alice Engineer")
        r2 = upsert_reviewer(store, "alice", "Alice Engineer 2")
        assert r1 == r2
        cur = store._conn.execute("SELECT display_name FROM reviewer WHERE id = ?", (r1,))
        assert cur.fetchone()["display_name"] == "Alice Engineer 2"


def test_default_bins_cover_zero_to_one() -> None:
    assert DEFAULT_BINS[0][0] == 0.0
    assert DEFAULT_BINS[-1][1] >= 1.0


def test_calibration_bin_dataclass_to_dict() -> None:
    cb = CalibrationBin(
        lower=0.0,
        upper=0.2,
        midpoint=0.1,
        sample_size=10,
        confirmed=8,
        rejected=2,
        observed_precision=0.8,
        abs_deviation=0.7,
    )
    d = cb.to_dict()
    assert d["sample_size"] == 10
    assert d["abs_deviation"] == 0.7
