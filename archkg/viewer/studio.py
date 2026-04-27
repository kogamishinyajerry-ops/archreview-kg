"""Studio: minimal upload UI for first-time users (Phase 19-B).

Goal: let a non-developer drag-drop a PDF (and optional ProjectMeta /
room / stair schedule YAMLs), get back the same artifacts that
`archkg review` produces, served through the existing read-only viewer
template.

Architecture choices:
- Flask, not http.server: multipart parsing in stdlib is fragile;
  Flask is small, well-known, and we already have Jinja2.
- In-process pipeline (no subprocess): same path as
  archkg.adversarial.battery._review_case but writes the FULL set of
  artifacts a reviewer expects (annotated.pdf, report.md, overlay PNG).
- Per-run isolated dirs under {state_dir}/runs/{run_id}/ so concurrent
  uploads don't trample each other.
- "Try the demo" button runs samples/sample_clean.pdf with the bundled
  demo metas — first-time visitors can see end-to-end output without
  preparing any inputs.

Out of scope here:
- Authentication (single-user local tool).
- Async queue (review of a small PDF takes <2s; the request just blocks).
- Real-PDF robustness — first failure modes will show up as exceptions
  surfaced to the user; v1.2.x can polish those.
"""

# Studio is a Chinese-zh-CN UI; full-width punctuation is intentional.
# ruff: noqa: RUF001

from __future__ import annotations

import json
import shutil
import traceback
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from importlib.resources import files
from pathlib import Path
from typing import Any

import yaml
from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template_string,
    request,
    send_from_directory,
    url_for,
)
from jinja2 import Environment, FileSystemLoader, select_autoescape
from werkzeug.utils import secure_filename

# ---------------------------------------------------------------------------
# In-process review pipeline (used by /review and /demo)
# ---------------------------------------------------------------------------


# Phase 19-C: thresholds for the entity-sanity-check quality flags.
# A real Chinese residential plan rarely has more than ~50 distinct rooms
# or doors per page. Above that, the builder is over-segmenting and the
# rule report is dominated by spurious gap detections (Medfield case
# study: 169 rooms / 204 doors / 89 spurious door-width violations).
ROOM_COUNT_NOISE_THRESHOLD = 50
DOOR_COUNT_NOISE_THRESHOLD = 50


@dataclass
class PipelineResult:
    out_dir: Path
    issues_count: int
    error_count: int
    info_count: int
    skipped_count: int
    room_count: int = 0
    door_count: int = 0
    corridor_count: int = 0
    quality_flags: tuple[str, ...] = ()


def _compute_quality_flags(graph: Any) -> tuple[str, ...]:
    """Phase 19-C: surface obvious noise patterns BEFORE the user reads
    the rule report. Real residential floor plans rarely cross these
    thresholds; when they do, the builder is over-segmenting and any
    rule firing on those entities is suspect.

    Codex P19-C R1 P2: accepts the typed ``EntityGraph`` directly so a
    serialisation shape change can't silently bypass the safeguards.
    A mapping (already-loaded JSON dict) is also accepted as a fallback
    for tests that fabricate synthetic graphs.
    """

    def _len(field: str) -> int:
        if hasattr(graph, field):
            return len(getattr(graph, field))
        if isinstance(graph, dict):
            return len(graph.get(field, []))
        return 0

    n_rooms = _len("rooms")
    n_doors = _len("doors")
    n_corridors = _len("corridors")

    flags: list[str] = []
    if n_rooms > ROOM_COUNT_NOISE_THRESHOLD:
        flags.append(
            f"⚠ rooms={n_rooms} > {ROOM_COUNT_NOISE_THRESHOLD}: 可能是 builder "
            "在 over-segmenting (把 window frames / fixture outlines / "
            "dimension boxes 当成 rooms), 也可能是单页密度异常高的真实图纸。"
            "请先人工核对实体数量再信任规则违规清单。"
        )
    if n_doors > DOOR_COUNT_NOISE_THRESHOLD:
        flags.append(
            f"⚠ doors={n_doors} > {DOOR_COUNT_NOISE_THRESHOLD}: gap 检测可能在"
            "非门洞的墙体断口 (windows / cabinet edges) 上 fire。"
            "RC-DOOR-WIDTH 违规在这些 entity 上不可信。"
        )
    if n_corridors == 0 and n_rooms > 0:
        flags.append(
            "ⓘ 未检出 corridor — RC-CORRIDOR-WIDTH 与 "
            "RC-ACCESSIBLE-INDOOR-CORRIDOR-WIDTH-1.20 不会触发。"
        )
    return tuple(flags)


def _knowledge_overview() -> dict[str, Any]:
    """Small summary payload for the upload page's knowledge-coverage panel."""
    from archkg.knowledge.loader import load_rules, load_standards

    try:
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
        "by_source": sorted(source_counter.items(), key=lambda p: p[1], reverse=True),
        "by_category": sorted(category_counter.items(), key=lambda p: p[1], reverse=True),
        "residential_rules": residential_rules,
    }


def _rule_readiness_map() -> dict[str, str]:
    """Load current rule->ready tier map for visual tagging.

    If readiness metadata is temporarily unavailable, degrade to an empty
    map and rely on ``UNKNOWN`` downstream.
    """
    try:
        from archkg.knowledge.loader import load_rules, load_standards
        from archkg.knowledge.readiness import classify_all

        rules = load_rules(standards=load_standards())
    except Exception:
        return {}
    return {finding.rule_id: finding.tier for finding in classify_all(rules)}


def _issue_summary(issues: list[dict[str, Any]]) -> dict[str, int]:
    """Summarise severity counts for the result dashboard."""
    severity = Counter(i.get("severity", "info") for i in issues)
    return {
        "total": len(issues),
        "error": int(severity.get("error", 0)),
        "warning": int(severity.get("warning", 0)),
        "info": int(severity.get("info", 0)),
        "other": int(len(issues) - severity.get("error", 0) - severity.get("warning", 0) - severity.get("info", 0)),
    }


def _issue_metric_payload(
    issues: list[dict[str, Any]],
    *,
    top_rules: int = 6,
    top_sources: int = 6,
) -> dict[str, Any]:
    """Pre-compute compact chart data so Jinja templates stay mostly layout."""
    summary = _issue_summary(issues)
    total = max(summary["total"], 1)
    rule_tiers = _rule_readiness_map()
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

    severity_bars = [
        ("error", "高风险", "var(--red)", summary["error"]),
        ("warning", "警示", "var(--orange)", summary["warning"]),
        ("info", "核对", "var(--blue)", summary["info"]),
    ]
    severity_chart = [
        {
            "key": key,
            "label": label,
            "color": color,
            "count": count,
            "pct": 100.0 * count / total,
        }
        for key, label, color, count in severity_bars
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
    top_rule_tier_counter = Counter(
        rule_tiers.get(rid, "UNKNOWN") for rid, _ in rule_counter.most_common(top_rules)
    )
    tier_rows = []
    for tier in tier_order:
        count = int(top_rule_tier_counter.get(tier, 0))
        if count == 0:
            continue
        tier_rows.append(
            {
                "tier": tier,
                "label": tier_labels[tier],
                "count": count,
                "pct": 100.0 * count / total,
                "color": tier_colors[tier],
            }
        )

    top_rule_rows = [
        {
            "rule_card_id": rid,
            "count": count,
            "tier": rule_tiers.get(rid, "UNKNOWN"),
            "pct": 100.0 * count / summary["total"] if summary["total"] else 0.0,
            "color": tier_colors[rule_tiers.get(rid, "UNKNOWN")],
        }
        for rid, count in rule_counter.most_common(top_rules)
    ]
    top_sources_rows = [
        {"source": source, "count": count}
        for source, count in clause_counter.most_common(top_sources)
    ]

    return {
        "summary": summary,
        "severity_chart": severity_chart,
        "rule_tier_bars": tier_rows,
        "rule_tiers": rule_tiers,
        "top_rules": top_rule_rows,
        "top_clauses": top_sources_rows,
    }


def _clause_refs(
    issues: list[dict[str, Any]],
    *,
    limit: int = 8,
) -> list[dict[str, Any]]:
    """Create a compact clause reference list from top-used clause IDs."""
    from archkg.knowledge.loader import load_standards

    if not issues:
        return []
    clause_ids: list[str] = []
    for issue in issues:
        clause_id = issue.get("standard_clause_id")
        if isinstance(clause_id, str):
            clause_ids.append(clause_id)
    top_clause_ids = [cid for cid, _ in Counter(clause_ids).most_common(limit)]

    try:
        standards = load_standards()
        by_id = {c.id: c for c in standards}
    except Exception:
        return []

    out = []
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


def run_pipeline(
    pdf_path: Path,
    out_dir: Path,
    *,
    project_meta_path: Path | None = None,
    room_schedule_path: Path | None = None,
    stair_schedule_path: Path | None = None,
    points_per_meter: float = 50.0,
    inspect_only: bool = False,
    min_room_area_m2: float = 1.0,
    sheet_region: tuple[float, float, float, float] | None = None,
    use_ocr: bool = False,
) -> PipelineResult:
    """End-to-end review on a single PDF.

    Same lane as `archkg review` but factored out so the studio's HTTP
    handler can call it directly. Writes primitives.json, entity_graph.json,
    drawing_understanding.json, rule_input_readiness.json (full mode),
    issues.json, annotated.pdf, report.md, and entity_overlay.png into
    out_dir.

    Phase 19-C:
    - ``points_per_meter`` exposed so the studio can take it from the
      user (US arch sheets, mm-scaled CAD exports, etc. all need
      different values).
    - ``inspect_only=True`` runs ingest + build_graph + overlay only;
      skips rule evaluation. Lets users sanity-check what the builder
      detected on an unfamiliar PDF before reading a (potentially
      noisy) rule report.

    Phase 19-D:
    - ``min_room_area_m2`` (default 1.0 m²) drops sub-threshold
      polygons before they become rooms. Suppresses the bulk of
      CAD-export noise (window frames, dim boxes, fixture outlines)
      that would otherwise light up the rule report with spurious
      door-width violations on non-door wall breaks adjacent to those
      noise rooms. Set to 0.0 to disable.

    Phase 20-B:
    - ``use_ocr`` enables the optional PaddleOCR bridge for raster
      uploads. It is best-effort and does not change vector-PDF
      behavior. If OCR is unavailable or returns no texts, the raster
      warning remains visible.
    """
    from archkg.annotate.pdf_annotator import annotate as annotate_pdf
    from archkg.annotate.report import render as render_report
    from archkg.graph.builder import build_graph, render_overlay
    from archkg.graph.builder import write_json as write_graph
    from archkg.ingest.primitive_extractor import extract as extract_pdf
    from archkg.ingest.primitive_extractor import write_json as write_prims
    from archkg.ingest.raster_extractor import extract as extract_raster
    from archkg.ingest.raster_extractor import wrap_image_as_pdf
    from archkg.ingest.sheet_region import crop_primitives_to_region
    from archkg.ingest.sheet_region_candidates import (
        build_sheet_region_candidates,
        write_sheet_region_candidates,
    )
    from archkg.knowledge.loader import load_rules, load_standards
    from archkg.knowledge.run_readiness import (
        build_rule_input_readiness,
        write_rule_input_readiness,
    )
    from archkg.rules.engine import evaluate
    from archkg.schemas import ProjectMeta
    from archkg.viewer.drawing_understanding import (
        build_drawing_understanding,
        write_drawing_understanding,
    )
    from archkg.viewer.ocr_diagnostics import build_ocr_diagnostics
    from archkg.viewer.rule_readiness import build_rule_readiness_view

    out_dir.mkdir(parents=True, exist_ok=True)

    meta: ProjectMeta | None = None
    if project_meta_path is not None:
        raw = yaml.safe_load(project_meta_path.read_text("utf-8"))
        meta = ProjectMeta.model_validate(raw)
        (out_dir / "project_meta.yaml").write_text(
            yaml.safe_dump(meta.model_dump(), allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    # Phase 20-A: dispatch on file extension. PDFs go through the
    # vector path (PyMuPDF); PNG/JPEG/TIFF go through the CV pipeline
    # (raster_extractor). OCR is opt-in because PaddleOCR is not part
    # of the default install.
    suffix = pdf_path.suffix.lower()
    is_raster_input = suffix in (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp")
    if is_raster_input:
        primitives = extract_raster(
            pdf_path,
            points_per_meter=points_per_meter,
            use_ocr=use_ocr,
        )
        # Wrap the image as a 1:1 px:pt PDF so the rest of the
        # pipeline (preview, annotation, overlay) treats it like any
        # other PDF and the pixel-space polygon coords align with
        # fitz's page rect.
        wrapped_pdf = pdf_path.with_suffix(".raster.pdf")
        wrap_image_as_pdf(pdf_path, wrapped_pdf)
        # Re-bind pdf_path to the wrapped file for downstream steps;
        # the original raster file stays in the run dir as a record.
        pdf_path = wrapped_pdf
    else:
        primitives = extract_pdf(pdf_path, points_per_meter=points_per_meter)
    sheet_candidates = build_sheet_region_candidates(
        primitives,
        applied_region=sheet_region,
    )
    write_sheet_region_candidates(sheet_candidates, out_dir / "sheet_region_candidates.json")
    if sheet_region is not None:
        primitives = crop_primitives_to_region(primitives, sheet_region)
    write_prims(primitives, out_dir / "primitives.json")
    graph = build_graph(primitives, min_room_area_m2=min_room_area_m2)

    schedule_apply = None
    if room_schedule_path is not None:
        if meta is None:
            raise ValueError(
                "room_schedule requires project_meta so the schedule's "
                "project_id can be cross-checked."
            )
        from archkg.graph.schedule import apply_room_schedule
        from archkg.knowledge.room_schedule import load_room_schedule

        schedule = load_room_schedule(room_schedule_path)
        if schedule.project_id != meta.project_id:
            raise ValueError(
                f"room_schedule project_id '{schedule.project_id}' does not "
                f"match project_meta project_id '{meta.project_id}'"
            )
        schedule_apply = apply_room_schedule(graph, schedule)
        graph = schedule_apply.graph

    stair_schedule_apply = None
    if stair_schedule_path is not None:
        if meta is None:
            raise ValueError(
                "stair_schedule requires project_meta so the schedule's "
                "project_id can be cross-checked."
            )
        from archkg.graph.stair_schedule import apply_stair_schedule
        from archkg.knowledge.stair_schedule import load_stair_schedule

        sched = load_stair_schedule(stair_schedule_path)
        if sched.project_id != meta.project_id:
            raise ValueError(
                f"stair_schedule project_id '{sched.project_id}' does not "
                f"match project_meta project_id '{meta.project_id}'"
            )
        stair_schedule_apply = apply_stair_schedule(graph, sched)
        graph = stair_schedule_apply.graph

    graph_path = write_graph(graph, out_dir / "entity_graph.json")
    render_overlay(graph, pdf_path, out_dir / "entity_overlay.png")
    primitives_payload = primitives.model_dump(mode="json")
    graph_payload = graph.model_dump(mode="json")
    ocr_diagnostics = build_ocr_diagnostics(primitives_payload, graph_payload)
    drawing_understanding = build_drawing_understanding(
        primitives_payload,
        graph_payload,
        ocr_diagnostics,
    )
    write_drawing_understanding(
        drawing_understanding,
        out_dir / "drawing_understanding.json",
    )

    # Count entities from the in-memory typed graph directly so a future
    # serialisation shape change can't silently neuter the quality flags.
    quality_flags = _compute_quality_flags(graph)
    n_rooms = len(graph.rooms)
    n_doors = len(graph.doors)
    n_corridors = len(graph.corridors)
    ocr_text_count = sum(
        1
        for page in primitives.pages
        for text in page.texts
        if text.source == "ocr"
    )

    # Codex P20-A R1 P1 / R2 P1: label-less raster ingest silently
    # skips label-dependent Room rules. P20-B keeps that warning unless
    # OCR actually produced text primitives. OCR being enabled is not
    # enough; unavailable PaddleOCR or empty results still mean a
    # partial review. The earlier false remediation path remains
    # forbidden: ``room_schedule.yaml`` selects existing room_id/label
    # and cannot patch label-less raster runs.
    if is_raster_input and ocr_text_count == 0:
        raster_flag = (
            "ⓘ 栅格图无 OCR：本次未获得 OCR text primitives，检出的房间均无 label，"
            "依赖 label 的 5 张 Room 规则不会触发"
            " (RC-BEDROOM-AREA / RC-LIVING-BEDROOM-NETHEIGHT-2.4 /"
            " RC-PITCHED-ROOF-MAJORITY-NETHEIGHT-2.1 /"
            " RC-BASEMENT-MEZZANINE-NETHEIGHT-2.0 / RC-NO-LIVING-IN-BASEMENT)。"
            " 本次违规清单是 partial 审图 (几何规则可触发, 上述 5 张 label-依赖规则不触发)。"
            " 完整审图请改上传与之对应的矢量 PDF，或安装 OCR 依赖后启用栅格 OCR beta。"
        )
        quality_flags = (raster_flag, *quality_flags)
    elif is_raster_input and ocr_text_count > 0:
        quality_flags = (
            f"ⓘ 栅格图 OCR beta：已获得 {ocr_text_count} 条 OCR text primitives；"
            "仍需人工核对 OCR 置信度与房间标签绑定结果。",
            *quality_flags,
        )

    # Codex P19-C R2 P0: persist mode + quality_flags so any downstream
    # renderer (archkg viewer, scripts that re-render index.html, future
    # web previews) honours the inspect_only semantics. Without this the
    # standalone `archkg viewer <run-dir>` would happily re-render an
    # inspect_only run as a green "0 violations" page.
    _write_run_meta(
        out_dir,
        mode="inspect_only" if inspect_only else "full",
        quality_flags=quality_flags,
        points_per_meter=points_per_meter,
        min_room_area_m2=min_room_area_m2,
        sheet_region=sheet_region,
        use_ocr=use_ocr if is_raster_input else False,
        ocr_text_count=ocr_text_count,
    )

    # Mirror what the existing viewer.serve() needs: a copy of the source
    # PDF + a 200-DPI preview PNG of the source. Always do this so even
    # inspect_only runs render correctly.
    if not (out_dir / "source.pdf").exists():
        shutil.copy(pdf_path, out_dir / "source.pdf")
    _render_preview(pdf_path, out_dir / "source_preview.png")

    if inspect_only:
        # Skip rule evaluation; write empty issues + a minimal report so
        # the viewer template still renders. The annotated PDF is just a
        # copy of the source with no markup.
        (out_dir / "issues.json").write_text("[]", encoding="utf-8")
        shutil.copy(pdf_path, out_dir / "annotated.pdf")
        _render_preview(out_dir / "annotated.pdf", out_dir / "annotated_preview.png")
        report_lines = [
            "# 仅识图模式 — ArchReview-KG",
            "",
            f"- 源文件：`{pdf_path.name}`",
            "- 模式：**inspect_only**（只跑 ingest + build_graph，不评估规则）",
            f"- 检出实体：rooms={n_rooms} / doors={n_doors} / corridors={n_corridors}",
            "",
            "## 质量提示" if quality_flags else "## 质量提示\n\n(无)",
        ]
        for flag in quality_flags:
            report_lines.append(f"- {flag}")
        report_lines.append("")
        report_lines.append(
            "如果上面 entity 数量看起来合理，可以重新上传选 **完整审图模式** "
            "让规则引擎评估违规。"
        )
        (out_dir / "report.md").write_text("\n".join(report_lines), encoding="utf-8")
        _render_viewer_index(
            out_dir, pdf_path,
            quality_flags=quality_flags,
            mode="inspect_only",
        )
        return PipelineResult(
            out_dir=out_dir,
            issues_count=0,
            error_count=0,
            info_count=0,
            skipped_count=0,
            room_count=n_rooms,
            door_count=n_doors,
            corridor_count=n_corridors,
            quality_flags=quality_flags,
        )

    standards = load_standards()
    rules = load_rules(standards=standards)
    result = evaluate(graph, rules, standards, project_meta=meta)
    rule_readiness = build_rule_input_readiness(
        graph,
        rules,
        standards,
        project_meta=meta,
        skipped=result.skipped,
        ocr_diagnostics=ocr_diagnostics,
        schedule_apply=schedule_apply,
        stair_schedule_apply=stair_schedule_apply,
    )
    write_rule_input_readiness(rule_readiness, out_dir / "rule_input_readiness.json")
    (out_dir / "issues.json").write_text(
        json.dumps([i.model_dump() for i in result.issues], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    annotated = annotate_pdf(pdf_path, result.issues, out_dir / "annotated.pdf")
    render_report(
        source_pdf=pdf_path,
        entity_graph_path=graph_path,
        annotated_pdf=annotated,
        issues=result.issues,
        clauses=standards,
        out_md=out_dir / "report.md",
        project_meta=meta,
        skipped=result.skipped,
        rule_readiness=build_rule_readiness_view(
            rule_readiness.model_dump(mode="json")
        ),
    )

    if annotated.exists():
        _render_preview(annotated, out_dir / "annotated_preview.png")

    # Pre-render the existing viewer index so the redirect lands on a
    # ready-to-display page.
    _render_viewer_index(
        out_dir, pdf_path,
        quality_flags=quality_flags,
        mode="full",
    )

    error_count = sum(1 for i in result.issues if i.severity == "error")
    info_count = sum(1 for i in result.issues if i.severity == "info")
    return PipelineResult(
        out_dir=out_dir,
        issues_count=len(result.issues),
        error_count=error_count,
        info_count=info_count,
        skipped_count=len(result.skipped),
        room_count=n_rooms,
        door_count=n_doors,
        corridor_count=n_corridors,
        quality_flags=quality_flags,
    )


def _write_run_meta(
    out_dir: Path,
    *,
    mode: str,
    quality_flags: tuple[str, ...] = (),
    points_per_meter: float | None = None,
    min_room_area_m2: float | None = None,
    sheet_region: tuple[float, float, float, float] | None = None,
    use_ocr: bool | None = None,
    ocr_text_count: int | None = None,
) -> Path:
    """Persist the inspect-only / full mode + quality flags + tunable
    knobs to a JSON file in the run directory. Read by
    ``archkg.viewer.server._render_index`` so any re-render of the
    run's ``index.html`` honours the inspect-only mode.

    Codex P19-C R2 P0: without this marker, ``archkg viewer <run-dir>``
    re-renders inspect_only runs as full-success pages because it can't
    distinguish "0 issues because rules ran and found nothing" from "0
    issues because rules were skipped".

    Codex P19-D R1 P2: also persist the tunable knobs that materially
    change outputs (ppm + min_room_area_m2) so a user reporting
    unexpected entity counts can be debugged from the run dir alone.

    Phase 20-B persists OCR mode and observed OCR text count so a
    raster run can be debugged from artifacts alone.
    """
    payload: dict[str, Any] = {
        "mode": mode,
        "quality_flags": list(quality_flags),
    }
    if points_per_meter is not None:
        payload["points_per_meter"] = points_per_meter
    if min_room_area_m2 is not None:
        payload["min_room_area_m2"] = min_room_area_m2
    if sheet_region is not None:
        payload["sheet_region"] = list(sheet_region)
    if use_ocr is not None:
        payload["use_ocr"] = use_ocr
    if ocr_text_count is not None:
        payload["ocr_text_count"] = ocr_text_count
    meta_path = out_dir / "run_meta.json"
    meta_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return meta_path


def _render_preview(pdf: Path, out_png: Path, dpi: int = 200) -> None:
    import fitz

    doc = fitz.open(str(pdf))
    try:
        page = doc[0]
        zoom = dpi / 72.0
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        pix.save(str(out_png))
    finally:
        doc.close()


def _render_viewer_index(
    out_dir: Path,
    source_pdf: Path,
    *,
    quality_flags: tuple[str, ...] = (),
    mode: str = "full",
) -> None:
    """Reuse the existing read-only viewer template.

    Phase 19-C: passes ``quality_flags`` and ``mode`` so the rendered
    page can warn the reader before they trust the rule output. The
    template treats both as optional (older fixtures still render)."""
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

    issues = json.loads(issues_path.read_text("utf-8")) if issues_path.exists() else []
    graph = json.loads(graph_path.read_text("utf-8")) if graph_path.exists() else {}
    primitives = (
        json.loads(primitives_path.read_text("utf-8")) if primitives_path.exists() else {}
    )
    report_md = report_path.read_text("utf-8") if report_path.exists() else "(report.md missing)"
    from archkg.viewer.drawing_understanding import load_or_build_drawing_understanding
    from archkg.viewer.ocr_diagnostics import build_ocr_diagnostics
    from archkg.viewer.rule_readiness import load_rule_readiness_view
    from archkg.viewer.sheet_region_candidates import load_sheet_region_candidate_view

    n_lines = sum(len(p.get("lines", [])) for p in primitives.get("pages", []))
    n_texts = sum(len(p.get("texts", [])) for p in primitives.get("pages", []))
    applicable = (
        len(graph.get("rooms", []))
        + len(graph.get("doors", []))
        + len(graph.get("corridors", []))
    )

    stats = {
        "lines": n_lines,
        "texts": n_texts,
        "rooms": len(graph.get("rooms", [])),
        "doors": len(graph.get("doors", [])),
        "corridors": len(graph.get("corridors", [])),
        "applicable_entities": applicable,
    }
    issue_payload = _issue_metric_payload(issues)
    issue_summary = issue_payload["summary"]
    clause_refs = _clause_refs(issues)
    knowledge_overview = _knowledge_overview()
    ocr_diagnostics = build_ocr_diagnostics(primitives, graph)
    drawing_understanding = load_or_build_drawing_understanding(
        out_dir,
        primitives,
        graph,
        ocr_diagnostics,
    )
    rule_readiness = load_rule_readiness_view(out_dir)
    sheet_region_candidates = load_sheet_region_candidate_view(out_dir)

    html = env.get_template("index.html.j2").render(
        source_pdf=str(source_pdf),
        created_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        issues=issues,
        stats=stats,
        report_md=report_md,
        quality_flags=list(quality_flags),
        mode=mode,
        knowledge_overview=knowledge_overview,
        issue_summary=issue_summary,
        issue_metrics=issue_payload,
        clause_refs=clause_refs,
        ocr_diagnostics=ocr_diagnostics,
        drawing_understanding=drawing_understanding,
        rule_readiness=rule_readiness,
        sheet_region_candidates=sheet_region_candidates,
    )
    (out_dir / "index.html").write_text(html, encoding="utf-8")


# ---------------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------------


# Inline studio template: keep the upload UX in code (small + heavily-
# customised) and let the existing index.html.j2 handle the result page.
STUDIO_HTML = r"""
<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<title>ArchReview-KG Studio</title>
<meta name="viewport" content="width=device-width, initial-scale=1" />
<style>
  :root {
    --bg: #070b12;
    --panel: #111827;
    --line: rgba(94, 114, 151, 0.35);
    --text: #e8eefb;
    --muted: #95a2b7;
    --blue: #3f87ff;
    --green: #34d399;
    --orange: #f2b45b;
    --red: #ff5c5c;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    color: var(--text);
    font: 14px/1.65 "Noto Sans SC", "PingFang SC", "Microsoft YaHei", "Source Han Sans CN", "WenQuanYi Micro Hei", sans-serif;
    background: radial-gradient(1100px 550px at 8% -8%, #16243b 0%, transparent 52%),
      radial-gradient(900px 640px at 110% 0%, #101e30 0%, transparent 45%),
      var(--bg);
  }
  .wrap {
    max-width: 980px;
    margin: 0 auto;
    padding: 22px 16px 72px;
  }
  header {
    border: 1px solid var(--line);
    border-radius: 14px;
    padding: 18px 18px;
    background: linear-gradient(180deg, rgba(18, 28, 43, 0.95), rgba(13, 20, 30, 0.9));
    box-shadow: 0 10px 24px rgba(0, 0, 0, 0.25);
  }
  header .top {
    display: flex;
    justify-content: space-between;
    gap: 10px;
    align-items: flex-end;
  }
  .brand {
    margin: 0;
    font-size: 28px;
    font-weight: 800;
    letter-spacing: .01em;
  }
  .tag {
    margin: 6px 0 0;
    color: var(--muted);
    font-size: 13px;
  }
  .kpi {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px;
  }
  .kpi-item {
    border: 1px solid var(--line);
    border-radius: 10px;
    padding: 10px 12px;
    min-width: 140px;
    background: rgba(255, 255, 255, 0.03);
  }
  .kpi-item .k { color: var(--muted); font-size: 12px; }
  .kpi-item .v { margin-top: 2px; font-size: 18px; font-weight: 700; }

  .card {
    margin-top: 16px;
    border: 1px solid var(--line);
    border-radius: 12px;
    background: linear-gradient(180deg, rgba(17, 25, 37, 0.96), rgba(15, 22, 32, 0.9));
    box-shadow: 0 6px 20px rgba(0, 0, 0, 0.22);
    padding: 16px;
  }
  .card h2 {
    margin: 0 0 10px;
    font-size: 13px;
    color: #aab9d4;
    letter-spacing: .05em;
  }
  .drop {
    border: 2px dashed rgba(94, 114, 151, 0.55);
    border-radius: 14px;
    padding: 32px 20px;
    text-align: center;
    background: #111827;
    transition: 0.18s border-color, .18s background;
    cursor: pointer;
    min-height: 190px;
    display: grid;
    place-items: center;
    gap: 4px;
  }
  .drop.over {
    border-color: var(--blue);
    background: rgba(63, 135, 255, 0.09);
  }
  .drop-hint {
    margin: 0;
    color: var(--muted);
    font-size: 13px;
    max-width: 640px;
    line-height: 1.7;
  }
  .drop input[type=file] { display: none; }
  .file-pill {
    margin-top: 8px;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: rgba(52, 211, 153, 0.12);
    border: 1px solid rgba(52, 211, 153, 0.3);
    color: var(--green);
    border-radius: 999px;
    padding: 4px 10px;
    font-size: 12px;
  }
  .file-pill .x { color: #d5deed; opacity: .9; cursor: pointer; }
  .panel-grid {
    display: grid;
    grid-template-columns: 1.1fr 0.9fr;
    gap: 12px;
  }
  .mini-vision {
    margin-top: 10px;
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 8px;
  }
  .mini-cell {
    border: 1px solid var(--line);
    border-radius: 10px;
    padding: 8px 10px;
    background: rgba(255, 255, 255, 0.03);
  }
  .mini-cell .k {
    color: var(--muted);
    font-size: 12px;
  }
  .mini-cell .v {
    margin-top: 3px;
    font-size: 18px;
    font-weight: 700;
  }
  .mini-track {
    margin-top: 8px;
    height: 7px;
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.08);
    overflow: hidden;
    border: 1px solid rgba(255, 255, 255, 0.14);
  }
  .mini-track > span {
    display: block;
    height: 100%;
    border-radius: 999px;
    background: linear-gradient(90deg, #56a8ff, #90d4ff);
  }
  details {
    border: 1px solid var(--line);
    border-radius: 10px;
    padding: 10px 12px;
    margin-top: 10px;
    background: rgba(255, 255, 255, 0.03);
  }
  details summary {
    cursor: pointer;
    font-weight: 600;
    user-select: none;
  }
  details > div {
    margin-top: 10px;
    color: var(--muted);
    font-size: 13px;
    line-height: 1.65;
  }
  details label {
    display: block;
    margin-top: 10px;
    margin-bottom: 4px;
    color: var(--text);
    font-size: 13px;
  }
  details input[type=file], .num {
    width: 100%;
    border: 1px solid var(--line);
    border-radius: 8px;
    color: var(--text);
    background: #0b1624;
    padding: 7px 9px;
    font-family: inherit;
    font-size: 13px;
  }
  .preset-row {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 12px;
  }
  .preset {
    border: 1px solid rgba(156, 203, 255, 0.45);
    background: rgba(156, 203, 255, 0.1);
    color: #c8deff;
    border-radius: 999px;
    padding: 5px 10px;
    font-size: 12px;
    cursor: pointer;
  }
  .actions {
    margin-top: 16px;
    display: flex;
    gap: 10px;
    align-items: center;
  }
  .btn {
    border: 0;
    border-radius: 10px;
    font: inherit;
    font-weight: 700;
    text-decoration: none;
    cursor: pointer;
    padding: 11px 18px;
    transition: transform .05s ease, opacity .2s;
  }
  .btn:active { transform: translateY(1px); }
  .btn-primary {
    background: linear-gradient(180deg, #4d93ff, #2e7bff);
    color: white;
  }
  .btn-ghost {
    background: transparent;
    color: var(--muted);
    border: 1px solid var(--line);
  }
  .btn-primary:disabled {
    opacity: .5;
    cursor: not-allowed;
  }
  .note {
    margin-top: 10px;
    color: #9fb0c7;
    font-size: 12px;
    line-height: 1.8;
  }
  .foot {
    margin-top: 18px;
    color: #7e8da2;
    font-size: 12px;
    line-height: 1.8;
  }
  .foot a { color: var(--blue); }
  .foot code {
    background: rgba(255, 255, 255, 0.08);
    padding: 1px 6px;
    border-radius: 6px;
  }
  .flashes {
    padding: 12px 14px;
    border-radius: 10px;
    margin-bottom: 12px;
    border: 1px solid rgba(255, 92, 92, 0.45);
    background: rgba(255, 92, 92, 0.1);
    color: #ffd4d4;
    white-space: pre-wrap;
    word-break: break-word;
  }

  .inline {
    display: flex;
    align-items: center;
    gap: 8px;
    color: var(--muted);
    font-size: 12px;
  }
  .path-timeline {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 8px;
  }
  .step-card {
    border: 1px solid var(--line);
    border-radius: 10px;
    padding: 10px;
    background: rgba(255, 255, 255, 0.03);
  }
  .step-card .idx {
    display: inline-block;
    width: 18px;
    height: 18px;
    border-radius: 999px;
    font-size: 11px;
    text-align: center;
    line-height: 18px;
    background: rgba(156, 203, 255, 0.18);
    color: #c8deff;
    font-weight: 700;
  }
  .step-card .label {
    color: #dce6f7;
    margin-top: 6px;
    font-weight: 700;
    font-size: 13px;
  }
  .step-card .hint {
    color: var(--muted);
    margin-top: 4px;
    font-size: 12px;
    line-height: 1.5;
  }
  .step-card.active {
    border-color: rgba(116, 185, 255, 0.9);
    box-shadow: 0 0 0 1px rgba(116, 185, 255, 0.25) inset;
    background: rgba(116, 185, 255, 0.06);
  }


  @media (max-width: 940px) {
    .panel-grid {
      grid-template-columns: 1fr;
    }
    header .top { display: block; }
    .kpi { grid-template-columns: 1fr; margin-top: 8px; }
    .brand { font-size: 24px; }
    .actions { flex-direction: column; align-items: flex-start; }
  }
</style>
</head>
<body>
<div class="wrap">
<header>
  <div class="top">
    <div>
      <h1 class="brand">ArchReview-KG Studio</h1>
      <p class="tag">v{{ version }} · 面向民用建筑图纸的快速复核工作台</p>
    </div>
    <div class="kpi">
      <div class="kpi-item">
        <div class="k">版本</div>
        <div class="v">{{ version }}</div>
      </div>
      <div class="kpi-item">
        <div class="k">知识基座</div>
        <div class="v">
          {% if knowledge_overview.total_clauses is number %}
            {{ knowledge_overview.total_clauses }} 条
          {% else %}
            {{ knowledge_overview.error or "读取中" }}
          {% endif %}
        </div>
      </div>
    </div>
  </div>
</header>

{% with messages = get_flashed_messages() %}
  {% if messages %}
    {% for msg in messages %}<div class="flashes">{{ msg }}</div>{% endfor %}
  {% endif %}
{% endwith %}

<div class="card">
  <h2>3 步快速上手（只看结果）</h2>
  <div class="path-timeline">
    <div id="timeline-upload" class="step-card active">
      <span class="idx">1</span>
      <div class="label">上传图纸</div>
      <div class="hint">拖拽 PDF / PNG（支持矢量与栅格）</div>
    </div>
    <div id="timeline-params" class="step-card">
      <span class="idx">2</span>
      <div class="label">自动识图</div>
      <div class="hint">可选参数：识图速度 / 噪声过滤</div>
    </div>
    <div id="timeline-result" class="step-card">
      <span class="idx">3</span>
      <div class="label">结果可视化</div>
      <div class="hint">图层、条文、问题列表一屏可见</div>
    </div>
  </div>
</div>

<div class="card">
  <h2>知识库快照（规则覆盖）</h2>
  {% if knowledge_overview.error %}
    <div class="note">知识库加载失败：{{ knowledge_overview.error }}</div>
  {% else %}
    <div class="inline" style="gap: 16px;">
      <div>条文 {{ knowledge_overview.total_clauses }} 条</div>
      <div>规则卡 {{ knowledge_overview.total_rules }} 条</div>
      <div>住宅相关 {{ knowledge_overview.residential_rules }} 条</div>
    </div>
    <div style="margin-top: 10px; color: var(--muted); font-size: 12px;">
      {% for name, count in knowledge_overview.by_source[:3] %}
        <span style="display:inline-block; margin-right: 8px; margin-bottom: 6px; border: 1px dashed var(--line); border-radius: 999px; padding: 2px 8px; font-size: 12px;">{{ name }} {{ count }}</span>
      {% endfor %}
    </div>
  {% endif %}
</div>

<div class="card">
  <h2>民用建筑工作流目标</h2>
  <div class="mini-vision">
    <div class="mini-cell">
      <div class="k">识图速度</div>
      <div class="v">秒级</div>
      <div class="mini-track"><span style="width: 90%;"></span></div>
    </div>
    <div class="mini-cell">
      <div class="k">复核闭环</div>
      <div class="v">3 步</div>
      <div class="mini-track"><span style="width: 86%;"></span></div>
    </div>
    <div class="mini-cell">
      <div class="k">规则可追溯</div>
      <div class="v">{{ knowledge_overview.total_clauses if knowledge_overview.total_clauses is number else "—" }}</div>
      <div class="mini-track"><span style="width: 72%;"></span></div>
    </div>
  </div>
  <div class="note" style="margin-top: 10px;">
    目标是把“识图-判读-出复核项”缩在一屏内完成，便于设计师快速决策与交底。
  </div>
</div>

<form method="post" action="{{ url_for('review') }}" enctype="multipart/form-data" id="reviewForm">
  <div class="panel-grid">
    <div class="card">
      <h2>1) 上传图纸（拖拽优先）</h2>
      <label class="drop" id="drop">
        <input type="file" name="pdf" id="pdfInput"
               accept="application/pdf,image/png,image/jpeg,image/tiff,image/bmp" required />
        <div style="font-size: 31px;">🧭</div>
        <strong style="font-size: 18px;">把 PDF 平面图（或 PNG/JPEG 图片）拖到这里</strong>
        <p class="drop-hint">先看识图结果，再决定规则策略。PDF 与 PNG/JPEG 都支持；
          栅格图默认不跑 OCR，可在识图参数里启用 beta。</p>
        <div id="fileChosen"></div>
      </label>
      <div class="note" id="fileHint">已选：等待你拖拽文件</div>
      <div class="note">支持：.pdf / .png / .jpg / .jpeg / .tif / .tiff / .bmp</div>

      <details>
        <summary>⚙️ 识图参数</summary>
        <div>
          <div class="inline">
            <label style="margin: 0;">points_per_meter</label>
            <div style="margin-left:auto; color: var(--muted);">常用：50 / 100 / 72</div>
          </div>
          <input id="ppmInput" class="num" type="number" name="points_per_meter" step="0.1" min="0.1" value="50.0" />
          <div class="preset-row">
            <button type="button" class="preset" data-ppm="50" data-room="1.0">默认（建筑）</button>
            <button type="button" class="preset" data-ppm="100" data-room="2.0">精细 CAD（100）</button>
            <button type="button" class="preset" data-ppm="72" data-room="0.0">英制图纸（72）</button>
          </div>
          <div class="inline" style="margin-top: 10px;">
            <label style="margin: 0;">image_dpi</label>
            <div style="margin-left:auto; color: var(--muted);">仅栅格图</div>
          </div>
          <input id="dpiInput" class="num" type="number" name="image_dpi" step="1" min="36" value="200" />
          <label style="margin-top: 10px;">
            <input type="checkbox" name="use_ocr" value="1" />
            栅格 OCR beta（需要本机安装 OCR 依赖）
          </label>
          <div class="inline" style="margin-top: 10px;">
            <label style="margin: 0;">min_room_area_m2</label>
            <div style="margin-left:auto; color: var(--muted);">噪声剔除阈值</div>
          </div>
          <input id="noiseInput" class="num" type="number" name="min_room_area_m2" step="0.1" min="0" value="1.0" />
          <div class="inline" style="margin-top: 10px;">
            <label style="margin: 0;">sheet_region</label>
            <div style="margin-left:auto; color: var(--muted);">x0,y0,x1,y1</div>
          </div>
          <input class="num" type="text" name="sheet_region" placeholder="留空=整张图；例：0,0,2200,1600" />
          <label style="margin-top: 10px;">
            <input type="checkbox" name="inspect_only" value="1" />
            仅识图模式（先检查 Rooms / Doors / Corridors）
          </label>
        </div>
      </details>
    </div>

    <div class="card">
      <h2>2) 激活规则能力（可选）</h2>
      <details open>
        <summary>📋 ProjectMeta YAML（可选 · 解锁 5 张项目级规则）</summary>
        <div>
          目标：识别居住类型 / 高度 / 耐火等级 / 采光朝向；用于项目级条款映射。<br />
          <a href="https://github.com/kogamishinyajerry-ops/archreview-kg/blob/main/samples/project_meta_demo.yaml" target="_blank">project_meta_demo.yaml</a>
          <label>project_meta.yaml</label>
          <input type="file" name="project_meta" accept=".yaml,.yml" />
        </div>
      </details>
      <details>
        <summary>🏠 填房间排表 YAML 解锁 4 张净高 / 楼层 / 坡屋顶规则（仅矢量 PDF）</summary>
        <div>
          仅矢量 PDF 且存在可匹配 room_id/label 时生效。<br />
          <strong>⚠️ 仅矢量 PDF</strong>：栅格图的 room_id/label 缺失，不能匹配。<br />
          <a href="https://github.com/kogamishinyajerry-ops/archreview-kg/blob/main/samples/room_schedule_demo.yaml" target="_blank">room_schedule_demo.yaml</a>
          <label>room_schedule.yaml</label>
          <input type="file" name="room_schedule" accept=".yaml,.yml" />
        </div>
      </details>
      <details>
        <summary>🪜 解锁 4 张净高 / 楼层 / 坡屋顶规则；仅矢量 PDF</summary>
        <div>
          需配套 project_meta.yaml。<br />
          <a href="https://github.com/kogamishinyajerry-ops/archreview-kg/blob/main/samples/stair_schedule_demo.yaml" target="_blank">stair_schedule_demo.yaml</a>
          <label>stair_schedule.yaml</label>
          <input type="file" name="stair_schedule" accept=".yaml,.yml" />
        </div>
      </details>
    </div>
  </div>

  <div class="actions">
    <button type="submit" class="btn btn-primary" id="submitBtn">开始复核（可视化）</button>
    <a href="{{ url_for('demo') }}" class="btn btn-ghost">先看内置 demo</a>
  </div>
  <p class="note">4 张基础规则可独立运行：户门净宽、走廊净宽、卧室面积、无障碍走廊宽度。</p>
</form>

<div class="foot">
  完整文档：<a href="https://github.com/kogamishinyajerry-ops/archreview-kg" target="_blank">GitHub</a> ·
  知识口径检查：<code>archkg clause readiness</code><br />
  数据只在本机处理，支持离线复核与交接交底。
</div>

</div>

<script>
const drop = document.getElementById('drop');
const pdfInput = document.getElementById('pdfInput');
const chosen = document.getElementById('fileChosen');
const fileHint = document.getElementById('fileHint');
const form = document.getElementById('reviewForm');
const submitBtn = document.getElementById('submitBtn');
const ppmInput = document.getElementById('ppmInput');
const noiseInput = document.getElementById('noiseInput');
document.querySelectorAll('.preset').forEach((btn) => {
  btn.addEventListener('click', (ev) => {
    ev.preventDefault();
    ppmInput.value = btn.dataset.ppm;
    noiseInput.value = btn.dataset.room;
  });
});

function showFile(file) {
  if (file) {
    const uploadStep = document.getElementById('timeline-upload');
    const paramStep = document.getElementById('timeline-params');
    chosen.innerHTML = '<div class="file-pill">' + file.name +
      ' <span class="x" onclick="event.preventDefault(); pdfInput.value=\'\'; document.getElementById(\'fileChosen\').innerHTML=\'\';">×</span></div>';
    fileHint.textContent = `已选择 ${file.name}，准备提交`;
    if (uploadStep) {
      uploadStep.classList.add('active');
    }
    if (paramStep) {
      paramStep.classList.add('active');
    }
  } else {
    chosen.innerHTML = '';
    fileHint.textContent = '已选：等待你拖拽文件';
    const uploadStep = document.getElementById('timeline-upload');
    const paramStep = document.getElementById('timeline-params');
    const resultStep = document.getElementById('timeline-result');
    if (uploadStep) {
      uploadStep.classList.remove('active');
    }
    if (paramStep) {
      paramStep.classList.remove('active');
    }
    if (resultStep) {
      resultStep.classList.remove('active');
    }
  }
}
pdfInput.addEventListener('change', () => showFile(pdfInput.files[0]));
drop.addEventListener('dragover', (e) => { e.preventDefault(); drop.classList.add('over'); });
drop.addEventListener('dragleave', () => drop.classList.remove('over'));
drop.addEventListener('drop', (e) => {
  e.preventDefault(); drop.classList.remove('over');
  const file = e.dataTransfer.files[0];
  if (file) {
    pdfInput.files = e.dataTransfer.files;
    showFile(file);
  }
});
form.addEventListener('submit', () => {
  const resultStep = document.getElementById('timeline-result');
  submitBtn.disabled = true;
  submitBtn.textContent = '⏳ 处理中…大约 3 秒';
  if (resultStep) {
    resultStep.classList.add('active');
  }
});
</script>
</body>
</html>
"""


def _save_upload(field_name: str, run_dir: Path) -> Path | None:
    """Save an uploaded file into run_dir; return its path or None if absent."""
    f = request.files.get(field_name)
    if f is None or not f.filename:
        return None
    safe = secure_filename(f.filename) or field_name
    dest = run_dir / safe
    f.save(dest)
    return dest


def create_app(state_dir: Path, *, archkg_version: str = "1.3.0") -> Flask:
    """Build the Flask app. state_dir holds the per-run output directories."""
    runs_dir = state_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)

    app = Flask(__name__, static_folder=None, template_folder=None)
    # Studio is a single-user local tool; secret key is only used for flash().
    app.secret_key = "archkg-studio-local-dev"

    @app.route("/", methods=["GET"])
    def index() -> str:
        return render_template_string(
            STUDIO_HTML,
            version=archkg_version,
            knowledge_overview=_knowledge_overview(),
        )

    @app.route("/review", methods=["POST"])
    def review() -> Any:
        run_id = uuid.uuid4().hex[:12]
        run_dir = runs_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        pdf = request.files.get("pdf")
        if pdf is None or not pdf.filename:
            flash("请上传 PDF 或 PNG/JPEG 图片。")
            return redirect(url_for("index"))

        # Phase 20-A: accept PDF or raster (.png/.jpg/.jpeg/.tif/.tiff/.bmp).
        # secure_filename normally preserves the extension; if missing
        # we treat the upload as PDF for backward-compat.
        supported_raster_exts = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp")
        safe_pdf_name = secure_filename(pdf.filename) or "input.pdf"
        ext = Path(safe_pdf_name).suffix.lower()
        if ext == "":
            safe_pdf_name += ".pdf"
        elif ext != ".pdf" and ext not in supported_raster_exts:
            flash(
                f"不支持的文件类型 '{ext}'。请上传 PDF 或 PNG / JPEG / TIFF / BMP 图片。"
            )
            return redirect(url_for("index"))
        pdf_path = run_dir / safe_pdf_name
        pdf.save(pdf_path)

        meta_path = _save_upload("project_meta", run_dir)
        room_path = _save_upload("room_schedule", run_dir)
        stair_path = _save_upload("stair_schedule", run_dir)

        # Phase 19-C: scale + mode form fields. Default to 50.0 / full
        # so existing tests and bookmarked URLs keep working.
        try:
            ppm = float(request.form.get("points_per_meter", "50.0"))
        except ValueError:
            flash("points_per_meter 必须是数字（默认 50.0）。")
            return redirect(url_for("index"))
        if ppm <= 0:
            flash("points_per_meter 必须 > 0。")
            return redirect(url_for("index"))
        inspect_only = request.form.get("inspect_only") == "1"

        # Phase 19-D: min_room_area_m2 noise floor.
        try:
            min_room_area = float(request.form.get("min_room_area_m2", "1.0"))
        except ValueError:
            flash("min_room_area_m2 必须是数字（默认 1.0）。")
            return redirect(url_for("index"))
        if min_room_area < 0:
            flash("min_room_area_m2 不能为负（设 0 即关闭过滤）。")
            return redirect(url_for("index"))

        raw_sheet_region = request.form.get("sheet_region", "").strip()
        sheet_region = None
        if raw_sheet_region:
            from archkg.ingest.sheet_region import parse_sheet_region

            try:
                sheet_region = parse_sheet_region(raw_sheet_region)
            except ValueError as exc:
                flash(f"sheet_region 无效：{exc}")
                return redirect(url_for("index"))

        # Phase 20-A R1 P0: raster uploads need PIXELS-per-meter, not
        # PDF points-per-meter. Compute from the form's `image_dpi`
        # (default 200) compounded with `points_per_meter` (the
        # source CAD's metric scale): ppm_pixel = ppm_pdf * dpi / 72.
        # PIL-detected DPI metadata is unreliable on PNGs (fitz
        # exports often carry a bogus 96 DPI), so we trust the user's
        # form value.
        if ext in supported_raster_exts:
            try:
                form_dpi = float(request.form.get("image_dpi", "200"))
            except ValueError:
                flash("image_dpi 必须是数字（默认 200）。")
                return redirect(url_for("index"))
            if form_dpi <= 0:
                flash("image_dpi 必须 > 0。")
                return redirect(url_for("index"))
            ppm = ppm * form_dpi / 72.0
        use_ocr = ext in supported_raster_exts and request.form.get("use_ocr") == "1"

        try:
            run_pipeline(
                pdf_path,
                run_dir,
                project_meta_path=meta_path,
                room_schedule_path=room_path,
                stair_schedule_path=stair_path,
                points_per_meter=ppm,
                inspect_only=inspect_only,
                min_room_area_m2=min_room_area,
                sheet_region=sheet_region,
                use_ocr=use_ocr,
            )
        except Exception as exc:
            tb = traceback.format_exc()
            (run_dir / "ERROR.txt").write_text(tb, encoding="utf-8")
            flash(
                "审图失败 — 这通常意味着 builder 没识别出图纸的几何或 schedule "
                "项目 ID 不一致。原始错误已写到 run 目录的 ERROR.txt。\n\n"
                f"{type(exc).__name__}: {exc}"
            )
            return redirect(url_for("index"))

        return redirect(url_for("run_index", run_id=run_id))

    @app.route("/demo", methods=["GET"])
    def demo() -> Any:
        # samples/sample_clean.pdf + project_meta_demo.yaml + room_schedule_demo.yaml
        # + stair_schedule_demo.yaml — full PARTIAL_AUTODETECT exercise.
        repo_root = Path(__file__).resolve().parents[2]
        samples = repo_root / "samples"
        sample_pdf = samples / "sample_clean.pdf"
        if not sample_pdf.exists():
            flash(
                "samples/sample_clean.pdf 不在仓库里，无法跑 demo。请通过 "
                "`uv run python samples/make_sample.py` 重新生成。"
            )
            return redirect(url_for("index"))

        run_id = "demo-" + uuid.uuid4().hex[:8]
        run_dir = runs_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        # Copy demo inputs into the run dir so the run is self-contained
        # (matches the upload path's behaviour).
        shutil.copy(sample_pdf, run_dir / "sample_clean.pdf")
        for src in ("project_meta_demo.yaml", "room_schedule_demo.yaml", "stair_schedule_demo.yaml"):
            shutil.copy(samples / src, run_dir / src)

        try:
            run_pipeline(
                run_dir / "sample_clean.pdf",
                run_dir,
                project_meta_path=run_dir / "project_meta_demo.yaml",
                room_schedule_path=run_dir / "room_schedule_demo.yaml",
                stair_schedule_path=run_dir / "stair_schedule_demo.yaml",
            )
        except Exception as exc:
            tb = traceback.format_exc()
            (run_dir / "ERROR.txt").write_text(tb, encoding="utf-8")
            flash(f"demo 跑挂了 (这是 bug, 请提 issue): {type(exc).__name__}: {exc}")
            return redirect(url_for("index"))

        return redirect(url_for("run_index", run_id=run_id))

    @app.route("/runs/<run_id>/", methods=["GET"])
    def run_index(run_id: str) -> Any:
        run_dir = runs_dir / secure_filename(run_id)
        index_html = run_dir / "index.html"
        if not run_dir.is_dir() or not index_html.exists():
            print(
                f"studio · run_index 404: run_dir={run_dir} "
                f"is_dir={run_dir.is_dir()} index_exists={index_html.exists()}"
            )
            abort(404)
        return send_from_directory(run_dir.resolve(), "index.html")

    @app.route("/runs/<run_id>/<path:filename>", methods=["GET"])
    def run_artifact(run_id: str, filename: str) -> Any:
        run_dir = runs_dir / secure_filename(run_id)
        if not run_dir.is_dir():
            abort(404)
        # send_from_directory rejects '..' traversal automatically.
        return send_from_directory(run_dir.resolve(), filename)

    return app


def serve(
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    state_dir: Path | None = None,
    open_browser: bool = True,
    archkg_version: str = "1.3.0",
) -> None:
    if state_dir is None:
        state_dir = Path("tmp") / "studio"
    app = create_app(state_dir, archkg_version=archkg_version)

    url = f"http://{host}:{port}/"
    print(f"studio · serving {url}  (state: {state_dir})")
    print("studio · drag-drop a PDF or hit /demo for the bundled sample run.")
    if open_browser:
        import threading
        import webbrowser
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()

    # Disable Flask's debugger / reloader; this is a local user-facing
    # service, not a dev playground. Keep stdout quiet.
    app.run(host=host, port=port, debug=False, use_reloader=False)


__all__ = ["PipelineResult", "create_app", "run_pipeline", "serve"]
