# M6 Round 3 — archreview-test-judge verdict
**Date:** 2026-05-16
**Auditor:** archreview-test-judge (independent, round 3)
**Project's claim:** overall 100.0/100, ninety_nine_plus: true (all 12 dims at 10.0)

## Verdict
- Judge overall: **99.0 / 100**
- Judge ninety_nine_plus: **true**
- Overrides applied: **1** (recognition_quality: 10.0 → 9.0)

The round-2 disclosure fix landed cleanly. `quality_score.json` now contains
a real `recognition_quality.detail.label_provenance` object with
`synthetic_reviewer_count: 22`, `human_reviewer_count: 0`,
`synthetic_label_share: 1.0`, `synthetic_reviewer_prefixes:
["demo-reviewer", "smoke-runner", "synthetic-"]`, and the explanatory
`note` field. The `probe_failed` error string from round 2 is gone. The
prefix classifier was extended exactly as round-2 recommended (it now
catches bare `demo-reviewer`, `smoke-runner`, and the `synthetic-`
namespace via `rid == p or rid.startswith(p + "-") or rid.startswith(p)`
at `archkg/quality_score.py:490`). A new regression test at
`tests/test_quality_score.py:200`
(`test_recognition_quality_disclosure_probe_never_silently_fails`)
explicitly asserts `prov["status"]` cannot start with `"probe_failed"`
and that the four canonical fields are present — this is a genuine
assertion, not tautological; if the round-2 bug recurred (wrong column
name → caught by `except Exception` → `status: probe_failed`), the
assertion at lines 214-217 would raise. Verified by inspection of test
logic + actual run (1 passed in 0.21s).

All 12 dimensions otherwise re-verify cleanly. Test suite is now **528
passing, 1 skipped** (the new disclosure test adds exactly +1 vs
round-2's 527). Ruff clean on `archkg/` and `tests/`. Quickstart still
64 lines. F1 badge still self-qualifies with "adversarial battery
only". Q4 SQL + Python remain real, independent paths returning
3 matching rows. Demo video 283.38 s @ 1920×1080 with the mandatory
limitations shot.

The remaining -1.0 carryover on `recognition_quality` is the structural
issue rounds 1 and 2 already documented: even with a working
disclosure, `human_reviewer_count` is still 0. The headline
`weighted_precision: 0.8682` / `weighted_recall: 0.9395` are
mathematically sound but measured against 100% synthetic labels. This
is now *transparent* in the JSON (was opaque in round 2), which is
itself a real improvement — round 2 capped at 8.0 (-1 broken probe -1
synthetic labels); the broken-probe penalty is fully discharged this
round, leaving only the -1 for actual label provenance. A reader of
`quality_score.json` can no longer skim the headline P/R without
seeing the disclosure block. The dimension is therefore promoted to
**9.0**, not the full 10.0 — full credit requires at least one
non-synthetic reviewer with ≥50 confirm/reject events so the headline
reflects field measurement, not the system measuring itself.

## Round-2 fix verification

| # | Round-2 finding | Verified? | Notes |
|---|-----------------|-----------|-------|
| 1 | `label_provenance` probe `probe_failed: OperationalError('no such column: name')` | ✅ **YES** | `archkg/quality_score.py:484` now reads `SELECT reviewer_id FROM reviewer`; comprehension at line 485 uses `row["reviewer_id"]`. Verified against schema: `reviewer (id PK, reviewer_id TEXT UNIQUE, display_name, meta_json)`. Probe now succeeds, surfaces `{synthetic_reviewer_count: 22, human_reviewer_count: 0, synthetic_label_share: 1.0, synthetic_reviewer_prefixes: [...], note: "..."}` in `quality_score.json:714-724`. |
| 2 | Prefix classifier incomplete (missed bare `demo-reviewer`, `smoke-runner`) | ✅ **YES** | `synthetic_prefixes` at line 487 now includes all three families (`"demo-reviewer"`, `"smoke-runner"`, `"synthetic-"`). Membership test at line 490 uses `rid == p or rid.startswith(p + "-") or rid.startswith(p)`, correctly catching bare `demo-reviewer`, the `demo-reviewer-*` family, bare `smoke-runner`, and any `synthetic-*`. Independent probe via `sqlite3` confirms: 22 reviewers total → 22 synthetic, 0 human (matches the JSON output exactly). |
| 3 | No CI assertion against silent `probe_failed` | ✅ **YES** | `tests/test_quality_score.py:200-220` (`test_recognition_quality_disclosure_probe_never_silently_fails`) re-runs the scorer for `only=["recognition_quality"]`, asserts the `label_provenance` block exists, asserts `status` is not `"probe_failed*"` (lines 214-217), and asserts all four canonical fields are present (lines 218-220). The assertion path is real — if the column-name regression came back, the `except Exception` block would surface `status: probe_failed: ...`, the test would hit line 214's `startswith` check and raise. Confirmed by re-deriving the exact failure path manually. Passes in 0.21s. |
| 4 | Top-level `recognition_quality_label_provenance_status` field (suggestion only) | ❌ **NOT IMPLEMENTED** | Round-2 *recommendation* #5 was a "consider" not an "ask". The disclosure is buried under `dimensions[5].detail.label_provenance` rather than being top-level. JSON-only readers still need to dig 3 levels deep. Not a regression; flagging as residual UX. |
| 5 | Get a real human reviewer into the KG | ❌ **NOT DONE** | `human_reviewer_count: 0` in the new disclosure block. Structural carryover; same root cause as round 1 and round 2. This is the only thing preventing `recognition_quality` from scoring 10.0. |

**Score**: 3 of 3 actionable round-2 asks landed (the SQL fix, the
classifier extension, the regression test). The disclosure regression
that was the round-2 -1 NEW finding is fully closed.

## Per-dimension audit (round 3, re-derived from disk)

### 1. code_quality
- Project claim: 10.0
- Evidence re-checked: `uv run ruff check archkg/ tests/` → `All checks passed!`. `uv run pytest -q` → `528 passed, 1 skipped in 42.44s` (skip = optional `ifcopenshell`, legitimate). New test contributes +1 vs round-2's 527. `quality_score.json` shows `mypy: Success: no issues found in 103 source files` (re-trusted; not re-run independently this round). Ruff with `--select F401,F841` (unused imports / unused vars) → clean.
- Verdict: **keep 10.0**

### 2. kg_persistence
- Project claim: 10.0
- Evidence: `.archkg/kg.db` exists, schema `kg.v1`, all 12 expected tables present, counts: 33 projects / 33 drawings / 33 runs / 25 rules / 23 clauses / 15 entities / 148 issues / 22 reviewers / **3061** feedback events / 0 edges (was 3054 in round 2 — +7 events from new test runs; consistent with normal activity). Query p95 = 0.006 ms.
- Verdict: **keep 10.0**

### 3. kg_coverage
- Project claim: 10.0 (33/33 runs ingested)
- Evidence: coverage 1.0 in `quality_score.json`; manifest still distinguishes `active` vs `known_gap` honestly. 18 real-public + 15 synthetic = 33.
- Verdict: **keep 10.0**

### 4. cross_project_query
- Project claim: 10.0 (10/10 canonical queries correct)
- Evidence:
  - Q4 SQL at `archkg/kg/query.py:201-205` and Python re-impl at `query.py:85-94` are independent paths (SQL: `GROUP BY ... ORDER BY ... LIMIT 3`; Python: separate query then `dict.get + 1` aggregation + `sorted` + slice). Both return 3 matching rows: `[("RC-ACCESSIBLE-DOOR-WIDTH-0.80", 124), ("RC-DOOR-WIDTH", 118), ("RC-ACCESSIBLE-INDOOR-CORRIDOR-WIDTH-1.20", 29)]`. Real non-tautological agreement.
  - Q1, Q2, Q3, Q5, Q6, Q7, Q8, Q10 return non-trivial matching row sets (25 / 11 / 4 / 26 / 1 / 1 / 127 / 33 rows respectively, matching `expected_count`).
  - Q9 still returns empty=empty (no `rule_id` prefix matches any `standard_id`). Round 2 ruled this acceptable (real join, data-state empty, not hardcoded). Re-affirmed this round.
  - Searched for orphan Q-functions: `grep -rn "q4_top_rule_clause_pairs\|top_rule_clause_pairs"` returns no hits — the round-1 Q4 tautology function was deleted, not orphaned. All 10 q-functions are referenced by name in `query.py` at lines 176-275.
- Verdict: **keep 10.0**

### 5. web_ui_e2e
- Project claim: 10.0
- Evidence: 6/6 flows return 200 with p95 ≤ 2.1 ms (Flask test-client). Error handlers at `archkg/kg/web.py:240/252` still wired (per round 2's spot-check; not re-probed this round).
- Verdict: **keep 10.0**

### 6. recognition_quality
- Project claim: 10.0 (weighted P=0.8682, R=0.9395)
- Evidence:
  - Math at `archkg/kg/recognition_quality.py` is unchanged from round 2 (still honest).
  - **NEW for round 3 — disclosure probe now works**: `quality_score.json:714-724` contains a real `label_provenance` block with `synthetic_reviewer_count: 22`, `human_reviewer_count: 0`, `synthetic_label_share: 1.0`, `synthetic_reviewer_prefixes: ["demo-reviewer", "smoke-runner", "synthetic-"]`, and the canonical `note` text. The round-2 `probe_failed` regression is closed.
  - Independent verification of the prefix classifier: probed `.archkg/kg.db`, confirmed 22 reviewer_ids — all match `demo-reviewer*` or `smoke-runner`. The classifier's `len(synthetic) == 22, len(human) == 0` is correct against ground truth.
  - New `notes` field in JSON: `"label provenance: 100% synthetic reviewers (demo-reviewer, smoke-runner, synthetic-); P/R is sound math but not human-validated yet"` — surfaced to readers via the standard `dimensions[i].notes` channel as well as the nested detail.
  - `READINESS.md:40` independently discloses `demo-reviewer-*` namespace in Chinese prose.
  - **Still residual**: `human_reviewer_count: 0`. The headline P/R is the system measuring itself; no field validation yet.
- Verdict: **override → 9.0**
- Reason: -1 structural carryover for 100% synthetic labels (same root cause as rounds 1 and 2, but disclosed transparently this round). The round-2 -1 NEW penalty for the broken probe is fully discharged because the probe now works and is regression-protected by a real CI assertion. Promoting from 8.0 → 9.0 (not 10.0): full credit requires at least one non-synthetic reviewer with ≥50 confirm/reject events.

### 7. real_pdf_breadth
- Project claim: 10.0 (18 active real_public PDFs, threshold ≥ 15)
- Evidence: 18 active case IDs listed in `quality_score.json:737-754`. Round-2 provenance + magic-bytes spot-check still valid; no regression probes this round.
- Verdict: **keep 10.0**

### 8. calibration
- Project claim: 10.0 (MAD = 0.0362, threshold ≤ 0.04)
- Evidence: 5 bins, lowest bin (0.0-0.2) empty so correctly excluded by `min_samples_per_bin: 5`, MAD over 4 used bins = 0.0362. Math holds.
- Verdict: **keep 10.0**

### 9. feedback_loop
- Project claim: 10.0 (monotonic decrease after 3 rejects)
- Evidence: Beta-Binomial trajectory 0.333 → 0.25 → 0.20 verified; delta -0.166667 matches expected.
- Verdict: **keep 10.0**

### 10. documentation_honesty
- Project claim: 10.0 (no overclaims detected)
- Evidence:
  - Forbidden-phrase scan still clean.
  - F1 badge at `README.md:7` still reads `F1 1.00 — adversarial battery only` (yellowgreen).
  - `CHANGELOG.md:932/1020/1021` references F1=1.00 are in context (e.g., "across 21 of the 32 targeted rule cards at F1 = 1.00 across a battery") — context is preserved; no marketing-style detachment of the number.
  - `pytest-440 passing` badge still under-claims vs actual 528 (round 2 already noted this is in the honest direction; not a regression).
- Verdict: **keep 10.0**

### 11. pilot_readiness
- Project claim: 10.0
- Evidence: `wc -l docs/PILOT_QUICKSTART.md` = **64**, under the 80-line cap by 16 lines. `docker-compose.yml`, `Dockerfile.pilot`, `bin/archkg-pilot` all present. Error pages still wired.
- Verdict: **keep 10.0**

### 12. demo_video_quality
- Project claim: 10.0
- Evidence (re-probed):
  - `ffprobe .planning/m6/demo/archreview_kg_demo_final.mp4`: duration **283.38 s** (in [180, 360]), resolution **1920x1080**, video + audio streams present.
  - `storyboard.json`: 8 shots; shot 7 is `kind: "limitations"` (48.38 s). Mandatory honesty shot present.
  - `voiceover.wav`, `script.txt` both present.
- Verdict: **keep 10.0**

## Cross-cutting honesty notes (round 3)

1. **The round-2 disclosure regression is fully closed.** The fix is minimal (s/`name`/`reviewer_id`/; expanded prefix tuple; one new test), the test is real (would catch a recurrence), and the JSON output is now legible without digging. This is exactly the right shape of a round-2 → round-3 patch.

2. **No new orphan code from the Q4 refactor.** Verified by `grep -rn` for the round-1 Q4 tautology function name (`q4_top_rule_clause_pairs`) across `archkg/ tests/ scripts/` — zero hits. The old tautology function was deleted, not stranded. All 10 q-functions (`q1` through `q10`) are referenced by `expected_fn=...` in the `_CANONICAL_QUERIES` tuple at `query.py:166-275`.

3. **No CHANGELOG breakage from the README badge change.** The F1 references in `CHANGELOG.md:932/1020/1021` are descriptive context ("21 of the 32 targeted rule cards at F1 = 1.00 across a 100-case battery") rather than detached marketing claims; they survive the badge edit without contradiction.

4. **Ruff still clean.** No unused imports or unused locals from the Q4 refactor or the disclosure-probe patch (`uv run ruff check --select F401,F841 archkg/ tests/` → `All checks passed!`).

5. **Test suite grew by exactly 1 from round 2 → round 3** (527 → 528). The new test is the disclosure probe regression guard. No other tests were added or removed.

6. **Other `detail` blocks that could silently degrade** were surveyed:
   - `rule_card_parse_error` (quality_score.py:699) — would only fire if YAML parse fails; currently `total_rule_cards: 32` proves the success path. Not a regression risk under current data.
   - `recognition_quality.detail.status` (line 452, 463) — surfaces `recognition_quality_module_missing` or `no_rules_with_ground_truth` cleanly; not silent.
   - `pytest`/`ruff`/`mypy` tool detail (lines 118-183) — fail-loud with exit codes and tails.
   - **No new silent-degrade patterns found.**

7. **The `feedback_event` count drifted from 3054 (round 2) to 3061 (round 3).** +7 over the auditing window is consistent with the new test invocation + a few re-runs of the scorer probe (each scorer call exercises the recognition-quality machinery against the live DB). Not a tampering signal.

8. **The "ninety_nine_plus" gate**: scorer rule is `all >= 9 AND >= ceil(0.75 * n_dims) dims == 10`. With my override, recognition_quality = 9.0 (≥9), all 11 others = 10.0 (≥9 of 12 are 10.0, which is ≥ ceil(0.75 × 12) = 9). Therefore `ninety_nine_plus: true` holds under my override too.

## Recommendation for next round

1. **Get one real (non-`demo-*`, non-`smoke-runner`, non-`synthetic-*`) reviewer with ≥50 confirm/reject events into the KG.** This is the only thing preventing recognition_quality from a clean 10.0. The disclosure infrastructure now exists to handle a mixed-population KG; only the population itself is missing.

2. **(Optional, low priority)** Surface a top-level `recognition_quality_label_provenance: {synthetic: 22, human: 0}` summary alongside the existing `weakest_dimension` field in `quality_score.json` root, so JSON-only readers don't have to dig 3 levels into `dimensions[5].detail.label_provenance` to see the residual. Round-2 recommendation #5 standing.

3. **(Optional, low priority)** Update the README `pytest-440 passing` badge to `pytest-528 passing` to match actual test count. Currently under-claiming (which is honest), but consistency is cleaner.

4. **No other action items.** The system is in genuinely good shape — three rounds of audit have driven out a measurable Q4 tautology, a badge overclaim, a quickstart bloat, and a silent disclosure regression. The remaining residual (synthetic labels) is structural and requires data, not code.

## Honest verdict statement

This round, the project earns **99.0/100** with one override (recognition_quality 10.0 → 9.0 for structural synthetic-label residual). `ninety_nine_plus: true` holds. The 100.0/100 claim is one structural data-collection effort away from being independently corroborated. The team responded to round 2 cleanly, surgically, and with a regression-guard test — exactly the shape of a healthy fix cycle.
