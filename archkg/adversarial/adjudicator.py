"""Adjudicator: score candidate's issues.json against examiner's ground_truth.

For each rule_id, compute precision/recall/F1 across the battery — this
is the per-rule quality signal that drives where to invest next.

Per-case scoring rule (deliberately set-based, not multiplicity-aware):
- TP: rule_id appears in both expected and actual
- FN: rule_id in expected only (candidate missed it)
- FP: rule_id in actual only AND not an info-reminder. Info-level rules
       are intentional always-fire reminder surfaces — counting them as
       FP every time would drown the signal. Note: if the examiner
       explicitly *expects* an info-level rule (Phase 18-D's stair-flight
       and stair-well rules are severity=info but examiners include them
       in ground truth), they are kept on the actual side too so
       missing them counts as an honest FN.

Multiplicity is set aside on purpose: a rule like RC-DOOR-WIDTH with 3
expected fires + 4 actual fires registers as TP=1 here. If we want
per-instance accuracy we need entity_hint matching, which means
agreement on entity ids between examiner and candidate. That's a
follow-up; today's signal is "did the candidate notice this rule on
this case at all?".
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from archkg.knowledge.loader import load_rules


@dataclass
class CaseScore:
    case_id: str
    expected_rule_ids: set[str]
    actual_rule_ids: set[str]
    true_positives: set[str] = field(default_factory=set)
    false_negatives: set[str] = field(default_factory=set)
    false_positives: set[str] = field(default_factory=set)


@dataclass
class RuleAggregateScore:
    rule_id: str
    tp: int = 0
    fn: int = 0
    fp: int = 0

    @property
    def precision(self) -> float | None:
        denom = self.tp + self.fp
        return None if denom == 0 else self.tp / denom

    @property
    def recall(self) -> float | None:
        denom = self.tp + self.fn
        return None if denom == 0 else self.tp / denom

    @property
    def f1(self) -> float | None:
        p, r = self.precision, self.recall
        if p is None or r is None or (p + r) == 0:
            return None
        return 2 * p * r / (p + r)


@dataclass
class BatteryScore:
    case_scores: list[CaseScore] = field(default_factory=list)
    rule_scores: dict[str, RuleAggregateScore] = field(default_factory=dict)

    @property
    def total_cases(self) -> int:
        return len(self.case_scores)

    def overall(self) -> RuleAggregateScore:
        agg = RuleAggregateScore(rule_id="(overall)")
        for r in self.rule_scores.values():
            agg.tp += r.tp
            agg.fn += r.fn
            agg.fp += r.fp
        return agg


def _load_ground_truth_rule_ids(case_dir: Path) -> set[str]:
    payload = yaml.safe_load((case_dir / "ground_truth.yaml").read_text(encoding="utf-8"))
    return {v["rule_id"] for v in payload.get("expected_violations", [])}


def _load_actual_rule_ids(review_out_dir: Path) -> set[str]:
    issues = json.loads((review_out_dir / "issues.json").read_text(encoding="utf-8"))
    return {i["rule_card_id"] for i in issues}


def _info_rule_ids() -> set[str]:
    """Rule ids whose effective severity is 'info'.

    These are the always-fire reminder cards. Counting them as FP would
    drown the signal — they're meant as a manual-check surface, not as
    auto-judgement. We strip them from `actual` before scoring UNLESS
    they appear in the expected set (Phase 18-D's stair_flight_width and
    stair_well_width rules are severity=info but the examiner includes
    them in ground truth — keeping them in actual when expected lets
    missing them count as a real FN).
    """
    info_ids: set[str] = set()
    for rule in load_rules():
        sev = rule.severity
        if sev == "info":
            info_ids.add(rule.id)
            continue
        if sev is None and rule.applies_to == "Project":
            info_ids.add(rule.id)
    return info_ids


def score_case(case_dir: Path, review_out_dir: Path) -> CaseScore:
    expected = _load_ground_truth_rule_ids(case_dir)
    actual_all = _load_actual_rule_ids(review_out_dir)
    info = _info_rule_ids()

    # Strip info reminders from actuals UNLESS they're explicitly expected
    # — the examiner DOES expect a few severity=info rules (the
    # stair_flight / stair_well rules are tagged info but ground truth
    # includes them when the schedule trips them), so we keep any rule
    # that appears in expected even if it's also in info.
    actual = {r for r in actual_all if r not in info or r in expected}

    tp = expected & actual
    fn = expected - actual
    fp = actual - expected

    return CaseScore(
        case_id=case_dir.name,
        expected_rule_ids=expected,
        actual_rule_ids=actual,
        true_positives=tp,
        false_negatives=fn,
        false_positives=fp,
    )


def aggregate(scores: list[CaseScore]) -> BatteryScore:
    rule_scores: dict[str, RuleAggregateScore] = defaultdict(
        lambda: RuleAggregateScore(rule_id="?")
    )

    for s in scores:
        for rid in s.true_positives:
            ag = rule_scores[rid]
            ag.rule_id = rid
            ag.tp += 1
        for rid in s.false_negatives:
            ag = rule_scores[rid]
            ag.rule_id = rid
            ag.fn += 1
        for rid in s.false_positives:
            ag = rule_scores[rid]
            ag.rule_id = rid
            ag.fp += 1

    return BatteryScore(case_scores=scores, rule_scores=dict(rule_scores))


def render_scoreboard_md(battery: BatteryScore, out_path: Path) -> Path:
    """Per-rule precision/recall/F1 + per-case verdict, ready to skim."""
    lines: list[str] = []
    lines.append("# Adversarial Battery Scoreboard\n")
    lines.append(f"Total cases: **{battery.total_cases}**\n")

    overall = battery.overall()
    lines.append(
        f"Overall: TP={overall.tp} FN={overall.fn} FP={overall.fp} "
        f"| precision={_fmt(overall.precision)} recall={_fmt(overall.recall)} "
        f"F1={_fmt(overall.f1)}\n"
    )

    lines.append("\n## Per-rule\n")
    lines.append("| rule_id | TP | FN | FP | precision | recall | F1 |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    for rid in sorted(battery.rule_scores):
        r = battery.rule_scores[rid]
        lines.append(
            f"| {rid} | {r.tp} | {r.fn} | {r.fp} | "
            f"{_fmt(r.precision)} | {_fmt(r.recall)} | {_fmt(r.f1)} |"
        )

    lines.append("\n## Per-case\n")
    lines.append("| case | TP | FN | FP | failures (rule ids) |")
    lines.append("|---|---:|---:|---:|---|")
    for cs in battery.case_scores:
        failures = sorted(cs.false_negatives | cs.false_positives)
        lines.append(
            f"| {cs.case_id} | {len(cs.true_positives)} | "
            f"{len(cs.false_negatives)} | {len(cs.false_positives)} | "
            f"{', '.join(failures) if failures else '—'} |"
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def _fmt(v: float | None) -> str:
    return "—" if v is None else f"{v:.2f}"


def render_scoreboard_json(battery: BatteryScore, out_path: Path) -> Path:
    """Machine-readable scoreboard for downstream tooling."""
    payload: dict[str, Any] = {
        "total_cases": battery.total_cases,
        "overall": _agg_to_dict(battery.overall()),
        "per_rule": {rid: _agg_to_dict(r) for rid, r in battery.rule_scores.items()},
        "per_case": [
            {
                "case_id": cs.case_id,
                "expected_rule_ids": sorted(cs.expected_rule_ids),
                "actual_rule_ids": sorted(cs.actual_rule_ids),
                "true_positives": sorted(cs.true_positives),
                "false_negatives": sorted(cs.false_negatives),
                "false_positives": sorted(cs.false_positives),
            }
            for cs in battery.case_scores
        ],
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return out_path


def _agg_to_dict(r: RuleAggregateScore) -> dict[str, Any]:
    return {
        "rule_id": r.rule_id,
        "tp": r.tp,
        "fn": r.fn,
        "fp": r.fp,
        "precision": r.precision,
        "recall": r.recall,
        "f1": r.f1,
    }
