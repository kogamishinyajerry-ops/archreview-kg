# M6 Blueprint — "From Tool to Product" + Commercial Showcase

> Created: 2026-05-16
> Owner: Claude (Opus 4.7, acting as project lead)
> Authorization: User-granted full autonomy, blueprint-driven iteration to >= 99/100, ending with a commercial-grade promo video.
> Predecessor: `.planning/m5/M5-CLOSEOUT.md` (M5 closed at 100/100 day-1; day-2 verification rolls into M6.Z).

## North Star (one sentence)

ArchReview-KG transitions from a benchmark-passing internal tool into a
**pilot-ready product** that an architectural firm can install, evaluate,
and decide to adopt within 30 minutes — and ships with a 3-5 minute
commercial-grade promo video that explains the product end-to-end.

## Why M6 (and why not just polish M5)

Test-judge round-4 closed M5 at 100/100, but the closeout document
itself flagged five honest M6-scope follow-ups:

1. Per-instance reviewer ground truth (recall formula's contract limit).
2. Precision uplift on 5 sub-0.7-precision rules.
3. Recall recovery on 4 sub-0.30-recall rules.
4. Sourcing diversity beyond MA (currently 17/18 active MA).
5. Q4 and Q9 canonical queries still return trivially-zero rows.

Plus three product-shipping concerns the M5 rubric didn't measure:

6. Web UI is functional but not camera-ready (no design system, no
   transitions, no empty/loading states).
7. No deployment kit — installing requires cloning the repo and
   running `archkg kg init` by hand.
8. The product has never been demonstrated to a non-developer.

M6 attacks 1-8.

## Scope: 8 phase clusters

### M6.A — Web UI camera-ready polish

- Design system tokens (typography scale, color, spacing, shadow).
- Empty / loading / error states on all 5 flows.
- Transitions: route changes, list updates, focus changes.
- High-contrast theme + screenshot-friendly default.
- Keyboard shortcuts on reviewer annotation.

### M6.B — Real reviewer ground truth pipeline

- New CLI: `archkg label assign --reviewer <id>` queues N issues per reviewer.
- New CLI: `archkg label record --issue-id <id> --verdict <true|false>`.
- Per-instance labels stored in new `instance_label` table, distinct from
  the synthetic panel `feedback_event` table.
- Recall formula gets an **instance-level** path that activates when at
  least 30 per-rule instance labels exist; the count-level fallback
  remains for unlabelled rules.
- Land at least 90 honest per-instance labels across 3 high-detection
  rules (RC-ACCESSIBLE-DOOR-WIDTH, RC-DOOR-WIDTH, RC-CORRIDOR-WIDTH).

### M6.C — Multi-state PDF sourcing expansion

Current: 17 MA + 1 MN = 2 states. Target: 5+ states.

- Source 7+ additional public PDFs from at least 4 new US states
  (CA, OR, WA, TX, MN beyond Hopkins, IL, CO).
- Each new active case lands with `expected_rule_counts` AND, where
  practical, real per-instance labels (M6.B linkage).
- Active real_public_pdf grows 18 → 25+.

### M6.D — Pilot deployment kit

- `docker compose up` boots the full stack (web UI + KG + sample data).
- One-command init: `./bin/archkg-pilot init` creates project, ingests
  sample bundle, opens browser.
- Error pages on the web UI for: malformed KG, missing run dir,
  unparseable PDF.
- 5-minute quickstart in `docs/PILOT_QUICKSTART.md`.

### M6.E — Demo storyboard + screen recording

- Script the demo: a 7-shot storyboard (opening → upload PDF →
  recognition pass → issue lifecycle → calibration / quality story →
  honest limitations → closing).
- Capture each shot deterministically via peekaboo MCP + screencapture.
- Output: 7 raw `mov` clips + 7 timestamped captions JSON.

### M6.F — Voiceover script + TTS render + audio mix

- Write the voiceover script (~600-800 words, 3-5 min reading).
- Render via `say -v Samantha` at 220 wpm → 30 kHz WAV.
- Optional ambient bed via ffmpeg sine wave (very quiet, -38 dB).
- Mix via ffmpeg with ducking under voice.

### M6.G — Video assembly + final cut

- ffmpeg pipeline: trim, crossfade, motion-zoom (Ken Burns), captions,
  voiceover bed, output 1080p H.264 mp4 + WebM.
- Captions baked in (no separate subtitle track for the primary mp4).
- 3-5 min final length.

### M6.Z — Iterate to 99+

After each phase delivery, run the test agent. Address the weakest
dimension first. Loop until overall >= 99 with no dimension < 9.
Stop work that does not improve a measured dimension.

## Scoring rubric — 12 dimensions, 120 points → normalised to 100

10 of the M5 dimensions carry over (they must not regress).
Two new dimensions for product/showcase:

| #  | Dimension                    | How measured                                                                                                  | 9-10 pt threshold                                          |
|----|------------------------------|---------------------------------------------------------------------------------------------------------------|------------------------------------------------------------|
| 1  | Code Quality                 | ruff / mypy / pytest -q, 0 warnings                                                                           | Green                                                      |
| 2  | KG Persistence               | schema valid, p95 < 50ms                                                                                      | OK                                                         |
| 3  | KG Coverage                  | runs ingested / runs available                                                                                | >= 95%                                                     |
| 4  | Cross-Project Query          | 10 canonical queries SQL-vs-Python match, **0 trivially-zero rows allowed**                                   | 10/10 with non-trivial Q4 + Q9                             |
| 5  | Web UI E2E                   | 5 reviewer flows + 3 new flows (upload, error, calibration view), p95 < 30s                                   | 8/8 pass                                                   |
| 6  | Recognition Quality          | weighted precision >= 0.85 AND recall >= 0.75, **of which >= 3 rules have instance-level recall**             | thresholds met + instance recall coverage                  |
| 7  | Real PDF Breadth             | >= 25 active real_public_pdf cases across >= 5 US states                                                      | 25+ active, 5+ states                                      |
| 8  | Calibration                  | MAD <= 0.04 AND >= 4 of 5 bins populated                                                                      | both                                                       |
| 9  | Feedback Loop                | synthetic-test monotone+predictable                                                                           | OK                                                         |
| 10 | Documentation Honesty        | READINESS + PILOT_QUICKSTART match measured artifact reality, 0 overclaim                                     | OK                                                         |
| 11 | **Pilot Readiness**          | `docker compose up` boots in < 60s; quickstart resolves all errors; first-time-user `archkg-pilot init` works | both                                                       |
| 12 | **Demo Video Quality**       | mp4 exists at agreed path; 3-5 min duration; 1080p; voiceover audible (>= -30 dB peak); captions every shot; honest limitations segment present | all checks pass + storyboard-vs-final diff small |

### Meta-rules (same as M5)

- Overall = `min(sum, weakest_dimension * 10) / 1.2` (12-dim normalisation).
- 99+ requires all 12 dims >= 9 AND at least 8 dims == 10.
- Test agent overrides any dim it cannot verify down to 0.
- Score regressions are blocking.

### Note on demo_video_quality

The test agent scores video as a **rubric checklist**, not a subjective
critique. It can verify:

- File exists at `.planning/m6/demo/archreview_kg_demo_final.mp4`.
- Duration in [180s, 360s] (3-6 min, with 5 min target).
- Resolution >= 1920x1080.
- Audio peak >= -30 dB, audio loudness >= -20 LUFS integrated.
- Storyboard JSON exists with 7+ shots, each with caption text.
- Each shot's timestamp range exists in the final video.
- At least one shot is explicitly labelled "limitations" or
  "honest residuals" in the storyboard.
- Voiceover script + TTS WAV files exist on disk.

What the agent **cannot** score: voiceover acting quality, motion
graphics polish, brand identity. Those are subjective. The agent will
abstain (score the rubric checklist, not the art).

## Exit gate for M6

1. Test-agent reports overall >= 99 across two consecutive runs on
   different days.
2. demo_video_quality == 10 AND pilot_readiness == 10.
3. Pre-M6 tests (527) still pass; new tests added for M6.A/B/D/E pass.
4. CHANGELOG + ROADMAP marked M6 complete with `quality_score.json`
   and the mp4 committed (or stored under .planning/m6/demo/ with
   path documented in CHANGELOG).
5. The promo video is watchable end-to-end without manual seeking.

## Process discipline

- No new handoff bundle navigation fields. P78-P85 freeze still holds.
- Commit prefix: `feat(M6.W?-NN): <summary>` with footer `confidence: low|med|high`.
- Atomic commits; no batching.
- All 527+ pre-M6 tests must continue to pass.

## Risk register

| Risk                                                  | Mitigation                                                                                              |
|-------------------------------------------------------|---------------------------------------------------------------------------------------------------------|
| TTS quality is mediocre (`say` is dated)              | Pick best voice (Samantha en_US); use ~220 wpm; accept honest "AI-narrated" framing in the closing card |
| Cross-state PDF sourcing hits paywalls                | Stop honestly at whatever count is achievable; document attempts                                         |
| Real per-instance labelling is slow                   | Cap at 90-120 labels; document partial coverage in instance_label provenance                            |
| Web UI polish creep                                   | Hard cap: 1 design pass, no theming UI, no admin panels                                                  |
| Docker compose hits OS-specific issues                | Test on darwin only; document in PILOT_QUICKSTART; arm64 only                                            |
| Video render fails on large input files               | Render at 720p first as sanity check, then 1080p; commit smaller proxy if size becomes an issue          |
| ffmpeg version drift between runs                     | Pin in CHANGELOG; reproducible via `make demo-video`                                                     |
| **Scope inflation**                                   | Hard cap each wave at ~1 day equivalent; if a wave is blowing past, write a note in M6-STATUS.md         |

## Out of scope for M6

- Real authentication / multi-user / cloud hosting.
- Government permit issuance language anywhere.
- ML-based recognizer rewrite.
- Notion / external integrations.
- Mobile UI.
- Music licensing (use synthesised ambient or none).

## Demo video storyboard (skeleton — fleshed out in M6.E)

```
SHOT 1 (0:00-0:20)   Title card + tagline
SHOT 2 (0:20-0:50)   Problem framing: drawing review is manual, error-prone
SHOT 3 (0:50-1:30)   Upload a real PDF; recognition pass runs; entities surface
SHOT 4 (1:30-2:10)   Issue lifecycle: candidate → reviewer confirms/rejects
SHOT 5 (2:10-2:50)   Quality story: per-rule precision/recall, calibration, KG queries
SHOT 6 (2:50-3:30)   Pilot deployment: `docker compose up`, the 30-minute path
SHOT 7 (3:30-4:00)   Honest limitations + roadmap (over-detection, sourcing gaps, M7+)
SHOT 8 (4:00-4:30)   Closing: contact / repo URL / "AI-narrated" disclosure
```

Adjust as needed during M6.E; the test agent verifies whatever
storyboard the project actually commits to.
