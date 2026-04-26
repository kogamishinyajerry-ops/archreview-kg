"""End-to-end smoke test for the adversarial battery (Phase 18-D)."""

from __future__ import annotations

import json
from pathlib import Path

from archkg.adversarial.battery import run_battery


def test_run_battery_smoke(tmp_path: Path) -> None:
    """One case end-to-end: examiner generates → candidate reviews →
    adjudicator scores. We don't assert specific recall numbers because
    they're a moving target as the builder evolves; we assert the
    pipeline produced the expected artifacts and the scoreboard
    contains data."""
    summary = run_battery(n=2, seed_start=12345, out_dir=tmp_path / "battery")

    assert summary.score.total_cases == 2
    assert (summary.out_dir / "scoreboard.md").exists()
    assert (summary.out_dir / "scoreboard.json").exists()

    # Each case has a review-out dir with issues.json.
    for case in summary.cases:
        review_dir = case.case_dir / "review-out"
        assert (review_dir / "issues.json").exists()
        # Issues file is valid JSON.
        json.loads((review_dir / "issues.json").read_text())

    # Scoreboard json has per-rule entries.
    payload = json.loads((summary.out_dir / "scoreboard.json").read_text())
    assert payload["total_cases"] == 2
    assert "per_rule" in payload
    assert "per_case" in payload
    assert len(payload["per_case"]) == 2


def test_run_battery_seeds_are_consecutive(tmp_path: Path) -> None:
    """case k uses seed_start + k. Sanity check so future battery
    aggregation can rely on the contract."""
    summary = run_battery(n=3, seed_start=1000, out_dir=tmp_path / "battery")
    seeds = [c.parameters.seed for c in summary.cases]
    assert seeds == [1000, 1001, 1002]
