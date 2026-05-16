"""Tests for archkg.kg.calibrator (M5.I.2 — Beta-posterior calibrator)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from archkg.kg import (
    KGStore,
    add_feedback,
    build_calibration_report,
    calibrate_db,
    calibrate_issue_confidence,
    ingest_run,
)


def _seed(tmp_path: Path) -> tuple[Path, list[int]]:
    db = tmp_path / "kg.db"
    run_dir = tmp_path / "demo_run"
    run_dir.mkdir()
    issues = [
        {
            "issue_id": f"X-{i}",
            "rule_card_id": "RC-X",
            "standard_clause_id": "S-1.1",
            "entity_ids": [],
            "page_index": 0,
            "severity": "error",
            "message": f"x{i}",
        }
        for i in range(10)
    ]
    (run_dir / "issues.json").write_text(json.dumps(issues), encoding="utf-8")
    with KGStore(db) as store:
        ingest_run(store, run_dir=run_dir, project_slug="demo")
        rows = store._conn.execute("SELECT id FROM issue ORDER BY id").fetchall()
        ids = [int(r["id"]) for r in rows]
    return db, ids


def test_calibrate_with_no_feedback_returns_empty(tmp_path: Path) -> None:
    db, _ = _seed(tmp_path)
    with KGStore(db, create=False) as store:
        results = calibrate_issue_confidence(store)
    assert results == []


def test_calibrate_applies_posterior_mean_to_issues(tmp_path: Path) -> None:
    db, ids = _seed(tmp_path)
    # 7 confirm + 3 reject → Beta(1+7, 1+3) = Beta(8, 4), mean = 8/12 ≈ 0.667
    with KGStore(db, create=False) as store:
        for i in range(7):
            add_feedback(store, issue_id=ids[i], reviewer_id="r", event_type="confirm")
        for i in range(7, 10):
            add_feedback(store, issue_id=ids[i], reviewer_id="r", event_type="reject")
        results = calibrate_issue_confidence(store)
    assert len(results) == 1
    r = results[0]
    assert r.rule_id == "RC-X"
    assert r.posterior_mean == pytest.approx(8 / 12, abs=1e-6)
    assert r.issues_updated == 10
    # Verify the issues got the new confidence
    with KGStore(db, create=False) as store:
        rows = store._conn.execute("SELECT confidence FROM issue").fetchall()
        for row in rows:
            assert float(row["confidence"]) == pytest.approx(8 / 12, abs=1e-6)


def test_dry_run_does_not_mutate(tmp_path: Path) -> None:
    db, ids = _seed(tmp_path)
    with KGStore(db, create=False) as store:
        for i in range(5):
            add_feedback(store, issue_id=ids[i], reviewer_id="r", event_type="confirm")
        # Set a sentinel confidence first
        store._conn.execute("UPDATE issue SET confidence = 0.123")
        results = calibrate_issue_confidence(store, dry_run=True)
        assert len(results) == 1
        # issues_updated should reflect what WOULD be touched
        assert results[0].issues_updated == 10
        # But the actual confidence column is unchanged
        rows = store._conn.execute("SELECT confidence FROM issue").fetchall()
        for row in rows:
            assert float(row["confidence"]) == 0.123


def test_calibration_mad_drops_after_calibration(tmp_path: Path) -> None:
    """Acceptance test: calibration MAD <= 8% after applying calibrator.

    This validates the M5.I.2 contract: after calibration, each rule's
    posterior_mean equals observed precision; binning by calibrated confidence
    should yield observed_precision ≈ midpoint per bin.
    """
    db = tmp_path / "kg.db"
    with KGStore(db) as store:
        # Three rules with different observed precisions across different bins
        proj = store.upsert_project("calib-test")
        draw = store.upsert_drawing(project_id=proj, source_path="t.pdf")
        run = store.upsert_run(project_id=proj, drawing_id=draw, run_dir="r")
        rule_ids: dict[str, int] = {}
        for rid in ("RC-LOW", "RC-MID", "RC-HIGH"):
            cur = store._conn.execute(
                "INSERT INTO rule(rule_id, version) VALUES (?, ?)", (rid, "1")
            )
            rule_ids[rid] = int(cur.lastrowid or 0)
        # Seed 20 issues per rule, with reviewer outcomes matching:
        # RC-LOW   -> 20% confirm  (true precision 0.2; lands in 0.0-0.2 bin)
        # RC-MID   -> 50% confirm  (lands in 0.4-0.6 bin)
        # RC-HIGH  -> 90% confirm  (lands in 0.8-1.0 bin)
        plan = (
            ("RC-LOW", 4),  # 4 out of 20 confirm
            ("RC-MID", 10),
            ("RC-HIGH", 18),
        )
        for rid, n_conf in plan:
            for i in range(20):
                cur = store._conn.execute(
                    "INSERT INTO issue(run_id, rule_id, source_issue_id, severity) "
                    "VALUES (?, ?, ?, ?)",
                    (run, rule_ids[rid], f"{rid}-{i}", "error"),
                )
                iid = int(cur.lastrowid or 0)
                event = "confirm" if i < n_conf else "reject"
                add_feedback(store, issue_id=iid, reviewer_id="r", event_type=event)
    # Before calibration: every issue has confidence None → no bins measurable
    rep_before = build_calibration_report(db)
    # Apply calibration
    summary = calibrate_db(db)
    assert summary["rules_calibrated"] == 3
    assert summary["issues_updated"] == 60
    # After calibration: each rule's issues have confidence = posterior_mean,
    # which equals observed precision (plus Beta(1,1) prior adjustment)
    rep_after = build_calibration_report(db)
    assert rep_after["status"] == "ok"
    mad = rep_after["mean_abs_deviation"]
    # Posterior means: RC-LOW=5/22≈0.227, RC-MID=11/22=0.5, RC-HIGH=19/22≈0.864
    # These land in bins (0.2-0.4), (0.4-0.6), (0.8-1.0) with midpoints
    # 0.30, 0.50, 0.90. Observed precision per bin matches confirm rate:
    # 0.20, 0.50, 0.90. Bin-vs-observed deviations: ~0.10, 0, 0.
    # MAD over 3 bins should be well under 8%.
    assert rep_after["bins_used_for_mad"] >= 3
    assert mad < 0.10, f"MAD {mad} should drop after calibration; before was {rep_before.get('mean_abs_deviation')}"


def test_calibrate_db_summary_shape(tmp_path: Path) -> None:
    db, ids = _seed(tmp_path)
    with KGStore(db, create=False) as store:
        for i in range(3):
            add_feedback(store, issue_id=ids[i], reviewer_id="r", event_type="confirm")
    summary = calibrate_db(db)
    assert summary["db_path"] == str(db)
    assert summary["dry_run"] is False
    assert summary["rules_calibrated"] == 1
    assert summary["issues_updated"] == 10
    assert len(summary["results"]) == 1
