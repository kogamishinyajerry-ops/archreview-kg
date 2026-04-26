"""Tests for the adversarial-battery adjudicator (Phase 18-D)."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from archkg.adversarial.adjudicator import (
    CaseScore,
    aggregate,
    render_scoreboard_json,
    render_scoreboard_md,
    score_case,
)


def _fake_case(
    tmp_path: Path,
    case_id: str,
    expected: list[str],
    actual: list[str],
) -> tuple[Path, Path]:
    case_dir = tmp_path / case_id
    case_dir.mkdir()
    review_dir = case_dir / "review-out"
    review_dir.mkdir()
    yaml_payload = {
        "case_id": case_id,
        "expected_violations": [{"rule_id": r, "entity_hint": "x", "note": ""} for r in expected],
    }
    (case_dir / "ground_truth.yaml").write_text(
        yaml.safe_dump(yaml_payload, sort_keys=False),
        encoding="utf-8",
    )
    (review_dir / "issues.json").write_text(
        json.dumps(
            [
                {
                    "issue_id": f"ISS-{i}",
                    "rule_card_id": r,
                    "standard_clause_id": "GB",
                    "entity_ids": ["e"],
                    "bbox": None,
                    "page_index": 0,
                    "severity": "error",
                    "message": "",
                    "evidence": {
                        "snippet": "",
                        "page_index": 0,
                        "measured_value": None,
                        "threshold_value": None,
                        "unit": None,
                    },
                }
                for i, r in enumerate(actual)
            ]
        ),
        encoding="utf-8",
    )
    return case_dir, review_dir


def test_score_case_perfect_match(tmp_path: Path) -> None:
    case_dir, review_dir = _fake_case(
        tmp_path,
        "case-1",
        expected=["RC-CORRIDOR-WIDTH", "RC-DOOR-WIDTH"],
        actual=["RC-CORRIDOR-WIDTH", "RC-DOOR-WIDTH"],
    )
    s = score_case(case_dir, review_dir)
    assert s.true_positives == {"RC-CORRIDOR-WIDTH", "RC-DOOR-WIDTH"}
    assert s.false_negatives == set()
    assert s.false_positives == set()


def test_score_case_records_false_negative(tmp_path: Path) -> None:
    case_dir, review_dir = _fake_case(
        tmp_path,
        "case-1",
        expected=["RC-CORRIDOR-WIDTH", "RC-DOOR-WIDTH"],
        actual=["RC-DOOR-WIDTH"],
    )
    s = score_case(case_dir, review_dir)
    assert s.false_negatives == {"RC-CORRIDOR-WIDTH"}


def test_score_case_records_false_positive(tmp_path: Path) -> None:
    case_dir, review_dir = _fake_case(
        tmp_path,
        "case-1",
        expected=["RC-CORRIDOR-WIDTH"],
        actual=["RC-CORRIDOR-WIDTH", "RC-BEDROOM-AREA"],
    )
    s = score_case(case_dir, review_dir)
    assert s.false_positives == {"RC-BEDROOM-AREA"}


def test_score_case_filters_info_reminders(tmp_path: Path) -> None:
    """Info-level reminder rules (always-fire reminders) must not register
    as false positives — they're surface-the-clause noise, not auto-judgement."""
    case_dir, review_dir = _fake_case(
        tmp_path,
        "case-1",
        expected=["RC-CORRIDOR-WIDTH"],
        # RC-RAILING-HEIGHT-6.7.3 is severity=info project reminder.
        actual=["RC-CORRIDOR-WIDTH", "RC-RAILING-HEIGHT-6.7.3"],
    )
    s = score_case(case_dir, review_dir)
    assert s.false_positives == set(), (
        "info-level reminder should not count as false positive"
    )


def test_score_case_keeps_expected_info_rule_for_fn_accounting(tmp_path: Path) -> None:
    """Codex P18-D R1 P3: the examiner expects severity=info stair rules
    (RC-STAIR-FLIGHT-WIDTH-1.10 / RC-STAIR-WELL-WIDTH-0.11). When the
    candidate misses them, that must still be a false negative — the
    info-rule filter must NOT strip them from the actual side just
    because they're tagged info."""
    case_dir, review_dir = _fake_case(
        tmp_path,
        "case-1",
        expected=["RC-STAIR-FLIGHT-WIDTH-1.10"],  # info-level stair rule
        actual=[],  # candidate didn't fire it
    )
    s = score_case(case_dir, review_dir)
    assert s.false_negatives == {"RC-STAIR-FLIGHT-WIDTH-1.10"}


def test_score_case_expected_info_rule_when_actual_fires_counts_as_tp(tmp_path: Path) -> None:
    """And when an expected info rule does fire, it counts as a true positive
    (not silently filtered)."""
    case_dir, review_dir = _fake_case(
        tmp_path,
        "case-1",
        expected=["RC-STAIR-WELL-WIDTH-0.11"],  # info-level
        actual=["RC-STAIR-WELL-WIDTH-0.11"],
    )
    s = score_case(case_dir, review_dir)
    assert s.true_positives == {"RC-STAIR-WELL-WIDTH-0.11"}
    assert s.false_negatives == set()
    assert s.false_positives == set()


def test_aggregate_sums_per_rule_counts() -> None:
    s1 = CaseScore(
        case_id="c1",
        expected_rule_ids={"RC-A", "RC-B"},
        actual_rule_ids={"RC-A", "RC-B"},
        true_positives={"RC-A", "RC-B"},
    )
    s2 = CaseScore(
        case_id="c2",
        expected_rule_ids={"RC-A"},
        actual_rule_ids=set(),
        false_negatives={"RC-A"},
    )
    s3 = CaseScore(
        case_id="c3",
        expected_rule_ids=set(),
        actual_rule_ids={"RC-C"},
        false_positives={"RC-C"},
    )

    agg = aggregate([s1, s2, s3])
    assert agg.rule_scores["RC-A"].tp == 1
    assert agg.rule_scores["RC-A"].fn == 1
    assert agg.rule_scores["RC-A"].recall == 0.5
    assert agg.rule_scores["RC-B"].tp == 1
    assert agg.rule_scores["RC-B"].recall == 1.0
    assert agg.rule_scores["RC-C"].fp == 1
    assert agg.rule_scores["RC-C"].precision == 0.0


def test_render_scoreboard_md_contains_per_rule_section(tmp_path: Path) -> None:
    score = aggregate([
        CaseScore(
            case_id="c1",
            expected_rule_ids={"RC-A"},
            actual_rule_ids={"RC-A"},
            true_positives={"RC-A"},
        )
    ])
    out = render_scoreboard_md(score, tmp_path / "scoreboard.md")
    text = out.read_text(encoding="utf-8")
    assert "Per-rule" in text
    assert "RC-A" in text
    assert "Per-case" in text


def test_render_scoreboard_json_round_trips(tmp_path: Path) -> None:
    score = aggregate([
        CaseScore(
            case_id="c1",
            expected_rule_ids={"RC-A", "RC-B"},
            actual_rule_ids={"RC-A"},
            true_positives={"RC-A"},
            false_negatives={"RC-B"},
        )
    ])
    out = render_scoreboard_json(score, tmp_path / "scoreboard.json")
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["total_cases"] == 1
    assert payload["per_rule"]["RC-A"]["tp"] == 1
    assert payload["per_rule"]["RC-B"]["fn"] == 1
