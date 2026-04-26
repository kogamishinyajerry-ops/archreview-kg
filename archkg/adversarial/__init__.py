"""Adversarial training lane (Phase 18-D).

A pair of agents drives test-corpus growth and rule-quality measurement:

  Examiner  → generates a flawed plan + ground_truth declaring the violations
              the candidate is expected to find.
  Candidate → archkg review pipeline (no changes).
  Adjudicator → scores the candidate's issues.json against ground_truth and
              produces per-rule precision/recall/F1.

The point: today archkg has exactly one toy fixture (sample_clean.pdf) and
the readiness lane is theoretical. With a battery of generated cases we
measure rule quality on dozens of variations and surface false-negatives
as candidate test_case material. (False-negatives are listed by
case_id in the scoreboard but not yet auto-promoted to rule_cards.yaml
test_cases — that promotion lives in a future phase.)

Phase 18-D ships an L1 (deterministic, no-LLM) examiner. L2 (LLM-driven
red-team examiner) and L3 (real-PDF perturbation) are later phases.
"""
