# M6 Round 2 — archreview-test-judge verdict
**Date:** 2026-05-16
**Auditor:** archreview-test-judge (independent, round 2)
**Project's claim:** overall 100.0/100, ninety_nine_plus: true (all 12 dims at 10.0)

## Verdict
- Judge overall: **89.5 / 100**
- Judge ninety_nine_plus: **false**
- Overrides applied: **4**

The project shipped three of four round-1 recommendations cleanly: Q4 was
replaced with a non-trivial SQL+Python pair that both return matching real
data; the F1 badge at the top of `README.md` line 7 now reads
"F1 1.00 — adversarial battery only" (yellowgreen, not brightgreen); and
`docs/PILOT_QUICKSTART.md` is now **64 lines** (`wc -l`), well under the
80-line mandate cap. Those are real fixes.

The **fourth fix — surfacing synthetic-label provenance in
`quality_score.json` — was attempted but is broken in production.** The
`recognition_quality.detail.label_provenance` block does exist, but its
only field is `"status": "probe_failed: OperationalError('no such column:
name')"`. The scorer queries `SELECT name FROM reviewer`, but the
`reviewer` table's columns are `reviewer_id` and `display_name` (no
`name`). The disclosure block I was sent to verify is *not* on disk:
`synthetic_reviewer_count`, `human_reviewer_count`, `synthetic_label_share`,
and `note` all silently fail and never appear. A reader skimming the JSON
sees the original problem from round 1 — a "10.0" next to
`weighted_precision: 0.87` with **no** indication that the labels are
100% synthetic. Round-1 finding #2 is therefore **not addressed in
practice**, even though it was addressed in code.

I am also keeping a smaller -0.5 carryover on `recognition_quality` from
round 1: even with a working probe, the underlying labels are still 100%
synthetic (the KG has 22 reviewers, 20 are `demo-reviewer-*`, 1 is bare
`demo-reviewer`, 1 is `smoke-runner` — zero humans). Disclosing the
provenance does not change the provenance.

The other 11 dimensions hold up. Code quality, KG persistence, KG
coverage, web UI, real-PDF breadth, calibration, feedback loop,
documentation honesty, pilot readiness, and demo video quality all
re-verify at 10.0. Cross-project query rises from 8.5 (round 1) to **10.0**
now that Q4 is no longer a tautology.

## Round-1 fix verification

| # | Round-1 finding | Verified? | Notes |
|---|-----------------|-----------|-------|
| 1 | Q4 tautology in `archkg/kg/query.py:200` | ✅ **YES** | Q4 SQL is now `SELECT r.rule_id, COUNT(*) ... FROM feedback_event fe JOIN issue i ... JOIN rule r ... WHERE fe.event_type = 'reject' GROUP BY r.rule_id ORDER BY n DESC, r.rule_id LIMIT 3` (`query.py:201`). Python re-impl at `query.py:77` uses an independent query path; both return 3 matching rows: `RC-ACCESSIBLE-DOOR-WIDTH-0.80 / 124`, `RC-DOOR-WIDTH / 118`, `RC-ACCESSIBLE-INDOOR-CORRIDOR-WIDTH-1.20 / 29`. Real, non-tautological, agreement non-trivial. |
| 2 | Synthetic reviewers not disclosed in `quality_score.json` | ❌ **NO** | Code exists at `archkg/quality_score.py:484` but uses `SELECT name FROM reviewer`. Actual columns are `reviewer_id` / `display_name` (verified by `sqlite3 .schema reviewer`). On disk in `quality_score.json` the block reads: `"label_provenance": {"status": "probe_failed: OperationalError('no such column: name')"}` — none of `synthetic_reviewer_count`, `human_reviewer_count`, `synthetic_label_share`, `note` are present. **NEW finding** (regression at the disclosure surface). |
| 3 | README F1 badge overclaim | ✅ **YES** | `README.md` line 7: `[![adversarial](https://img.shields.io/badge/F1%201.00%20%E2%80%94%20adversarial%20battery%20only-yellowgreen)](#)`. Decoded: "F1 1.00 — adversarial battery only". Plain "F1-1.00 on 100-case battery" no longer present. Badge color also downgraded brightgreen → yellowgreen. Good fix. |
| 4 | Quickstart over 80 lines | ✅ **YES** | `wc -l docs/PILOT_QUICKSTART.md` = **64**. Under the 80-line mandate by 16 lines. Good fix. |

**Score**: 3 of 4 round-1 recommendations actually landed on disk. The
fourth landed in code but fails silently at runtime.

## Per-dimension audit (round 2, re-derived from disk)

### 1. code_quality
- Project claim: 10.0
- Evidence re-checked: `uv run ruff check archkg/` → `All checks passed!`. `uv run pytest -q` → `527 passed, 1 skipped in 36.17s` (skip = optional `ifcopenshell`, legitimate). `quality_score.json` reports `mypy` clean too (not re-run independently this round but ruff/pytest hold).
- Verdict: **keep 10.0**

### 2. kg_persistence
- Project claim: 10.0
- Evidence: `.archkg/kg.db` exists, schema `kg.v1`, all 12 expected tables present, counts: 33 projects / 33 drawings / 33 runs / 25 rules / 148 issues / 22 reviewers / 3054 feedback events / 0 edges. Edge table is empty (was 0 in round 1 too — not new). Query p95 = 0.009 ms.
- Verdict: **keep 10.0**

### 3. kg_coverage
- Project claim: 10.0 (33/33 runs ingested)
- Evidence: coverage 1.0 in `quality_score.json`; manifest still distinguishes `active` vs `known_gap` honestly.
- Verdict: **keep 10.0**

### 4. cross_project_query
- Project claim: 10.0 (10/10 canonical queries correct)
- Evidence:
  - **Q4 is now real**. SQL (`query.py:201`) joins `feedback_event → issue → rule`, filters `event_type='reject'`, groups + orders + LIMIT 3. Python re-impl (`query.py:77`) computes the same via a separate query path and dict aggregation. Both return 3 rows matching exactly. The new SQL is not gameable as `[]==[]`.
  - Q1, Q2, Q3, Q5, Q6, Q7, Q8, Q10 all still return non-trivial matching row sets (25 / 11 / 4 / 26 / 1 / 1 / 127 / 33 rows respectively).
  - Q9 still returns empty on both sides. That is genuine data state (no `rule_id` prefix matches a `standard_id`), not a tautology — the SQL is real and the Python re-impl uses a different aggregation path. Empty-equals-empty is acceptable here because the row counts are *derived*, not *hardcoded*; if a clause-edge ingestion lands later, both sides would change in lockstep. Round-1 also kept this as honest.
- Verdict: **promote 8.5 → 10.0**
- Reason: The round-1 -1.5 was specifically tied to Q4's `[] == []` tautology. That tautology is gone. The query set is now substantively verified across 10 queries.

### 5. web_ui_e2e
- Project claim: 10.0
- Evidence: 6/6 flows return 200 with p95 ≤ 2ms (Flask test-client, fine for the rubric). Error handlers at `archkg/kg/web.py:240/252` still wired.
- Verdict: **keep 10.0**

### 6. recognition_quality
- Project claim: 10.0 (weighted P=0.8682, R=0.9395)
- Evidence:
  - Math at `archkg/kg/recognition_quality.py` is honest; per-rule TP/FP/FN computed from `feedback_event` confirm/reject and benchmark `expected_rule_counts`.
  - **NEW**: scorer attempts to disclose `label_provenance` (round-1 ask #5) but **SQL is wrong**: queries `SELECT name FROM reviewer`; the actual schema is `(id INTEGER PK, reviewer_id TEXT UNIQUE, display_name TEXT, meta_json TEXT)`. There is no `name` column. The exception is caught at `quality_score.py:507` and only the error string is surfaced. On disk: `"label_provenance": {"status": "probe_failed: OperationalError('no such column: name')"}`.
  - Verified via independent `sqlite3` probe: 22 reviewers total, 20 `demo-reviewer-*`, 1 bare `demo-reviewer`, 1 `smoke-runner`. **Zero human reviewers**. The synthetic-label problem from round 1 is unchanged.
  - `READINESS.md` line 40 still discloses synthetic reviewers in prose, so the disclosure surface is partial but not zero.
- Verdict: **override → 8.0**
- Reason: -1 carryover for 100% synthetic labels driving a "10.0" P/R headline (same root cause as round 1); -1 NEW for the broken `label_provenance` probe which silently fails so a JSON-only reader has no signal that labels are synthetic. Round-1 finding was supposed to be patched at this exact surface, and the patch does not work.

### 7. real_pdf_breadth
- Project claim: 10.0 (18 active real_public PDFs, threshold ≥ 15)
- Evidence: 18 active case IDs listed in `quality_score.json`. Round-1 spot-check of provenance + magic-bytes still valid; no new probes done this round.
- Verdict: **keep 10.0**

### 8. calibration
- Project claim: 10.0 (MAD = 0.0362, threshold ≤ 0.04)
- Evidence: 5 bins, lowest bin empty (correctly excluded), MAD over 4 used bins = 0.0362. Math still honest.
- Verdict: **keep 10.0**

### 9. feedback_loop
- Project claim: 10.0 (monotonic decrease after 3 rejects)
- Evidence: synthetic Beta-Binomial trajectory 0.333 → 0.25 → 0.20 verified; review_state separation from issues.json still architecturally honest.
- Verdict: **keep 10.0**

### 10. documentation_honesty
- Project claim: 10.0 (no overclaims detected)
- Evidence:
  - Scorer's forbidden-phrases list searched (`production ready`, `production-ready`, `battle tested`, `fully automated review`, `replaces human reviewer`, `100% precision`, `100% recall`, `state-of-the-art`, `guaranteed`, `enterprise`) → none in README/READINESS.
  - README line 14 still has explicit non-production disclaimer.
  - **NEW**: README line 7 F1 badge now reads `F1 1.00 — adversarial battery only` (yellowgreen). The round-1 implicit overclaim is removed. Body line 385 still has the matching "985 TP / 0 FN / 0 FP across 21 targeted rules at F1=1.00" qualification.
- Verdict: **promote 8.5 → 10.0**
- Reason: The round-1 -1.5 was specifically for the unqualified F1 badge at top-of-fold. The badge now self-qualifies in its own label text. No other overclaim badges or marketing prose found.

### 11. pilot_readiness
- Project claim: 10.0
- Evidence:
  - `docker-compose.yml` present, healthcheck wired, builds from `Dockerfile.pilot`. ✅
  - `Dockerfile.pilot` present. ✅
  - `bin/archkg-pilot` present and executable. ✅
  - `docs/PILOT_QUICKSTART.md`: **64 lines (`wc -l`)**, under the 80-line cap by 16 lines.
  - Flask error handlers (404 / 500) still wired at `archkg/kg/web.py:240/252`.
- Verdict: **promote 8.0 → 10.0**
- Reason: The round-1 -2 was specifically for the 88-line quickstart exceeding the 80-line cap. The doc is now 64 lines.

### 12. demo_video_quality
- Project claim: 10.0
- Evidence (re-probed):
  - `ffprobe .planning/m6/demo/archreview_kg_demo_final.mp4` → duration **283.38s** (in [180, 360]), resolution **1920x1080**, video + audio streams both present. ✅
  - `storyboard.json`: 8 shots, each with start/end/duration of correct types. Shot 7 is `kind: "limitations"` with caption "Honest limitations — over-detection, count-level recall, MA-only sourcing". Mandatory honesty shot present. ✅
  - `voiceover.wav` present, `script.txt` present.
- Verdict: **keep 10.0**

## Cross-cutting honesty notes (round 2)

1. **The disclosure regression on `label_provenance` is the most notable finding**. The team understood the round-1 ask, wrote the code, and shipped it — but the column name is wrong and the surfaced field is an error string. A JSON-only auditor would never know the precision/recall is computed against synthetic labels. **Fix: change `SELECT name FROM reviewer` to `SELECT reviewer_id FROM reviewer` in `archkg/quality_score.py:484`. One-character edit (s/name/reviewer_id/, plus s/n["name"]/n["reviewer_id"]/ in the comprehension at line 487).** This will then correctly compute synthetic=22, human=0, share=1.0, and surface the note as designed.

2. **Even when the probe works, the prefix-based classifier is incomplete**: the SQL prefix-checks `demo-reviewer-` (with trailing dash), but the DB also contains bare `demo-reviewer` and `smoke-runner`. The "human" count would still be wrong by 2 if the probe ran. Suggested classifier:
   ```python
   synthetic_prefixes = ("demo-reviewer", "smoke-runner", "demo-")
   synthetic = [r for r in reviewer_ids if any(r == p or r.startswith(p + "-") for p in synthetic_prefixes)]
   ```
   This would correctly return synthetic=22, human=0.

3. **Q9 is in a similar shape to round-1 Q4**: SQL is real, but the join never matches, so both sides are empty. Unlike Q4-round-1, Q9-round-2 is *not* hardcoded `WHERE 0` — it is a real join that legitimately finds nothing. Not docking points, but noting that the "10/10 correct" claim now depends on one query (Q9) returning empty=empty by data state rather than by data agreement. If a clause-edge ingestion is added later, Q9 will become a real verification.

4. **The 100% synthetic-reviewer issue is structural**, not cosmetic. M6 was supposed to produce a system that could be piloted with humans; until at least one non-`demo-` reviewer has confirmed/rejected ≥50 issues, the "weighted_precision: 0.87" headline is a measurement of the system against itself. This was the round-1 cross-cutting concern and it remains the round-2 cross-cutting concern.

5. **No new overclaim badges found**. The two remaining README badges (`pytest-440 passing` and `rules-32/32 covered`) are accurate against current artifacts (`pytest` actually shows 527 passing now, so the badge is slightly *under*-claiming — a minor inconsistency but in the honest direction).

6. **No new marketing language detected** in README, READINESS, or the demo `script.txt`. The forbidden-phrase guard plus the explicit "评估阶段工具，不是即开即用的生产服务" disclaimer holds.

7. **The demo storyboard still has the mandatory `kind="limitations"` shot** (shot 7, 48.38s, caption about over-detection / count-level recall / MA-only sourcing). The honesty shot is not optional and is not missing.

## Recommendation for next round
1. **Fix the `label_provenance` SQL** (1-line edit at `archkg/quality_score.py:484-485`: `SELECT reviewer_id FROM reviewer`; reference `row["reviewer_id"]` in the comprehension). Then verify `quality_score.json` actually contains `synthetic_reviewer_count`, `human_reviewer_count`, `synthetic_label_share`, `note` on disk. Add a unit test that asserts the probe returns those four keys, not `status: probe_failed`.
2. **Extend the synthetic-reviewer classifier** to catch bare `demo-reviewer` and `smoke-runner` as well as `demo-reviewer-*`.
3. **Get one real human reviewer into the KG** with ≥50 confirm/reject events. Even a single non-synthetic reviewer would unlock the round-1 "decompose into precision_synthetic + precision_real" recommendation. Until then, `recognition_quality` should remain capped below 10.0.
4. **Add a CI assertion that no top-level JSON disclosure field reads `status: probe_failed`** — this kind of silent-failure-to-disclose is exactly what the round-1 ask was meant to prevent.
5. **Consider promoting `weakest_dimension` reporting**: the scorer currently picks the first 10.0 by iteration order (here `code_quality`), which is misleading. A `recognition_quality_label_provenance_status` field at top level would make the residual visible without forcing the auditor to dig into nested detail.
