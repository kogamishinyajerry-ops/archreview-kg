# ArchReview-KG Pilot Quickstart

> 5 minutes from clone to running review UI on your laptop.
> Pilot tier only — single-evaluator, local SQLite, no auth.

## Prerequisites
- Python 3.11+, ~600 MB disk, macOS/Linux (Windows untested as of M6)
- Optional: Docker if you prefer `docker compose up`

## Path A — native install (recommended)
```bash
git clone <repo> archreview-kg
cd archreview-kg
python -m venv .venv && source .venv/bin/activate
pip install -e .
bin/archkg-pilot init
```
`init` runs: `archkg kg init` → `archkg kg ingest-suite` → `archkg kg serve`
on `http://127.0.0.1:8765` and opens the browser. Re-run `bin/archkg-pilot
start` from any cwd later — the script resolves the repo root via git.

## Path B — docker compose
```bash
git clone <repo> archreview-kg
cd archreview-kg
docker compose up -d
open http://127.0.0.1:8765
```
The compose file mounts `./.archkg` so the SQLite KG persists on the host.
`docker compose down` stops cleanly.

## Verifying the install
```bash
bin/archkg-pilot doctor
```
Reports python version, archkg help, KG file present, ffmpeg present
(needed for M6 demo render), port 8765 status.

## Running your first review
```bash
.venv/bin/python -m archkg.cli.main review samples/sample_clean.pdf -o out
.venv/bin/python -m archkg.cli.main kg ingest out --project my-first-review
```
First command produces an annotated PDF + issue list; second pulls the run
into the KG so the web UI lists it under `my-first-review`.

## Health checks
```bash
.venv/bin/python -m archkg.cli.main kg status        # schema, counts, p95
.venv/bin/python -m archkg.cli.main kg quality       # per-rule P/R
.venv/bin/python -m archkg.cli.main kg calibration   # confidence calibration
.venv/bin/python -m archkg.cli.main quality-score    # overall 12-dim score
```

## Troubleshooting
- **Port 8765 busy**: `ARCHKG_PORT=8766 bin/archkg-pilot start`.
- **KG locked**: `bin/archkg-pilot stop` then retry.
- **Ingest fails**: re-run `archkg kg ingest-suite` and read stderr;
  usually a missing `drawing_understanding.json` in a run dir.

## What this pilot does not do
- No auth, no multi-tenant, no cloud sync, no production error recovery.
- AI / LLM advisor features not exposed; recogniser is rule-based
  (CFR / GB clause-driven). Full out-of-scope list: `.planning/M6-BLUEPRINT.md`.
