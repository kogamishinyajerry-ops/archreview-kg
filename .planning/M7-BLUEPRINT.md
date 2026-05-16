# M7 — Camera-Ready Workbench

**Mandate (2026-05-16):** Drive the product from M6's "minimal workbench that
demos itself" → blueprint image #1 (3-pane PDF viewport + queue + drawer),
plus blueprint #4 (web-UI quality dashboard) and blueprint #5 (multi-reviewer
disagreement inspector). Close the two carry-forward backlog items
(M6.W2 real reviewer labels, M6.W3 cross-state PDFs). Iterate to a judge-
verified 99+. Final deliverable: a real-UI screencapture demo video that
shows the workbench actually doing the thing.

**Authorization:** full ("全权开发" 2026-05-16).
**North star:** `.planning/m6/blueprint/` (6 PNGs + README).
**Honesty bar:** every score is the judge's, never the project's.

## Goal-backward decomposition (5 must-have waves + 1 stretch + Z + D)

| Wave | Deliverable | Blueprint anchor | Why now |
|------|-------------|------------------|---------|
| **W1** | PDF viewport in the workbench — server-side PDF→PNG render endpoint + SVG bbox overlay + bidirectional sync between bbox click and issue row click | image #1 left pane | Biggest single visual gap; "evidence-first" only makes sense when you can SEE the evidence on the drawing |
| **W2** | Filter chips + sort dropdown — top bar status chips (candidate / confirmed / rejected / needs_info / superseded / resolved) that filter the issue queue + sort by severity / rule_id / source_issue_id | image #1 top bar | Makes the queue actually usable when a project has 52 issues |
| **W3** | `/quality` page in the web UI — render per-rule P/R bar chart, calibration reliability plot, label provenance donut, judge audit arc, cross-project coverage — all live from quality_score.json | image #4 dashboard | Today the only path to quality data is `archkg quality-score` CLI. The pilot evaluator must see it in the UI |
| **W4** | Disagreement inspector — `/issues/<id>/disagreement` route with the 4-corner reviewer card layout + central PDF crop + append-only audit ledger | image #5 differentiator | Visual proof that "AI advises, human decides, KG remembers everything" |
| **W5** | Real per-instance reviewer label CLI — `archkg label assign` / `archkg label record` commands that write to feedback_event with a NEW `instance_label` payload field; `recognition_quality` scorer must also surface human-event counts so the M6 -1 closes when real labels appear | M6.W2 carry-forward | Only path to honestly closing the recognition_quality synthetic-label residual |
| **W6** *(stretch)* | Cross-state PDF expansion — source 4+ new non-MA active cases (target ≥3 distinct US states OR ≥1 CN city) | M6.W3 carry-forward | If time; otherwise stays in M7.5 backlog |
| **Z** | 13-dim scoring rubric extension + judge audits + iteration to 99+ | n/a | Same pattern as M5/M6 |
| **D** | Real-UI demo video v2 — 90-120s screencapture showing the new workbench live (PDF + bbox sync + filter chips + disagreement view + quality page); voiceover + Ken-Burns + highlight annotations | image #1 hero | The user's explicit deliverable |

## Scoring rubric — 13 dimensions

Existing 12 + `viewport_evidence_link` (new for W1+W4):

- `viewport_evidence_link` — bidirectional link between PDF bbox + issue row exists; clicking either selects the other; at least 1 sample drawing renders successfully via the PDF→PNG endpoint; bbox overlay coordinates are correctly scaled to image dimensions.

**99+ requirements** (unchanged from M6):
- All 13 dims ≥ 9
- ≥ ceil(0.75 * 13) = 10 dims at 10.0
- Judge override authority preserved

## Out of scope for M7

- Sheet classification (A1/S1/M1/FA1) — blueprint image #2 stage 1 — defer to M7.5
- Plugin SDK for custom rules — blueprint image #6 prod tier — M8+
- PostgreSQL multi-user deployment — blueprint image #6 — M8+
- Real LLM advisor integration — explicitly OUT, advisor stays out-of-band per philosophy

## Order of execution

1. **W5 first** (smallest, unlocks recognition_quality math) — ~30 min
2. **W1** (biggest visual leap, foundation for W4) — ~90 min
3. **W2** (small UX enabler on top of W1) — ~30 min
4. **W3** quality page — ~45 min
5. **W4** disagreement inspector (builds on W1+W2) — ~45 min
6. **Z** scoring rubric extension + judge audits (expect 2-3 rounds based on M6 pattern) — ~60-90 min
7. **W6** cross-state if time — ~45 min
8. **D** demo video assembly — ~45 min

Total budget: ~5-7 hours of focused work over multiple commits. Each
wave commits independently with a `feat(M7.Wx)` prefix.
