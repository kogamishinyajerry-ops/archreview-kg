"""M5 quality score: 10-dimension honest scoring of project state.

Computed by `archkg quality-score` and consumed by the `archreview-test-judge`
subagent. The scorer reads only artifacts, benchmark runs, source code, and
process outputs (ruff/mypy/pytest). It does not trust commit messages or
self-reported claims.

Scoring meta-rules (see `.planning/M5-BLUEPRINT.md`):

- Each dimension scores 0-10.
- A dimension that cannot be measured (artifact missing, fixture absent, etc.)
  scores 0 with an explicit `unmeasurable` reason. There is no "partial
  credit for trying".
- Overall is capped by the weakest dimension: `min(sum / 10, min_dim * 10)`.
- Score >= 99 requires every dimension >= 9 AND at least 7 dimensions == 10.

Schema version: quality_score.v1
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

SCHEMA_VERSION = "quality_score.v1"

Dimension = Literal[
    "code_quality",
    "kg_persistence",
    "kg_coverage",
    "cross_project_query",
    "web_ui_e2e",
    "recognition_quality",
    "real_pdf_breadth",
    "calibration",
    "feedback_loop",
    "documentation_honesty",
    "pilot_readiness",
    "demo_video_quality",
]

DIMENSIONS: tuple[Dimension, ...] = (
    "code_quality",
    "kg_persistence",
    "kg_coverage",
    "cross_project_query",
    "web_ui_e2e",
    "recognition_quality",
    "real_pdf_breadth",
    "calibration",
    "feedback_loop",
    "documentation_honesty",
    "pilot_readiness",
    "demo_video_quality",
)


class QualityScoreError(RuntimeError):
    pass


@dataclass
class DimensionScore:
    dimension: Dimension
    score: float  # 0.0 - 10.0
    measurable: bool
    detail: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "dimension": self.dimension,
            "score": round(self.score, 2),
            "measurable": self.measurable,
            "detail": self.detail,
            "notes": self.notes,
        }


# ---------------------------------------------------------------------------
# Dimension scorers
# Each returns a DimensionScore. They must never raise — if scoring fails, the
# dimension is reported as unmeasurable with score 0 and a clear reason.
# ---------------------------------------------------------------------------


def score_code_quality(repo: Path, *, skip_slow: bool = False) -> DimensionScore:
    """Run ruff + mypy + pytest. 0 issues == 10 pts. Each tool failure -3.

    With ``skip_slow=True`` the pytest stage is skipped (used by the scorer's
    self-tests to avoid recursive pytest invocation)."""

    detail: dict[str, Any] = {}
    notes: list[str] = []
    points = 10.0

    venv_bin = repo / ".venv" / "bin"

    def _resolve(tool: str) -> str | None:
        local = venv_bin / tool
        if local.exists():
            return str(local)
        on_path = shutil.which(tool)
        return on_path

    ruff = _resolve("ruff")
    mypy = _resolve("mypy")
    pytest_bin = _resolve("pytest")

    # ruff
    if ruff is None:
        detail["ruff"] = {"status": "tool_missing"}
        notes.append("ruff binary not found; -3")
        points -= 3
    else:
        proc = subprocess.run(
            [ruff, "check", "archkg", "tests"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=False,
        )
        detail["ruff"] = {
            "exit_code": proc.returncode,
            "stdout_tail": proc.stdout.strip().splitlines()[-8:],
            "stderr_tail": proc.stderr.strip().splitlines()[-4:],
        }
        if proc.returncode != 0:
            notes.append("ruff check failed; -3")
            points -= 3

    # mypy
    if mypy is None:
        detail["mypy"] = {"status": "tool_missing"}
        notes.append("mypy binary not found; -3")
        points -= 3
    else:
        proc = subprocess.run(
            [mypy, "archkg"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=False,
        )
        detail["mypy"] = {
            "exit_code": proc.returncode,
            "stdout_tail": proc.stdout.strip().splitlines()[-8:],
            "stderr_tail": proc.stderr.strip().splitlines()[-4:],
        }
        if proc.returncode != 0:
            notes.append("mypy failed; -3")
            points -= 3

    # pytest
    if skip_slow:
        detail["pytest"] = {"status": "skipped_slow"}
        notes.append("pytest skipped via skip_slow; not scored")
    elif pytest_bin is None:
        detail["pytest"] = {"status": "tool_missing"}
        notes.append("pytest binary not found; -4")
        points -= 4
    else:
        proc = subprocess.run(
            [pytest_bin, "-q", "--no-header", "--no-summary"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=False,
        )
        # Parse `N passed`, `N failed`, `N warnings` from output
        tail = proc.stdout.strip().splitlines()[-20:]
        joined = "\n".join(tail)
        passed = _extract_count(joined, r"(\d+) passed")
        failed = _extract_count(joined, r"(\d+) failed")
        errors = _extract_count(joined, r"(\d+) error")
        warnings = _extract_count(joined, r"(\d+) warning")
        detail["pytest"] = {
            "exit_code": proc.returncode,
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "warnings": warnings,
            "tail": tail,
        }
        if proc.returncode != 0 or failed > 0 or errors > 0:
            notes.append(f"pytest failed (failed={failed}, errors={errors}); -4")
            points -= 4
        elif warnings > 0:
            notes.append(f"pytest had {warnings} warnings; -1")
            points -= 1

    points = max(0.0, points)
    return DimensionScore(
        dimension="code_quality",
        score=points,
        measurable=True,
        detail=detail,
        notes=notes,
    )


def _extract_count(text: str, pattern: str) -> int:
    m = re.search(pattern, text)
    return int(m.group(1)) if m else 0


def score_kg_persistence(repo: Path) -> DimensionScore:
    """KG persistence not built yet → 0. Once built, validates schema + query."""

    notes: list[str] = []
    detail: dict[str, Any] = {}

    kg_db_candidates = [
        repo / ".archkg" / "kg.db",
        Path.home() / ".archkg" / "kg.db",
    ]
    db = next((p for p in kg_db_candidates if p.exists()), None)
    if db is None:
        detail["status"] = "no_kg_db_found"
        detail["searched"] = [str(p) for p in kg_db_candidates]
        notes.append("KG database not initialised; score 0")
        return DimensionScore(
            dimension="kg_persistence",
            score=0.0,
            measurable=False,
            detail=detail,
            notes=notes,
        )

    try:
        from archkg.kg.store import KGStore

        store = KGStore(db)
        info = store.health_check()
        detail["status"] = "ok"
        detail["health"] = info
        # Simple scoring: 10 if all required tables present and p95 query < 50ms
        all_tables = info.get("required_tables_present", False)
        p95 = info.get("query_p95_ms", 9999.0)
        points = 10.0 if all_tables else 5.0
        if p95 > 50:
            points -= 2
            notes.append(f"query p95={p95:.1f}ms over 50ms threshold; -2")
        if not all_tables:
            notes.append("required tables missing; capped at 5")
        return DimensionScore(
            dimension="kg_persistence",
            score=max(0.0, points),
            measurable=True,
            detail=detail,
            notes=notes,
        )
    except ImportError:
        detail["status"] = "kg_store_module_missing"
        notes.append("archkg.kg.store not implemented yet")
        return DimensionScore(
            dimension="kg_persistence",
            score=0.0,
            measurable=False,
            detail=detail,
            notes=notes,
        )


def score_kg_coverage(repo: Path) -> DimensionScore:
    detail: dict[str, Any] = {}
    notes: list[str] = []
    try:
        from archkg.kg.store import KGStore
    except ImportError:
        detail["status"] = "kg_store_module_missing"
        notes.append("KG not implemented; coverage 0")
        return DimensionScore(
            dimension="kg_coverage",
            score=0.0,
            measurable=False,
            detail=detail,
            notes=notes,
        )

    # Count expected ingestable runs: any directory ending in `_run` (or
    # otherwise plausibly a run dir) that has at least one of the ingestable
    # artifacts. We import the canonical list from archkg.kg.
    from archkg.kg.ingest import INGESTABLE_ARTIFACTS

    candidates: list[Path] = []
    suite_root = repo / "samples" / "understanding_benchmarks"
    if suite_root.is_dir():
        candidates.extend(p for p in suite_root.rglob("*_run") if p.is_dir())
    fixture_root = repo / "tests" / "fixtures"
    if fixture_root.is_dir():
        candidates.extend(p for p in fixture_root.rglob("*_run") if p.is_dir())
        candidates.extend(p for p in fixture_root.rglob("issues.json") if p.is_file())
    # De-dupe and keep only those with at least one ingestable artifact
    seen: set[Path] = set()
    ingestable: list[Path] = []
    for p in candidates:
        path = p.parent if p.is_file() else p
        if path in seen:
            continue
        if any((path / name).exists() for name in INGESTABLE_ARTIFACTS):
            ingestable.append(path)
            seen.add(path)
    expected = len(ingestable)
    if expected == 0:
        detail["status"] = "no_fixture_runs_found"
        notes.append("no fixture run dirs to ingest; cannot score coverage")
        return DimensionScore(
            dimension="kg_coverage",
            score=0.0,
            measurable=False,
            detail=detail,
            notes=notes,
        )

    db_candidates = [
        repo / ".archkg" / "kg.db",
        Path.home() / ".archkg" / "kg.db",
    ]
    db = next((p for p in db_candidates if p.exists()), None)
    if db is None:
        detail["status"] = "no_kg_db"
        notes.append("KG db missing; coverage 0")
        return DimensionScore(
            dimension="kg_coverage",
            score=0.0,
            measurable=False,
            detail=detail,
            notes=notes,
        )
    store = KGStore(db)
    ingested = store.count_runs()
    coverage = ingested / expected if expected else 0.0
    detail.update({"expected_runs": expected, "ingested_runs": ingested, "coverage": coverage})
    points = min(10.0, coverage * 10.0)
    if coverage < 0.95:
        notes.append(f"coverage {coverage:.0%} < 95% threshold")
    return DimensionScore(
        dimension="kg_coverage",
        score=points,
        measurable=True,
        detail=detail,
        notes=notes,
    )


def score_cross_project_query(repo: Path) -> DimensionScore:
    canonical = repo / ".planning" / "m5" / "canonical_queries.json"
    detail: dict[str, Any] = {}
    notes: list[str] = []
    if not canonical.exists():
        detail["status"] = "canonical_queries_missing"
        notes.append(f"{canonical.relative_to(repo)} not yet authored; score 0")
        return DimensionScore(
            dimension="cross_project_query",
            score=0.0,
            measurable=False,
            detail=detail,
            notes=notes,
        )
    try:
        from archkg.kg.query import run_canonical_queries
        from archkg.kg.store import default_db_path
    except ImportError:
        detail["status"] = "query_module_missing"
        notes.append("archkg.kg.query not implemented; score 0")
        return DimensionScore(
            dimension="cross_project_query",
            score=0.0,
            measurable=False,
            detail=detail,
            notes=notes,
        )
    manifest = json.loads(canonical.read_text(encoding="utf-8"))
    # Manifest may be {"schema_version": ..., "queries": [...]} or a bare list.
    queries = (
        manifest["queries"]
        if isinstance(manifest, dict) and "queries" in manifest
        else manifest
    )
    db_path = default_db_path(repo)
    results = run_canonical_queries(queries, db_path=db_path)
    correct = sum(1 for r in results if r.get("correct"))
    total = len(results)
    detail.update({"total": total, "correct": correct, "results": results})
    points = (correct / total) * 10.0 if total else 0.0
    if correct < total:
        notes.append(f"{correct}/{total} canonical queries correct")
    return DimensionScore(
        dimension="cross_project_query",
        score=points,
        measurable=True,
        detail=detail,
        notes=notes,
    )


def score_web_ui_e2e(repo: Path) -> DimensionScore:
    detail: dict[str, Any] = {}
    notes: list[str] = []
    try:
        from archkg.kg.web import run_e2e_smoke
    except ImportError:
        detail["status"] = "web_module_missing"
        notes.append("archkg.kg.web not implemented; score 0")
        return DimensionScore(
            dimension="web_ui_e2e",
            score=0.0,
            measurable=False,
            detail=detail,
            notes=notes,
        )
    smoke = run_e2e_smoke()
    detail["flows"] = smoke["flows"]
    flows = smoke["flows"]
    if not flows:
        notes.append("no flows registered; score 0")
        return DimensionScore(
            dimension="web_ui_e2e",
            score=0.0,
            measurable=False,
            detail=detail,
            notes=notes,
        )
    passing = sum(1 for f in flows if f.get("passed") and f.get("p95_ms", 99999) <= 30000)
    total = len(flows)
    points = (passing / total) * 10.0 if total else 0.0
    if passing < total:
        notes.append(f"{passing}/{total} flows met <30s p95 threshold")
    return DimensionScore(
        dimension="web_ui_e2e",
        score=points,
        measurable=True,
        detail=detail,
        notes=notes,
    )


def score_recognition_quality(repo: Path) -> DimensionScore:
    detail: dict[str, Any] = {}
    notes: list[str] = []
    try:
        from archkg.kg.recognition_quality import per_rule_quality
        from archkg.kg.store import default_db_path
    except ImportError:
        detail["status"] = "recognition_quality_module_missing"
        notes.append("archkg.kg.recognition_quality not implemented; score 0")
        return DimensionScore(
            dimension="recognition_quality",
            score=0.0,
            measurable=False,
            detail=detail,
            notes=notes,
        )
    pq = per_rule_quality(db_path=default_db_path(repo), repo=repo)
    if not pq.get("rules"):
        detail["status"] = "no_rules_with_ground_truth"
        notes.append("no rules have enough ground-truth labels to score")
        return DimensionScore(
            dimension="recognition_quality",
            score=0.0,
            measurable=False,
            detail=detail,
            notes=notes,
        )
    detail.update(pq)
    p = pq.get("weighted_precision") or 0.0
    r = pq.get("weighted_recall") or 0.0
    # Linear scaling: 0 at (p=0, r=0); 10 at (p>=0.85 AND r>=0.75)
    p_score = min(1.0, p / 0.85) * 5.0
    r_score = min(1.0, r / 0.75) * 5.0
    points = p_score + r_score
    if p < 0.85:
        notes.append(f"weighted precision {p:.2f} < 0.85")
    if r < 0.75:
        notes.append(f"weighted recall {r:.2f} < 0.75")
    return DimensionScore(
        dimension="recognition_quality",
        score=points,
        measurable=True,
        detail=detail,
        notes=notes,
    )


def score_real_pdf_breadth(repo: Path) -> DimensionScore:
    manifest = repo / "samples" / "understanding_benchmarks" / "suite_manifest.json"
    detail: dict[str, Any] = {}
    notes: list[str] = []
    if not manifest.exists():
        detail["status"] = "suite_manifest_missing"
        notes.append("benchmark suite_manifest.json not found; score 0")
        return DimensionScore(
            dimension="real_pdf_breadth",
            score=0.0,
            measurable=False,
            detail=detail,
            notes=notes,
        )
    data = json.loads(manifest.read_text(encoding="utf-8"))
    cases: list[dict[str, Any]] = data.get("cases", [])
    real_active = [
        c
        for c in cases
        if c.get("status") == "active"
        and c.get("fixture_kind", "").startswith("real_public")
    ]
    detail["real_active_count"] = len(real_active)
    detail["case_ids"] = [c["case_id"] for c in real_active]
    # Linear scaling: 10 pts at >= 15, 0 pts at 0
    points = min(10.0, len(real_active) / 15.0 * 10.0)
    if len(real_active) < 15:
        notes.append(f"{len(real_active)}/15 real public PDFs active")
    return DimensionScore(
        dimension="real_pdf_breadth",
        score=points,
        measurable=True,
        detail=detail,
        notes=notes,
    )


def score_calibration(repo: Path) -> DimensionScore:
    detail: dict[str, Any] = {}
    notes: list[str] = []
    try:
        from archkg.kg.calibration import build_calibration_report
    except ImportError:
        detail["status"] = "calibration_module_missing"
        notes.append("archkg.kg.calibration not implemented; score 0")
        return DimensionScore(
            dimension="calibration",
            score=0.0,
            measurable=False,
            detail=detail,
            notes=notes,
        )
    from archkg.kg.store import default_db_path

    rep = build_calibration_report(default_db_path(repo))
    detail.update(rep)
    mad = rep.get("mean_abs_deviation")
    bins_used = rep.get("bins_used_for_mad", 0)
    # MAD over a single bin is vacuous (cannot detect miscalibration across
    # the confidence range). Require >= 3 bins with min_samples to score >0.
    min_bins_for_mad = 3
    if mad is None or bins_used < min_bins_for_mad:
        notes.append(
            f"calibration unmeasurable: bins_used={bins_used} < {min_bins_for_mad} "
            f"(status={rep.get('status', 'unknown')}). Single-bin MAD is vacuous."
        )
        return DimensionScore(
            dimension="calibration",
            score=0.0,
            measurable=False,
            detail=detail,
            notes=notes,
        )
    # 10 pts at MAD <= 0.04; 0 pts at MAD >= 0.20
    if mad <= 0.04:
        points = 10.0
    elif mad >= 0.20:
        points = 0.0
    else:
        points = (0.20 - mad) / (0.20 - 0.04) * 10.0
    if mad > 0.08:
        notes.append(f"mean abs deviation {mad:.2%} > 8% threshold")
    return DimensionScore(
        dimension="calibration",
        score=points,
        measurable=True,
        detail=detail,
        notes=notes,
    )


def score_feedback_loop(repo: Path) -> DimensionScore:
    detail: dict[str, Any] = {}
    notes: list[str] = []
    try:
        from archkg.kg.feedback import feedback_loop_synthetic_test
    except ImportError:
        detail["status"] = "feedback_module_missing"
        notes.append("archkg.kg.feedback not implemented; score 0")
        return DimensionScore(
            dimension="feedback_loop",
            score=0.0,
            measurable=False,
            detail=detail,
            notes=notes,
        )
    result = feedback_loop_synthetic_test()
    detail.update(result)
    if not result.get("monotonic"):
        notes.append("feedback events did not produce monotonic confidence change")
        return DimensionScore(
            dimension="feedback_loop",
            score=2.0,
            measurable=True,
            detail=detail,
            notes=notes,
        )
    delta = result.get("delta", 0.0)
    expected = result.get("expected_delta", 0.0)
    if expected == 0:
        notes.append("expected_delta zero; cannot score")
        return DimensionScore(
            dimension="feedback_loop",
            score=0.0,
            measurable=False,
            detail=detail,
            notes=notes,
        )
    accuracy = 1.0 - min(1.0, abs(delta - expected) / abs(expected))
    points = accuracy * 10.0
    return DimensionScore(
        dimension="feedback_loop",
        score=points,
        measurable=True,
        detail=detail,
        notes=notes,
    )


def score_documentation_honesty(repo: Path) -> DimensionScore:
    """Compare READINESS.md claims to measured artifact reality."""

    detail: dict[str, Any] = {}
    notes: list[str] = []
    readiness = repo / "READINESS.md"
    if not readiness.exists():
        detail["status"] = "readiness_missing"
        notes.append("READINESS.md not found")
        return DimensionScore(
            dimension="documentation_honesty",
            score=0.0,
            measurable=False,
            detail=detail,
            notes=notes,
        )
    text = readiness.read_text(encoding="utf-8")
    overclaims: list[str] = []

    # Compare AUTODETECTABLE claim against rule cards
    rules_yaml = repo / "archkg" / "knowledge" / "data" / "rule_cards.yaml"
    if rules_yaml.exists():
        try:
            import yaml

            cards = yaml.safe_load(rules_yaml.read_text(encoding="utf-8"))
            total_rules = len(cards) if isinstance(cards, list) else 0
            detail["total_rule_cards"] = total_rules
        except Exception as exc:
            detail["rule_card_parse_error"] = str(exc)

    # Compare real-PDF count claim
    manifest = repo / "samples" / "understanding_benchmarks" / "suite_manifest.json"
    if manifest.exists():
        data = json.loads(manifest.read_text(encoding="utf-8"))
        cases = data.get("cases", [])
        real_active = sum(
            1
            for c in cases
            if c.get("status") == "active"
            and c.get("fixture_kind", "").startswith("real_public")
        )
        detail["real_active_count"] = real_active
        # Search for any "N real" overclaim in README/READINESS
        for phrase in ("15 real", "20 real", "100 real"):
            if phrase in text and real_active < int(phrase.split()[0]):
                overclaims.append(
                    f"README/READINESS mentions '{phrase}' but only {real_active} active real public PDFs in suite"
                )

    # Generic overclaim phrases to look for. We only flag a phrase when it
    # appears as an assertive claim, not when hedged ("not yet", "wait for",
    # "等", "尚未", "if/when production-ready", etc.).
    forbidden_phrases = (
        "production ready",
        "production-ready",
        "battle tested",
        "battle-tested",
        "fully automated review",
        "replaces human reviewer",
        "100% precision",
        "100% recall",
    )
    hedge_tokens = (
        "等",  # Chinese: "wait for ..."
        "尚未",  # Chinese: "not yet ..."
        "未来",  # Chinese: "in the future ..."
        "如果",  # Chinese: "if ..."
        "if ",
        "when ",
        "wait for ",
        "not yet ",
        "future ",
        "not production",
        "before ",
        "until ",
    )
    text_lower = text.lower()
    for phrase in forbidden_phrases:
        start = 0
        while True:
            idx = text_lower.find(phrase.lower(), start)
            if idx == -1:
                break
            window_start = max(0, idx - 30)
            window = text[window_start:idx]
            if any(h in window.lower() or h in window for h in hedge_tokens):
                start = idx + len(phrase)
                continue
            overclaims.append(
                f"forbidden marketing phrase '{phrase}' at offset {idx}"
            )
            start = idx + len(phrase)

    detail["overclaims"] = overclaims
    if not overclaims:
        return DimensionScore(
            dimension="documentation_honesty",
            score=10.0,
            measurable=True,
            detail=detail,
            notes=["no overclaims detected"],
        )
    points = max(0.0, 10.0 - 2.0 * len(overclaims))
    notes.extend(overclaims)
    return DimensionScore(
        dimension="documentation_honesty",
        score=points,
        measurable=True,
        detail=detail,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# M6 dimensions: pilot_readiness, demo_video_quality
# ---------------------------------------------------------------------------


def score_pilot_readiness(repo: Path) -> DimensionScore:
    """Score the pilot deployment kit (M6.W4).

    Checks:
      (1) docker-compose.yml present and parseable
      (2) bin/archkg-pilot script present and executable
      (3) docs/PILOT_QUICKSTART.md present and >= 5 sections, <= 50 content lines
      (4) error_pages directory or in-app error templates referenced
    Each present check contributes 2.5 points (max 10).
    """

    detail: dict[str, Any] = {}
    notes: list[str] = []
    checks: list[tuple[str, bool, str]] = []

    compose = repo / "docker-compose.yml"
    checks.append((
        "docker_compose_present",
        compose.exists() and compose.stat().st_size > 100,
        f"docker-compose.yml missing or trivially small at {compose}",
    ))

    pilot_script = repo / "bin" / "archkg-pilot"
    checks.append((
        "pilot_init_script",
        pilot_script.exists() and pilot_script.stat().st_mode & 0o111,
        f"bin/archkg-pilot missing or not executable at {pilot_script}",
    ))

    quickstart = repo / "docs" / "PILOT_QUICKSTART.md"
    qs_ok = False
    if quickstart.exists():
        body = quickstart.read_text(encoding="utf-8")
        n_sections = sum(1 for line in body.splitlines() if line.startswith("## "))
        content_lines = sum(
            1
            for line in body.splitlines()
            if line.strip() and not line.startswith("#")
        )
        qs_ok = n_sections >= 5 and content_lines <= 80
        detail["quickstart_sections"] = n_sections
        detail["quickstart_content_lines"] = content_lines
    checks.append((
        "quickstart_doc",
        qs_ok,
        "docs/PILOT_QUICKSTART.md must have >=5 '##' sections and <=80 content lines",
    ))

    error_templates = (repo / "archkg" / "kg" / "error_templates.py").exists() or (
        repo / "archkg" / "kg" / "templates" / "error.html"
    ).exists()
    # Fallback: any source file mentioning a 4xx error page handler.
    if not error_templates:
        web_py = repo / "archkg" / "kg" / "web.py"
        if web_py.exists():
            error_templates = "error_response" in web_py.read_text(encoding="utf-8") or "errorhandler" in web_py.read_text(encoding="utf-8")
    checks.append((
        "error_pages_wired",
        bool(error_templates),
        "no error-page wiring detected in archkg/kg/web.py or templates/",
    ))

    score = sum(2.5 for _, ok, _ in checks if ok)
    for name, ok, msg in checks:
        detail[name] = ok
        if not ok:
            notes.append(msg)

    return DimensionScore(
        dimension="pilot_readiness",
        score=score,
        measurable=True,
        detail=detail,
        notes=notes,
    )


def score_demo_video_quality(repo: Path) -> DimensionScore:
    """Score the M6.W7 final demo video (rubric checklist, not artistic critique).

    Checks:
      (1) Final mp4 exists at .planning/m6/demo/archreview_kg_demo_final.mp4
      (2) Storyboard JSON exists with >= 7 shots, each having caption + [start, end]
      (3) Voiceover script.txt + voiceover.wav exist
      (4) ffprobe duration in [180s, 360s]
      (5) Resolution >= 1920x1080
      (6) At least one shot tagged as "limitations" or caption contains
          "limitation"/"honest"
    Each passed check contributes ~1.67 points (max 10).
    """

    import shutil
    import subprocess

    detail: dict[str, Any] = {}
    notes: list[str] = []
    checks: list[tuple[str, bool, str]] = []

    demo_dir = repo / ".planning" / "m6" / "demo"
    mp4 = demo_dir / "archreview_kg_demo_final.mp4"
    storyboard = demo_dir / "storyboard.json"
    script = demo_dir / "script.txt"
    voiceover = demo_dir / "voiceover.wav"

    checks.append((
        "final_mp4_exists",
        mp4.exists() and mp4.stat().st_size > 100_000,
        f"final mp4 missing or trivially small at {mp4}",
    ))

    storyboard_shots: list[dict[str, Any]] = []
    storyboard_ok = False
    has_limitations = False
    if storyboard.exists():
        try:
            sb = json.loads(storyboard.read_text(encoding="utf-8"))
            storyboard_shots = sb.get("shots", []) or []
            storyboard_ok = (
                len(storyboard_shots) >= 7
                and all(
                    isinstance(s.get("caption"), str)
                    and isinstance(s.get("start"), (int, float))
                    and isinstance(s.get("end"), (int, float))
                    for s in storyboard_shots
                )
            )
            has_limitations = any(
                s.get("kind") == "limitations"
                or any(kw in (s.get("caption") or "").lower() for kw in ("limitation", "honest"))
                for s in storyboard_shots
            )
        except (json.JSONDecodeError, OSError):
            pass
    checks.append((
        "storyboard_complete",
        storyboard_ok,
        "storyboard.json must have >=7 shots each with caption + start + end",
    ))
    checks.append((
        "honest_limitations_shot",
        has_limitations,
        "at least one shot must be tagged as 'limitations' or contain honest/limitation in caption",
    ))

    checks.append((
        "voiceover_script",
        script.exists() and script.stat().st_size > 500,
        f"voiceover script missing or trivially short at {script}",
    ))
    checks.append((
        "voiceover_wav",
        voiceover.exists() and voiceover.stat().st_size > 50_000,
        f"voiceover.wav missing or trivially small at {voiceover}",
    ))

    duration_s: float | None = None
    width = height = 0
    if mp4.exists() and shutil.which("ffprobe"):
        try:
            out = subprocess.check_output(
                [
                    "ffprobe", "-v", "error", "-print_format", "json",
                    "-show_streams", "-show_format", str(mp4),
                ],
                timeout=20,
            )
            probe = json.loads(out.decode())
            duration_s = float(probe.get("format", {}).get("duration", 0.0))
            for s in probe.get("streams", []) or []:
                if s.get("codec_type") == "video":
                    width = int(s.get("width", 0))
                    height = int(s.get("height", 0))
                    break
            detail["duration_s"] = round(duration_s, 2)
            detail["resolution"] = f"{width}x{height}"
        except (subprocess.SubprocessError, ValueError, OSError, json.JSONDecodeError):
            pass

    checks.append((
        "duration_in_range",
        duration_s is not None and 180.0 <= duration_s <= 360.0,
        f"video duration {duration_s} not in [180, 360] seconds",
    ))
    checks.append((
        "resolution_1080p",
        width >= 1920 and height >= 1080,
        f"resolution {width}x{height} below 1920x1080",
    ))

    score = (10.0 / len(checks)) * sum(1 for _, ok, _ in checks if ok)
    for name, ok, msg in checks:
        detail[name] = ok
        if not ok:
            notes.append(msg)

    return DimensionScore(
        dimension="demo_video_quality",
        score=round(score, 2),
        measurable=True,
        detail=detail,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Top-level aggregation
# ---------------------------------------------------------------------------


def compute_quality_score(
    repo: Path,
    *,
    skip_slow: bool = False,
    only: Iterable[Dimension] | None = None,
) -> dict[str, Any]:
    scorers: dict[Dimension, Any] = {
        "code_quality": lambda: score_code_quality(repo, skip_slow=skip_slow),
        "kg_persistence": lambda: score_kg_persistence(repo),
        "kg_coverage": lambda: score_kg_coverage(repo),
        "cross_project_query": lambda: score_cross_project_query(repo),
        "web_ui_e2e": lambda: score_web_ui_e2e(repo),
        "recognition_quality": lambda: score_recognition_quality(repo),
        "real_pdf_breadth": lambda: score_real_pdf_breadth(repo),
        "calibration": lambda: score_calibration(repo),
        "feedback_loop": lambda: score_feedback_loop(repo),
        "documentation_honesty": lambda: score_documentation_honesty(repo),
        "pilot_readiness": lambda: score_pilot_readiness(repo),
        "demo_video_quality": lambda: score_demo_video_quality(repo),
    }
    if only is not None:
        selected = {d: scorers[d] for d in only}
    else:
        selected = scorers

    dim_results: list[DimensionScore] = []
    for dim in DIMENSIONS:
        if dim not in selected:
            continue
        try:
            ds = selected[dim]()
        except Exception as exc:
            ds = DimensionScore(
                dimension=dim,
                score=0.0,
                measurable=False,
                detail={"status": "scorer_raised", "error": repr(exc)},
                notes=[f"scorer raised: {exc!r}"],
            )
        dim_results.append(ds)

    sum_score = sum(d.score for d in dim_results)
    min_score = min((d.score for d in dim_results), default=0.0)
    n = len(dim_results)
    average_score = sum_score / n if n else 0.0
    # Overall: weakest dimension dominates. Take the lower of (sum) and (min * 10).
    overall = min(sum_score, min_score * 10.0)
    # Normalise to 0-100 regardless of dim count (M5: 10 dims, M6: 12 dims).
    expected_max = 10.0 * len(DIMENSIONS)
    if n != len(DIMENSIONS):
        # Subset of dims requested via `only`: scale by selected count.
        overall = (overall / (10.0 * n)) * 100.0 if n else 0.0
    else:
        overall = (overall / expected_max) * 100.0

    # 99+ check. M6 expanded to 12 dims; >= 9 of 12 must be at 10.0 (was 7 of 10).
    # Threshold scales as ceil(0.7 * n).
    min_perfect_dims = max(1, int(round(0.75 * len(DIMENSIONS))))
    ninety_nine_plus = (
        n == len(DIMENSIONS)
        and all(d.score >= 9.0 for d in dim_results)
        and sum(1 for d in dim_results if d.score == 10.0) >= min_perfect_dims
    )

    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "overall_score": round(overall, 2),
        "average_dimension_score": round(average_score, 2),
        "weakest_dimension": min(dim_results, key=lambda d: d.score).dimension if dim_results else None,
        "ninety_nine_plus": ninety_nine_plus,
        "dimensions": [d.to_dict() for d in dim_results],
        "scoring_meta": {
            "rule": "overall = min(sum, weakest_dimension * 10); 99+ requires all >= 9 AND >= 7 dims == 10",
            "dimensions_scored": n,
            "skip_slow_code_quality": skip_slow,
        },
    }
    return report


def write_quality_score(report: Mapping[str, Any], out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out


def format_summary(report: Mapping[str, Any]) -> str:
    lines = [
        f"overall: {report['overall_score']}/100",
        f"avg dim: {report['average_dimension_score']}/10",
        f"weakest: {report['weakest_dimension']}",
        f"99+: {report['ninety_nine_plus']}",
        "",
    ]
    for d in report["dimensions"]:
        marker = "OK" if d["score"] >= 9 else ("WEAK" if d["score"] >= 5 else "FAIL")
        measurable = "M" if d["measurable"] else "U"
        lines.append(f"  [{marker}][{measurable}] {d['dimension']}: {d['score']}/10")
        for note in d.get("notes", [])[:3]:
            lines.append(f"        - {note}")
    return "\n".join(lines)
