# ArchReview-KG Pilot Quickstart

> 5 minutes from clone to running review UI on your laptop.
> Pilot tier only — single-evaluator, local SQLite, no authentication.

## Prerequisites

- Python 3.11+
- ~600 MB disk for source + sample suite
- macOS / Linux (Windows: untested as of M6)
- Optional: Docker if you prefer `docker compose up`

## Path A — native install (recommended for evaluators)

```bash
git clone <repo> archreview-kg
cd archreview-kg
python -m venv .venv && source .venv/bin/activate
pip install -e .
bin/archkg-pilot init
```

`init` runs:
1. `archkg kg init` — creates `.archkg/kg.db`
2. `archkg kg ingest-suite` — loads the bundled benchmark sample bundle
3. `archkg kg serve` — boots the Flask web UI on `http://127.0.0.1:8765`
4. opens the browser to that URL (macOS `open` command)

If your shell does not have the venv on PATH, run `bin/archkg-pilot start`
again later from any cwd; the script resolves the repo root via git.

## Path B — docker compose

```bash
git clone <repo> archreview-kg
cd archreview-kg
docker compose up -d
open http://127.0.0.1:8765
```

The compose file mounts `./.archkg` so the SQLite KG persists on the host
filesystem. `docker compose down` stops cleanly.

## Verifying the install

```bash
bin/archkg-pilot doctor
```

Expected output: python version, archkg help line, KG file present, ffmpeg
present (needed for M6 demo render), port 8765 status.

## Running your first review

```bash
.venv/bin/python -m archkg.cli.main review samples/sample_clean.pdf -o out
.venv/bin/python -m archkg.cli.main kg ingest out --project my-first-review
```

The first command produces an annotated PDF + issue list. The second pulls
the run into the KG so the web UI shows it under "my-first-review".

## Health checks

```bash
.venv/bin/python -m archkg.cli.main kg status        # schema, table counts, p95 query time
.venv/bin/python -m archkg.cli.main kg quality       # per-rule precision / recall
.venv/bin/python -m archkg.cli.main kg calibration   # confidence vs observed precision
.venv/bin/python -m archkg.cli.main quality-score    # overall 12-dim score
```

## Troubleshooting

- **Port 8765 already in use**: `ARCHKG_PORT=8766 bin/archkg-pilot start`.
- **KG database locked**: another process holds it; `bin/archkg-pilot stop`
  then retry.
- **Sample suite ingest fails**: run `.venv/bin/python -m archkg.cli.main kg
  ingest-suite` and read the stderr — usually a missing `drawing_understanding.json`
  in a run directory. Add the file or omit the case.

## What this pilot does not do

- No authentication, no multi-tenant, no cloud sync.
- No production-grade error recovery; recoverable from `bin/archkg-pilot stop`
  + restart.
- AI / LLM advisor features are not exposed in the pilot; the recogniser is
  rule-based and CFR/GB-clause-driven.
- See `.planning/M6-BLUEPRINT.md` "Out of scope for M6" for the full list.
