# Milestone scope — real-corridor extraction (R7-BUG-003)

> Status: **scoped, not started.** Acceptance gate = `tests/test_graph_builder.py::test_m16_real_corridor_extracted` (currently `xfail strict`).
> Authored 2026-05-29 after a diagnosis workflow + independent verification. This is the deepest remaining recall gap and the one the M11–M16 audits repeatedly deferred.

## The gap

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
