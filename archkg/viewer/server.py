"""Static, read-only demo viewer.

Spins up `python -m http.server` rooted at the run directory and opens
http://localhost:<port>/ in the default browser. The server only ever
streams files — there is no API, no rules editing, no DB. Strictly a
presentation layer over the existing artifacts.
"""

from __future__ import annotations

import functools
import http.server
import json
import shutil
import socketserver
import threading
import webbrowser
from collections import Counter
from datetime import datetime
from importlib.resources import files
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape


def _knowledge_overview() -> dict[str, object]:
    """Small knowledge-base summary for the result dashboard."""
    try:
        from archkg.knowledge.loader import load_rules, load_standards

        standards = load_standards()
        rules = load_rules(standards=standards)
    except Exception as exc:
        return {"error": str(exc), "total_clauses": "—", "total_rules": "—"}

    source_counter: Counter[str] = Counter(c.source for c in standards)
    category_counter: Counter[str] = Counter(c.category for c in standards)
    residential_rules = len([r for r in standards if "residential" in r.applies_to_building_type])

    return {
        "total_clauses": len(standards),
        "total_rules": len(rules),
        "residential_rules": residential_rules,
        "by_source": sorted(source_counter.items(), key=lambda p: p[1], reverse=True),
        "by_category": sorted(category_counter.items(), key=lambda p: p[1], reverse=True),
    }


def _issue_metrics_payload(
    issues: list[dict[str, object]],
    *,
    top_rules: int = 6,
    top_clauses: int = 6,
) -> dict[str, object]:
    """Same compact chart payload as studio for a text-light dashboard."""
    total = len(issues)
    total_safe = max(total, 1)
    try:
        from archkg.knowledge.loader import load_rules, load_standards
        from archkg.knowledge.readiness import classify_all

        rules = load_rules(standards=load_standards())
        rule_tiers = {finding.rule_id: finding.tier for finding in classify_all(rules)}
    except Exception:
        rule_tiers = {}

    tier_labels = {
        "AUTODETECTABLE": "可自动检测",
        "PARTIAL_AUTODETECT": "待补数据",
        "PROJECT_META_DRIVEN": "项目驱动",
        "REMINDER_BY_DESIGN": "设计复核",
        "STAIR_PENDING": "STAIR 待建",
        "UNKNOWN": "未映射",
    }
    tier_colors = {
        "AUTODETECTABLE": "var(--tier-autodetect)",
        "PARTIAL_AUTODETECT": "var(--tier-partial)",
        "PROJECT_META_DRIVEN": "var(--tier-project)",
        "REMINDER_BY_DESIGN": "var(--tier-reminder)",
        "STAIR_PENDING": "var(--tier-stair)",
        "UNKNOWN": "var(--tier-unknown)",
    }
    tier_order = (
        "AUTODETECTABLE",
        "PARTIAL_AUTODETECT",
        "PROJECT_META_DRIVEN",
        "REMINDER_BY_DESIGN",
        "STAIR_PENDING",
        "UNKNOWN",
    )

    severity = Counter(i.get("severity", "info") for i in issues)
    summary = {
        "total": total,
        "error": int(severity.get("error", 0)),
        "warning": int(severity.get("warning", 0)),
        "info": int(severity.get("info", 0)),
        "other": int(total - severity.get("error", 0) - severity.get("warning", 0) - severity.get("info", 0)),
    }

    severity_chart = [
        {
            "key": "error",
            "label": "高风险",
            "color": "var(--red)",
            "count": summary["error"],
            "pct": 100.0 * summary["error"] / total_safe,
        },
        {
            "key": "warning",
            "label": "警示",
            "color": "var(--orange)",
            "count": summary["warning"],
            "pct": 100.0 * summary["warning"] / total_safe,
        },
        {
            "key": "info",
            "label": "核对",
            "color": "var(--blue)",
            "count": summary["info"],
            "pct": 100.0 * summary["info"] / total_safe,
        },
    ]

    rule_counter: Counter[str] = Counter()
    clause_counter: Counter[str] = Counter()

    for issue in issues:
        rule_id = issue.get("rule_card_id")
        if isinstance(rule_id, str):
            rule_counter.update([rule_id])
        clause_id = issue.get("standard_clause_id")
        if isinstance(clause_id, str):
            clause_counter.update([clause_id])
    top_rules_rows = [
        {
            "rule_card_id": rid,
            "count": count,
            "pct": 100.0 * count / total_safe,
            "tier": rule_tiers.get(rid, "UNKNOWN"),
            "color": tier_colors[rule_tiers.get(rid, "UNKNOWN")],
        }
        for rid, count in rule_counter.most_common(top_rules)
    ]
    top_rule_tier_counter = Counter(
        rule_tiers.get(rid, "UNKNOWN") for rid, _ in rule_counter.most_common(top_rules)
    )
    rule_tier_rows = []
    for tier in tier_order:
        count = int(top_rule_tier_counter.get(tier, 0))
        if count == 0:
            continue
        rule_tier_rows.append(
            {
                "tier": tier,
                "label": tier_labels[tier],
                "count": count,
                "pct": 100.0 * count / total_safe,
                "color": tier_colors[tier],
            }
        )
    top_clause_rows = [
        {"source": source, "count": count, "pct": 100.0 * count / total_safe}
        for source, count in clause_counter.most_common(top_clauses)
    ]
    return {
        "summary": summary,
        "severity_chart": severity_chart,
        "rule_tier_bars": rule_tier_rows,
        "rule_tiers": rule_tiers,
        "top_rules": top_rules_rows,
        "top_clauses": top_clause_rows,
    }


def _render_index(out_dir: Path, source_pdf: Path) -> Path:
    template_dir = str(files("archkg.viewer.templates"))
    env = Environment(
        loader=FileSystemLoader(template_dir),
        autoescape=select_autoescape(default=True, default_for_string=True),
        trim_blocks=True,
        lstrip_blocks=True,
    )

    issues_path = out_dir / "issues.json"
    graph_path = out_dir / "entity_graph.json"
    primitives_path = out_dir / "primitives.json"
    report_path = out_dir / "report.md"
    run_meta_path = out_dir / "run_meta.json"

    issues = json.loads(issues_path.read_text("utf-8")) if issues_path.exists() else []
    graph = json.loads(graph_path.read_text("utf-8")) if graph_path.exists() else {}
    primitives = (
        json.loads(primitives_path.read_text("utf-8")) if primitives_path.exists() else {}
    )
    report_md = report_path.read_text("utf-8") if report_path.exists() else "(report.md missing)"
    from archkg.viewer.drawing_understanding import load_or_build_drawing_understanding
    from archkg.viewer.ocr_diagnostics import build_ocr_diagnostics
    from archkg.viewer.review_state import load_review_state_view
    from archkg.viewer.rule_readiness import load_rule_readiness_view
    from archkg.viewer.sheet_classification import load_sheet_classification_view
    from archkg.viewer.sheet_graphs import load_sheet_graphs_view
    from archkg.viewer.sheet_issues import load_sheet_issues_view
    from archkg.viewer.sheet_region_candidates import load_sheet_region_candidate_view
    from archkg.viewer.sheet_routing import load_sheet_routing_view

    # Codex P19-C R2 P0: honour inspect_only mode on re-render. Without
    # this, archkg viewer re-renders an inspect_only run as a misleading
    # "0 violations = clean review" page.
    if run_meta_path.exists():
        run_meta = json.loads(run_meta_path.read_text("utf-8"))
        mode = run_meta.get("mode", "full")
        quality_flags = list(run_meta.get("quality_flags", []))
    else:
        mode = "full"
        quality_flags = []

    n_lines = sum(len(p.get("lines", [])) for p in primitives.get("pages", []))
    n_texts = sum(len(p.get("texts", [])) for p in primitives.get("pages", []))
    applicable = len(graph.get("rooms", [])) + len(graph.get("doors", [])) + len(graph.get("corridors", []))
    clause_refs = _clause_refs(issues)
    issue_payload = _issue_metrics_payload(issues)
    issue_summary = issue_payload["summary"]
    ocr_diagnostics = build_ocr_diagnostics(primitives, graph)
    drawing_understanding = load_or_build_drawing_understanding(
        out_dir,
        primitives,
        graph,
        ocr_diagnostics,
    )
    rule_readiness = load_rule_readiness_view(out_dir)
    review_state = load_review_state_view(out_dir, issues)
    sheet_classification = load_sheet_classification_view(out_dir)
    sheet_graphs = load_sheet_graphs_view(out_dir)
    sheet_issues = load_sheet_issues_view(out_dir)
    sheet_routing = load_sheet_routing_view(out_dir)
    sheet_region_candidates = load_sheet_region_candidate_view(out_dir)

    stats = {
        "lines": n_lines,
        "texts": n_texts,
        "rooms": len(graph.get("rooms", [])),
        "doors": len(graph.get("doors", [])),
        "corridors": len(graph.get("corridors", [])),
        "applicable_entities": applicable,
    }

    html = env.get_template("index.html.j2").render(
        source_pdf=str(source_pdf),
        created_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        issues=issues,
        stats=stats,
        report_md=report_md,
        knowledge_overview=_knowledge_overview(),
        issue_summary=issue_summary,
        issue_metrics=issue_payload,
        clause_refs=clause_refs,
        ocr_diagnostics=ocr_diagnostics,
        drawing_understanding=drawing_understanding,
        rule_readiness=rule_readiness,
        review_state=review_state,
        sheet_classification=sheet_classification,
        sheet_graphs=sheet_graphs,
        sheet_issues=sheet_issues,
        sheet_routing=sheet_routing,
        sheet_region_candidates=sheet_region_candidates,
        mode=mode,
        quality_flags=quality_flags,
    )
    index_path = out_dir / "index.html"
    index_path.write_text(html, encoding="utf-8")
    return index_path


def _clause_refs(
    issues: list[dict[str, object]],
    *,
    limit: int = 8,
) -> list[dict[str, object]]:
    """Build a compact clause reference list for the result template."""
    from archkg.knowledge.loader import load_standards

    if not issues:
        return []
    clause_ids: list[str] = []
    for issue in issues:
        clause_id = issue.get("standard_clause_id")
        if isinstance(clause_id, str):
            clause_ids.append(clause_id)
    top_clause_ids = [cid for cid, _ in Counter(clause_ids).most_common(limit)]
    if not top_clause_ids:
        return []
    try:
        standards = load_standards()
        by_id = {c.id: c for c in standards}
    except Exception:
        return []

    out: list[dict[str, object]] = []
    for cid in top_clause_ids:
        clause = by_id.get(cid)
        if clause is None:
            continue
        text = clause.clause_text.replace("\n", " ")
        if len(text) > 85:
            text = text[:82] + "…"
        out.append(
            {
                "clause_id": cid,
                "source": clause.source,
                "category": clause.category,
                "threshold_value": clause.threshold_value if clause.threshold_value is not None else "—",
                "unit": clause.unit or "",
                "clause_text": text,
            }
        )
    return out


def _render_pdf_preview(pdf: Path, out_png: Path, dpi: int = 200) -> Path:
    import fitz

    doc = fitz.open(str(pdf))
    try:
        page = doc[0]
        zoom = dpi / 72.0
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        pix.save(str(out_png))
    finally:
        doc.close()
    return out_png


def serve(
    out_dir: Path,
    source_pdf: Path,
    *,
    port: int = 8765,
    open_browser: bool = True,
) -> None:
    if not (out_dir / "issues.json").exists():
        raise FileNotFoundError(
            f"{out_dir}/issues.json missing — run `archkg review <pdf> -o {out_dir}` first."
        )

    # 1) materialise inline previews + copy the source PDF so the page can deep-link to it
    _render_pdf_preview(source_pdf, out_dir / "source_preview.png")
    if (out_dir / "annotated.pdf").exists():
        _render_pdf_preview(out_dir / "annotated.pdf", out_dir / "annotated_preview.png")
    if not (out_dir / "source.pdf").exists() or (
        out_dir / "source.pdf"
    ).resolve() != source_pdf.resolve():
        shutil.copy(source_pdf, out_dir / "source.pdf")

    # 2) generate index.html
    index = _render_index(out_dir, source_pdf)
    print(f"viewer · index = {index}")

    # 3) start http.server rooted at out_dir
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(out_dir))
    with socketserver.TCPServer(("127.0.0.1", port), handler) as httpd:
        url = f"http://127.0.0.1:{port}/index.html"
        print(f"viewer · serving {out_dir} at {url}")
        if open_browser:
            threading.Timer(0.6, lambda: webbrowser.open(url)).start()
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nviewer · stopping (Ctrl-C)")
