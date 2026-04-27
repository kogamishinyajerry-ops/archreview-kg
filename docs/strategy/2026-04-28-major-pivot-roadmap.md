# Major Pivot Roadmap: Evidence-First Intelligent Plan Review

Date: 2026-04-28

This document is the human-facing companion to `.planning/`. It summarizes the post-P32 strategy shift.

## Pivot Summary

ArchReview-KG should now optimize for trustworthy review readiness before broader automatic compliance.

The new mainline is:

```plain text
Sheet/source classification
  -> component evidence inventory
  -> rule input readiness
  -> rule execution only where inputs are ready
  -> reviewable issue lifecycle
  -> feedback, rerun, benchmark expansion
```

## What Changes

Old emphasis:

- More rule cards.
- More automatic detections.
- More direct end-to-end review claims.

New emphasis:

- Which evidence exists.
- Which evidence is missing.
- Which rules are runnable.
- Which findings are only candidates.
- Which review states have been confirmed by a human.
- Which open standards can be reused.

## Development Pillars

1. Runtime Readiness
   - Every review run writes rule readiness.
   - Missing input is never treated as pass.

2. Source Classification
   - Design region, title block, schedule, legend, detail/callout, and noise are separate sources.
   - Candidate crop suggestions are visible and reviewable.

3. Benchmark Discipline
   - Real drawings require reviewed expected inventory.
   - Generated fixtures remain useful but cannot prove real readiness.

4. Issue Lifecycle
   - Rule engine emits candidates.
   - Humans confirm, reject, resolve, or request more information.

5. OpenBIM Side Lane
   - IFC/IDS support should reuse IfcOpenShell/IfcTester.
   - PDF graph extraction and IFC validation remain independent until integration is justified.

6. Assistant-Only AI
   - AI can draft rule cards, citations, region guesses, and review notes.
   - AI cannot directly create final violations or benchmark ground truth.

## Immediate Implementation Order

1. P33 rule-input readiness dashboard.
2. P34 sheet-region candidate suggestions.
3. P35 issue lifecycle and review state.
4. P36 IFC/IDS side lane spike.
5. P37 rule-card authoring/citation assistant.

## Acceptance Bar

A phase is complete only when:

- Its artifact is committed to the repo.
- Tests cover the main contract.
- The readiness/readme/changelog surface is updated if the user-facing story changes.
- Notion is updated as a mirror with commit and validation.

## Agent Contract v3

GPT-5.5-xhigh owns:

- Strategy, architecture, phase sequencing, risk gates, and acceptance standards.

codex-5.3-spark owns:

- Small bounded execution slices with clear file ownership.
- Fixture and test expansion.
- Mechanical documentation sync.
- It must not rewrite architecture, alter rule-engine semantics, or promote AI output to active truth.

Current Codex owns:

- Main local implementation.
- Verification.
- Commit hygiene.
- Notion mirror sync.
