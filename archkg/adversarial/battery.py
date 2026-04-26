"""Run a battery of adversarial cases end-to-end.

Pipeline per case:
  1. examiner.generate_case(seed) → plan.pdf + meta + schedules + ground_truth
  2. archkg review (in-process) → issues.json
  3. adjudicator.score_case → CaseScore

Aggregate → scoreboard.md / scoreboard.json under the battery dir.

The runner deliberately calls archkg's review machinery in-process
(not via subprocess) so this module is unit-testable without spawning
processes per case.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import yaml

from archkg.adversarial.adjudicator import (
    BatteryScore,
    aggregate,
    render_scoreboard_json,
    render_scoreboard_md,
    score_case,
)
from archkg.adversarial.examiner import GeneratedCase, generate_case
from archkg.graph.builder import build_graph
from archkg.graph.schedule import apply_room_schedule
from archkg.graph.stair_schedule import apply_stair_schedule
from archkg.ingest.primitive_extractor import extract
from archkg.knowledge.loader import load_rules, load_standards
from archkg.knowledge.room_schedule import load_room_schedule
from archkg.knowledge.stair_schedule import load_stair_schedule
from archkg.rules.engine import evaluate
from archkg.schemas import ProjectMeta


@dataclass
class BatteryRunSummary:
    out_dir: Path
    cases: list[GeneratedCase]
    score: BatteryScore


def _review_case(case: GeneratedCase) -> Path:
    """In-process equivalent of `archkg review`. Writes issues.json into
    case_dir/review-out/ and returns that directory."""
    review_dir = case.case_dir / "review-out"
    review_dir.mkdir(parents=True, exist_ok=True)

    primitives = extract(case.pdf_path, points_per_meter=50.0)
    graph = build_graph(primitives)

    meta_payload = yaml.safe_load(case.project_meta_path.read_text(encoding="utf-8"))
    meta = ProjectMeta.model_validate(meta_payload)

    room_sched = load_room_schedule(case.room_schedule_path)
    graph = apply_room_schedule(graph, room_sched).graph

    if case.stair_schedule_path is not None:
        stair_sched = load_stair_schedule(case.stair_schedule_path)
        graph = apply_stair_schedule(graph, stair_sched).graph

    standards = load_standards()
    rules = load_rules(standards=standards)
    result = evaluate(graph, rules, standards, project_meta=meta)

    (review_dir / "issues.json").write_text(
        json.dumps(
            [i.model_dump() for i in result.issues],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return review_dir


def run_battery(
    n: int,
    seed_start: int,
    out_dir: Path,
) -> BatteryRunSummary:
    """Generate `n` cases starting from `seed_start`, run each through the
    candidate, score, and write scoreboard artifacts.

    Cases live under `{out_dir}/case-NNNNNN/` with their per-case review
    output under `case-NNNNNN/review-out/`. Aggregate scoreboard lives
    in `{out_dir}/scoreboard.{md,json}`."""
    out_dir.mkdir(parents=True, exist_ok=True)
    cases: list[GeneratedCase] = []
    case_scores = []

    for i in range(n):
        seed = seed_start + i
        case = generate_case(seed=seed, out_dir=out_dir)
        cases.append(case)
        review_dir = _review_case(case)
        case_scores.append(score_case(case.case_dir, review_dir))

    score = aggregate(case_scores)
    render_scoreboard_md(score, out_dir / "scoreboard.md")
    render_scoreboard_json(score, out_dir / "scoreboard.json")
    return BatteryRunSummary(out_dir=out_dir, cases=cases, score=score)
