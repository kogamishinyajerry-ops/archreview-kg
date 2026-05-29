# Milestone scope — real-corridor extraction (R7-BUG-003)

> Status: **PARTS 1 + 2 LANDED (2026-05-29).** Part 1 (wide-opening repair in
> `archkg/graph/geometry.py`) extracts the m16/m15 **page-0** ground-floor
> corridors; part 2 (trunk-corridor carve in `archkg/graph/builder.py`) recovers
> the m16/m15 **page-1** trunk corridor that part 1 could not close. Both are
> verified **issue-level FP-neutral** on the cambridge / m10-m14 control set (at
> `min_room_area_m2` 0.0 AND 1.0). Acceptance gates
> `tests/test_graph_builder.py::test_m16_real_corridor_extracted` (page-0) and
> `::test_m16_page1_trunk_corridor_extracted` (page-1) both pass.
> **Remaining (part 3, lower priority):** p1 bedroom-door positions don't match
> intended, and the RC-BEDROOM-AREA matcher gap. See "Remaining work" below.
> Authored 2026-05-29 after a diagnosis workflow + independent verification + two
> FP-controlled candidate workflows (closure, then carve). This was the deepest
> recall gap the M11–M16 audits repeatedly deferred.

## What landed (part 1)

The verified FP-neutral closure (workflow `corridor-closure-fp-controlled` Candidate 2, then independently re-measured and **refined to fix an FP the workflow missed**): a horizontal-only additive pass in `bridge_door_gaps` that bridges a wide gap (up to `WIDE_GAP_MAX_PT=70pt`) **only when flanked on both sides by long collinear wall runs (`LONG_RUN_PT=150pt`)**. Critically the wide bridge is appended to `augmented` (wall closure for polygonize) **but not to `bridges`** — so it never creates a Door entity. The workflow's corridor-only FP measurement had passed Candidate 2, but my issue-level re-measurement found the door-creating form added spurious RC-DOOR-WIDTH issues on m10 (0.75m) and m14 (0.85m) via dimension binding; the augmented-only form is issue-level FP-neutral (0 new issues on every geometrically-distinct control plan).

## What landed (part 2 — page-1 trunk corridor carve)

The m16/m15 **page-1** trunk corridor was still missed after part 1: its top wall
has a **74pt (1.48m) opening** that exceeds `WIDE_GAP_MAX_PT=70`, so the wall never
closes and `polygonize` floods the corridor strip into the room band. Naively
raising the wide ceiling to catch the 74pt gap closes the top wall but yields a
**1.65m merged polygon** (the strip merges downward through the debris-laden
bottom wall into the room below) — which is `>= 1.20m` so it fires **nothing**:
useless for recall, and it adds FP risk. Three candidate fixes were prototyped in
an FP-controlled workflow (raise-ceiling-and-close-both-walls; re-measure width
from wall chords; post-polygonize carve). The first two were rejected — the
ceiling-raise leaves a spurious 1.65m entity, and post-hoc width re-measurement is
**inseparable from an m14 false positive** (m14/m15/m16 share the same band
geometry; any re-measure that catches m16-p1 also lights m14).

The **post-polygonize carve** (`_carve_trunk_corridors` in `builder.py`, run before
dimension binding) won: it detects the corridor directly from its defining
geometry — two long, mostly-covered parallel wall chords a corridor-width apart —
and carves that band out of the flooded host room, measuring width from the
**chord gap** (so it reports the TRUE ~1.10m regardless of whether the wall
closed). Three discriminators carry FP-control (each verified load-bearing by
ablation, pinned by `test_trunk_carve_gate_*_is_load_bearing`):

1. **host-room** — the band must sit inside a polygonized room (the flooded host);
2. **remnant-both-sides** — a real room remnant ≥0.5m above AND below the band
   (rejects bands glued to a room edge, e.g. m14);
3. **no-crossing-verticals** — no interior vertical crosses ≥60% of the band height
   (rejects furniture/fixture clusters chopped into cells, e.g. m13).

The width window reuses the corridor classifier's `CORRIDOR_SHORT_MIN_M..MAX_M`
(0.5–2.0m), **not** a fixture-centered window: independently verified that widening
it to the full corridor band changes nothing on any control plan, so the
discriminators — not the width — do the FP-control work. Result (independently
re-measured at issue level, not trusting the workflow): m16/m15 page-1 gains
**exactly one** corridor at 1.10m firing both corridor-width rules (+2 issues);
**every** control plan (cambridge×3, m10, m12, m13, m14, sample_clean) byte-
unchanged in total issues AND corridor counts at `min_room_area_m2` ∈ {0.0, 1.0};
0 dangling door refs; page-0 not double-carved. 581 tests green.

## Remaining work (part 3 — door/area gaps)

## The gap (part 1, historical — page-0, now closed)

On `samples/real_plans/test-m16-defective-plan.pdf` the engine extracts **0 of 3** real corridors, so `RC-CORRIDOR-WIDTH` recall is ~0. (The phantom "corridors" that previously fired were border/legend bands, removed by the `_is_sheet_edge_band` fix; their removal corrected the m16 headline recall from a phantom-inflated 62.5% to an honest 25%.)

## Verified root cause

Real corridors **are explicitly walled** (not negative space), but the corridor's bottom long-wall never closes into a thin polygon, so `polygonize_segments` floods the corridor strip into the room band below it (one polygon bbox≈`[70,440,1060,762]`, short side **6.44 m** → classified a room, not a corridor).

Two compounding causes on the bottom wall (engine ppm 50, wall at y≈495):

1. **Wide opening exceeds the door-bridge ceiling.** One intended opening is **66 pt (1.32 m, the "service entry")**, wider than `DOOR_MAX_M*ppm = 50 pt (1.0 m)`. `bridge_door_gaps` only closes openings in `[DOOR_MIN_M, DOOR_MAX_M]·ppm = 35..50 pt`, so this hole stays permanently open. Any corridor whose bounding wall has a ≥1.0 m doorway is structurally un-closable today.
2. **Door-swing debris masks the bridgeable gaps.** Door-swing arc/leaf line primitives snap into the wall's y-group; `bridge_door_gaps` sorts segments by start-x, so the interleaved arc chords destroy consecutive wall-fragment adjacency and the otherwise-bridgeable ~44 pt gap is missed. Net: **0 bridges on the bottom wall vs 4 on the top.**

The top wall closes fine (its 4 gaps are 38/44/41/44 pt, all in-window). It is a bottom-wall-only closure failure.

## Why there is no quick fix (independently verified)

Every naive closure that restores m16 corridor recall **re-introduces the phantom-thin-polygon FP class just eliminated**, and m16 needs *both* causes fixed:

| Plan | corridors @ DOOR_MAX_M=1.0 (base) | @ 1.4 m (naive closure) |
|---|---|---|
| `sample_clean.pdf` | 1 | **2** (new FP) |
| `test-m12-defective-plan.pdf` | 4 | **6** (new FPs) |
| `test-m13-defective-plan.pdf` | 13 | **17** (new FPs) |
| `test-m16-defective-plan.pdf` | 0 | **0** (still broken — debris also blocks it) |

Also note the corridor classifier is **already noisy on real plans** with no ground truth to validate against: `cambridge-343medford` reports 9 "corridors" incl. 30 m / 14 m wide; `cambridge-sp336-basement` reports a single **87 m** "corridor" (the whole plan). These don't fire `RC-CORRIDOR-WIDTH` (≥1.2 m) but are mis-classifications. So loosening corridor detection without an FP control set will make real-plan output worse, silently.

## The real fix (two parts, both required)

1. **Door-swing debris stripper** — exclude door-swing arc chains + leaf chords from wall-fragment grouping (signature: ≥4 short segments with cumulative turn, which straight walls never have). FP-neutral and recall-neutral *alone* (the 66 pt gap still blocks), but required so closure can see real wall adjacency. Touch `archkg/ingest/pdf_loader.py` or a pre-pass before `bridge_door_gaps` in `archkg/graph/geometry.py`.
2. **Corridor-aware closure** — pair two long, mostly-covered parallel wall chords a corridor-band apart and force-close the gappy chord *within their overlap* to form the thin polygon, tolerating one wide (circulation-width) opening. Do **not** raise the global `DOOR_MAX_M` (re-merges rooms across legitimate 1.0–1.35 m doorways) and do **not** force-close on bare parallel-wall proximity (creates interior slivers — measured a 0.5 m sliver on `cambridge-sp336` and a 1.65 m sliver on m16 p1 — that the sheet-edge guard cannot catch because they are mid-page).

## FP control protocol (mandatory for this milestone)

- Treat the three `cambridge-*` plans as a regression **FP control set**: corridor count must not exceed a recorded baseline after closure ships.
- Reuse the existing `_is_sheet_edge_band` guard (it still drops border/legend bands).
- Add interior-sliver rejection (min corridor area / min length) tuned against the cambridge control.

## Acceptance gate

`tests/test_graph_builder.py::test_m16_real_corridor_extracted` (xfail strict). It flips to XPASS — and, being `strict`, fails the suite to prompt removal of the mark — exactly when the milestone lands. Also add: a cambridge FP-control test, and a `test_rules_engine` assertion that `RC-CORRIDOR-WIDTH` fires on the m16 corridor at 1.10 m once extraction works.
