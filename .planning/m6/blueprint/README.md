# M6 Blueprint Anchor Images

Six independent reference images generated 2026-05-16 via GPT Image-2 from
prompts in the M6 closeout review. These are the **visual north star** for
all post-M6 design work (M6.5, M7, M8). When in doubt about UX direction,
typography, palette, or what a feature "should look like in its final
form" — return here.

Source prompts live in conversation history (search "GPT Image-2 提示词集").

| # | File | Purpose | Use when |
|---|------|---------|----------|
| 1 | `archreview_kg_01_hero_final_workbench.png` | Hero — the end-state 3-pane workbench UI (PDF viewport + issue queue + evidence drawer) | M7 UI planning, README hero, conference talk slide 1 |
| 2 | `archreview_kg_02_system_architecture_data_flow.png` | 7-stage pipeline diagram with AI advisor as dotted out-of-band loop | Architecture explanation, ADR docs, onboarding eng |
| 3 | `archreview_kg_03_evidence_chain_lifecycle.png` | One finding traced from PDF→entity→rule→issue→reviewers→calibration update | Compliance auditor pitch, philosophy doc opening, "why us not them" |
| 4 | `archreview_kg_04_honest_quality_dashboard.png` | Per-rule P/R + calibration + label provenance + judge audit arc | Trust page, blog post on honest scoring, M7+ QA dashboard target |
| 5 | `archreview_kg_05_disagreement_preserved_multi_reviewer.png` | Same issue, 4 reviewer verdicts (incl. arbiter override), audit ledger preserved | Differentiation vs "AI auto-review" competitors, multi-reviewer feature spec |
| 6 | `archreview_kg_06_deployment_jurisdiction_expansion.png` | Pilot (M6) vs Production (M7+) tiers + jurisdictional expansion map | Pricing/tiering conversation, roadmap doc, investor deck (later) |

## Quality notes (judge-honest assessment)

- Images 1, 2, 3, 5 are pixel-canonical — use as-is.
- Image 4 is excellent except the US map silhouette is abstract (still
  legible because MA + MN labels are correct).
- Image 6 is the weakest of the set — the geographic map is barely-
  recognizable continent shapes. **Regenerate if used externally**:
  use a prompt that specifies "low-poly SVG-style real continent outlines
  + lat/lng-accurate city dots".

## Status of features depicted

Not every feature in these images is shipped in M6. The images are
**aspirational anchors** for the final product, not screenshots of
current state. Specifically:

| Feature in image | Status in M6 | Tracked in |
|------------------|--------------|------------|
| 3-pane workbench with PDF viewport overlay | ❌ not shipped | M7 scope |
| Issue-detail drawer + feedback buttons | ✅ shipped (M6.W1) | committed in `archkg/kg/web.py` |
| Live confirm/reject POST writing to KG | ✅ shipped | M6 demo video proves this |
| Beta-Binomial calibration | ✅ shipped (per-rule) | `archkg/kg/calibration.py` |
| Disagreement preservation | ✅ shipped (feedback_event table) | KG schema |
| Synthetic-vs-human disclosure | ✅ shipped (label_provenance) | `quality_score.json::recognition_quality.detail` |
| Judge audit arc | ✅ shipped (4 rounds R1 88 → R4 100) | `JUDGE-VERDICT-round{1..4}*.md` |
| Pilot tier (docker compose / archkg-pilot) | ✅ shipped | `docker-compose.yml` + `bin/archkg-pilot` |
| Production tier (PostgreSQL, multi-user, audit export) | ❌ not shipped | M7+ scope |
| Jurisdictional packs (GB / IRC / NCC / NBC) | ❌ not shipped | M7+ scope |
| Cross-state coverage (≥5 US states + ≥5 CN cities) | ❌ M6.5.W3 backlog | |

Anything in these images that is **not yet shipped** must NOT be claimed
in marketing copy as if it were. The blueprint images are for internal
design anchoring + roadmap visualization only, not for misrepresenting
current capabilities.
