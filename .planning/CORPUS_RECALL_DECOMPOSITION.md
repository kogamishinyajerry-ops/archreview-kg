# Corpus-wide recall decomposition — the honest two-number gap (2026-05-29)

> Measured end-to-end through the real engine (`archkg review` fresh run) against
> all 7 defective-plan manifests (m10, m10b, m12–m16), using the round-7 audit's
> own recall matcher (same `rule_id` + same `page_index` + IoU≥0.1 OR x-overlap≥50%).
> Engine state: corridor-extraction parts 1+2 landed (commits e4c48d7, 20e5c37, 41f5969).

## The three numbers

| number | value | what it actually measures |
|---|---|---|
| self `quality-score` | **99.75/100** | UI / workbench / KG / process / honesty — **NOT detection recall** |
| raw adversarial audit recall | **43.6%** (34/78) | hits / ALL intended defects — **unfair denominator** (see below) |
| **honest perception recall** | **66.7%** (34/51) | hits / genuinely-detectable defects with a correctly-modelled rule |

The raw 43.6% is misleading: **27 of the 78 "defects" can never be caught by any
perception improvement.** The honest measure of the engine's detection quality is
**66.7%**.

## Decomposition of all 78 corpus defects

| bucket | count | meaning | fixable? |
|---|---|---|---|
| **HIT** | 34 | engine fired a matching issue | — |
| **ADVERSARIAL-TRAP** | 6 | manifest bbox is malformed (negative / x0>x1 / zero-area) or flagged ADVERSARIAL — unmatchable **by construction** (robustness traps, not detection targets) | no (by design) |
| **CAPABILITY-LIMIT** | 16 | non-geometric rule (stair tread/riser, railing height/spacing, net-height, basement occupancy, handrail, step-protection, elevator adjacency) — needs section / 3D / OCR / specialised-symbol data a 2D line-primitive engine cannot extract | no (without new capabilities) |
| **RULE-MODELING-GAP** | 5 | engine detected the entity, but the rule card is coded more leniently than the audit's ground truth — e.g. RC-BEDROOM-AREA fires `<5.0 m²` (单人卧室 floor) while the defects are 5.6–7.2 m² violations of the 9 m² 双人卧室 minimum (`code_minimum=9.0`). The same clause GB50096-5.3.1 carries both thresholds; only the lenient one is implemented (a flat 9.0 would false-positive on every legit 5–9 m² single bedroom — single-vs-double is not derivable from 2D geometry) | rule change, trades recall for FP risk — NOT a detection fix |
| **REAL PERCEPTION GAP** | **17** | entity genuinely not detected (flooded / merged / missed) and the rule *would* fire if it were — the only truly fixable detection bugs | **yes** |

Per-plan: m10 `3/1/2/1/1`, m10b `0/0/7/0/0` (all capability-limit — a basement/stair/height plan), m12 `3/0/5/1/0`, m13 `12/0/0/1/5`, m14 `2/5/0/0/6`, m15 `9/0/2/1/3`, m16 `5/0/0/1/2` (HIT/ADV/CAP/RULE/PERC).

## The 17 real perception gaps — and they CLUSTER

| cluster | count | plans | nature |
|---|---|---|---|
| **trunk corridors (west/east split)** | **8** | m13, m14 (each: west + east half × {RC-CORRIDOR-WIDTH, RC-ACCESSIBLE-CORRIDOR}) | **the exact flooding class fixed for m15/m16 page corridors — different topology (split trunk). Highest-leverage fixable cluster.** |
| **door label-vs-geometry CLASH** | 4 | m14, m15, m16 | adversarial: a wide opening (e.g. 74pt/1.48m) labelled "650mm" — engine makes no door (>door ceiling) and geometric width isn't a defect; needs door-from-text/symbol (a capability gap in disguise) |
| **master-egress door** | 2 | m15, m16 | 38pt gap on a debris-laden bottom wall — door-swing debris breaks fragment adjacency (pre-scoped "debris stripper") |
| **other doors / accessible** | 3 | m10, m13, m15 | bathroom accessible-door, UNIT-B bedroom door |

## Implications (the honest assessment)

1. **The engine's true perception recall is 66.7%, not 43.6%** — the adversarial
   audit's headline understates detection quality as badly as the self-score
   overstates it. Neither number is the honest one; this decomposition is.
2. **Corridors are the dominant fixable gap (8 of 17).** The m13/m14 split trunk
   corridors are the same flooding root cause as parts 1+2, on plans previously
   used only as FP *controls* — so they were never targeted. This is the clear
   next high-leverage fix (potential 66.7% → ~82% honest perception recall),
   in-wheelhouse and FP-controllable with the established protocol.
3. **~half the gap is structurally not a detection problem.** 16 capability-limit
   + 6 adversarial-trap + 5 rule-modeling = 27 defects (35% of the corpus) that
   no perception work can recover. Beyond corridors, further recall requires
   either new capabilities (OCR / schedule-table parsing / section data) or rule
   changes that trade recall for FP risk — strategic investments, not bug fixes.
4. **The door-CLASH cluster (4) is adversarial label-vs-geometry** — properly a
   capability gap (door-from-text), not a quick geometric fix.

## Recommended next: m13/m14 trunk-corridor extraction (perception, FP-controlled)

8 of the 17 perception gaps. Same milestone discipline as parts 1+2: diagnose the
m13/m14 split-trunk topology, design an FP-safe extraction, validate issue-level
FP-neutral on the cambridge control set AND that m13/m14's *other* regions don't
gain phantoms. Everything past that is capability/rule investment, to be decided
deliberately.
