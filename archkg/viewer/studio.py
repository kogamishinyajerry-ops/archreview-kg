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


def run_pipeline(
    pdf_path: Path,
    out_dir: Path,
    *,
    project_meta_path: Path | None = None,
    room_schedule_path: Path | None = None,
    stair_schedule_path: Path | None = None,
    points_per_meter: float = 50.0,
    inspect_only: bool = False,
) -> PipelineResult:
    """End-to-end review on a single PDF.

    Same lane as `archkg review` but factored out so the studio's HTTP
    handler can call it directly. Writes primitives.json, entity_graph.json,
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
    """
    from archkg.annotate.pdf_annotator import annotate as annotate_pdf
    from archkg.annotate.report import render as render_report
    from archkg.graph.builder import build_graph, render_overlay
    from archkg.graph.builder import write_json as write_graph
    from archkg.ingest.primitive_extractor import extract
    from archkg.ingest.primitive_extractor import write_json as write_prims
    from archkg.knowledge.loader import load_rules, load_standards
    from archkg.rules.engine import evaluate
    from archkg.schemas import ProjectMeta

    out_dir.mkdir(parents=True, exist_ok=True)

    meta: ProjectMeta | None = None
    if project_meta_path is not None:
        raw = yaml.safe_load(project_meta_path.read_text("utf-8"))
        meta = ProjectMeta.model_validate(raw)
        (out_dir / "project_meta.yaml").write_text(
            yaml.safe_dump(meta.model_dump(), allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    primitives = extract(pdf_path, points_per_meter=points_per_meter)
    write_prims(primitives, out_dir / "primitives.json")
    graph = build_graph(primitives)

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
        graph = apply_room_schedule(graph, schedule).graph

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
        graph = apply_stair_schedule(graph, sched).graph

    graph_path = write_graph(graph, out_dir / "entity_graph.json")
    render_overlay(graph, pdf_path, out_dir / "entity_overlay.png")

    # Count entities from the in-memory typed graph directly so a future
    # serialisation shape change can't silently neuter the quality flags.
    quality_flags = _compute_quality_flags(graph)
    n_rooms = len(graph.rooms)
    n_doors = len(graph.doors)
    n_corridors = len(graph.corridors)

    # Codex P19-C R2 P0: persist mode + quality_flags so any downstream
    # renderer (archkg viewer, scripts that re-render index.html, future
    # web previews) honours the inspect_only semantics. Without this the
    # standalone `archkg viewer <run-dir>` would happily re-render an
    # inspect_only run as a green "0 violations" page.
    _write_run_meta(
        out_dir,
        mode="inspect_only" if inspect_only else "full",
        quality_flags=quality_flags,
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
) -> Path:
    """Persist the inspect-only / full mode + quality flags to a JSON file
    in the run directory. Read by archkg.viewer.server._render_index so
    any re-render of the run's index.html honours the inspect-only mode.

    Codex P19-C R2 P0: without this marker, `archkg viewer <run-dir>`
    re-renders inspect_only runs as full-success pages because it can't
    distinguish "0 issues because rules ran and found nothing" from "0
    issues because rules were skipped".
    """
    meta_path = out_dir / "run_meta.json"
    meta_path.write_text(
        json.dumps(
            {"mode": mode, "quality_flags": list(quality_flags)},
            ensure_ascii=False,
            indent=2,
        ),
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

    html = env.get_template("index.html.j2").render(
        source_pdf=str(source_pdf),
        created_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        issues=issues,
        stats=stats,
        report_md=report_md,
        quality_flags=list(quality_flags),
        mode=mode,
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
<title>ArchReview-KG Studio · 上传图纸自动审图</title>
<meta name="viewport" content="width=device-width, initial-scale=1" />
<style>
  :root {
    --bg: #0e1014;
    --panel: #161a22;
    --border: #2a3140;
    --text: #e6edf3;
    --muted: #7d8590;
    --blue: #2f81f7;
    --green: #3fb950;
    --orange: #f59e0b;
    --red: #f85149;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; font: 15px/1.55 -apple-system, BlinkMacSystemFont,
      "Segoe UI", "PingFang SC", "Hiragino Sans GB", sans-serif;
    background: var(--bg); color: var(--text);
  }
  .wrap { max-width: 880px; margin: 0 auto; padding: 36px 24px 80px; }
  header { padding-bottom: 22px; border-bottom: 1px solid var(--border); margin-bottom: 28px; }
  header h1 { margin: 0 0 6px; font-size: 26px; font-weight: 700; }
  header p { margin: 0; color: var(--muted); font-size: 14px; }
  .lede { background: var(--panel); border: 1px solid var(--border); border-radius: 10px;
          padding: 18px 22px; margin-bottom: 28px; font-size: 14px; line-height: 1.7; }
  .lede strong { color: var(--blue); }
  .lede ul { margin: 8px 0 0; padding-left: 24px; }
  .lede li { margin-bottom: 4px; }

  .drop {
    border: 2px dashed var(--border); border-radius: 14px;
    padding: 40px 24px; text-align: center; background: var(--panel);
    transition: border-color .15s, background .15s;
    cursor: pointer; margin-bottom: 22px;
  }
  .drop.over { border-color: var(--blue); background: rgba(47, 129, 247, 0.08); }
  .drop-icon { font-size: 32px; margin-bottom: 8px; }
  .drop-hint { color: var(--muted); font-size: 13px; margin-top: 4px; }
  .drop input[type=file] { display: none; }
  .file-pill {
    display: inline-flex; align-items: center; gap: 8px;
    padding: 6px 12px; border: 1px solid var(--border); border-radius: 999px;
    background: rgba(63, 185, 80, 0.08); color: var(--green);
    font-size: 13px; margin-top: 12px;
  }
  .file-pill .x { color: var(--muted); cursor: pointer; }

  details { margin-bottom: 16px; background: var(--panel);
            border: 1px solid var(--border); border-radius: 10px; padding: 12px 18px; }
  details summary { cursor: pointer; font-weight: 600; color: var(--text);
                    user-select: none; }
  details > div { padding-top: 10px; color: var(--muted); font-size: 13px; }
  details label { display: block; margin: 10px 0 4px; color: var(--text);
                  font-weight: 500; font-size: 14px; }
  details input[type=file] { display: block; padding: 6px 0; color: var(--muted);
                             font-family: inherit; font-size: 13px; width: 100%; }
  details a { color: var(--blue); text-decoration: none; }
  details a:hover { text-decoration: underline; }

  .actions { display: flex; gap: 12px; margin-top: 26px; align-items: center; }
  .btn {
    border: 0; padding: 12px 22px; border-radius: 8px; cursor: pointer;
    font: inherit; font-weight: 600; transition: transform .05s, opacity .15s;
  }
  .btn:active { transform: translateY(1px); }
  .btn-primary { background: var(--blue); color: #fff; font-size: 15px; }
  .btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
  .btn-ghost { background: transparent; color: var(--muted); border: 1px solid var(--border); }
  .btn-ghost:hover { color: var(--text); border-color: var(--blue); }

  .footer { margin-top: 36px; color: var(--muted); font-size: 12px; line-height: 1.7; }
  .footer code { background: var(--panel); padding: 2px 6px; border-radius: 4px; }
  .footer a { color: var(--blue); text-decoration: none; }

  .flashes { padding: 12px 18px; margin-bottom: 18px; border-radius: 8px;
             background: rgba(248, 81, 73, 0.08); border: 1px solid rgba(248, 81, 73, 0.4);
             color: var(--red); font-size: 14px; line-height: 1.6;
             white-space: pre-wrap; word-break: break-word; font-family: ui-monospace, monospace; }
</style>
</head>
<body>
<div class="wrap">
<header>
  <h1>ArchReview-KG Studio</h1>
  <p>v{{ version }} · 上传 PDF 平面图，自动审 GB 50096 / 50352 / 50016 / 50763 国标违规项</p>
</header>

{% with messages = get_flashed_messages() %}
  {% if messages %}
    {% for msg in messages %}<div class="flashes">{{ msg }}</div>{% endfor %}
  {% endif %}
{% endwith %}

<div class="lede">
<strong>这是评估阶段工具，不是即开即用生产服务</strong>。当前能力 (v{{ version }})：
<ul>
  <li>4 张规则可在任意 PDF 上直接判违规（户门净宽 / 走廊净宽 / 卧室面积 / 无障碍走廊）</li>
  <li>填 ProjectMeta YAML 解锁 5 张项目级规则（无障碍住房比例 + 4 张高层规则）</li>
  <li>填房间排表 YAML 解锁 4 张净高 / 楼层 / 坡屋顶规则</li>
  <li>填楼梯排表 YAML 解锁 5 张楼梯踏步 / 踢面 / 扶手规则</li>
  <li>另有 18 张人工核对清单 (severity=info) 自动生成</li>
</ul>
不填 YAML 也能跑，但只触发 4 张直判规则；其它 reminder 占多数。
</div>

<form method="post" action="{{ url_for('review') }}" enctype="multipart/form-data" id="reviewForm">

<label class="drop" id="drop">
  <input type="file" name="pdf" id="pdfInput" accept="application/pdf" required />
  <div class="drop-icon">📄</div>
  <div><strong>把 PDF 平面图拖到这里</strong>，或点击选择</div>
  <div class="drop-hint">单页 / 多页都支持。当前以工程 PDF 为主，扫描版未做鲁棒性测试。</div>
  <div id="fileChosen"></div>
</label>

<details>
<summary>📋 ProjectMeta YAML（可选 · 解锁 5 张项目级规则）</summary>
<div>
  <p>项目级元数据：建筑类型 / 高度类别 / 层数 / 户数 / 耐火等级 / 气候区。
  模板见 <a href="https://github.com/kogamishinyajerry-ops/archreview-kg/blob/main/samples/project_meta_demo.yaml" target="_blank">samples/project_meta_demo.yaml</a>。</p>
  <label>project_meta.yaml</label>
  <input type="file" name="project_meta" accept=".yaml,.yml" />
</div>
</details>

<details>
<summary>🏠 房间排表 YAML（可选 · 解锁 4 张净高 / 楼层 / 坡屋顶规则）</summary>
<div>
  <p>每个房间的剖面信息：净高 / 所在楼层（地下室 / 地面层 / 上层 / 夹层）/ 是否坡屋顶 / 主截面净高。
  模板见 <a href="https://github.com/kogamishinyajerry-ops/archreview-kg/blob/main/samples/room_schedule_demo.yaml" target="_blank">samples/room_schedule_demo.yaml</a>。
  <em>需要同时填 ProjectMeta YAML，schedule 的 project_id 必须与 meta 一致。</em></p>
  <label>room_schedule.yaml</label>
  <input type="file" name="room_schedule" accept=".yaml,.yml" />
</div>
</details>

<details>
<summary>🪜 楼梯排表 YAML（可选 · 解锁 5 张楼梯规则）</summary>
<div>
  <p>每个楼梯实体的尺寸：踏步宽 / 踢面高 / 梯段净宽 / 扶手高 / 梯井净宽。
  模板见 <a href="https://github.com/kogamishinyajerry-ops/archreview-kg/blob/main/samples/stair_schedule_demo.yaml" target="_blank">samples/stair_schedule_demo.yaml</a>。
  <em>同样需要 ProjectMeta YAML。</em></p>
  <label>stair_schedule.yaml</label>
  <input type="file" name="stair_schedule" accept=".yaml,.yml" />
</div>
</details>

<details>
<summary>⚙️ 高级参数（PDF 比例尺 / 模式选择）</summary>
<div>
  <p><strong>points_per_meter (ppm)</strong>: PDF 中每米对应多少 PostScript 点。
  Archicad / Revit 默认导出值约为 50；AutoCAD 用英制单位时按 1 inch = 72 pt 推算（如 1:50 平面 ≈ 0.5 m = 36 pt → ppm ≈ 72）。
  不确定就先用 50，看实体数量是否合理；不合理再调。</p>
  <label>points_per_meter</label>
  <input type="number" name="points_per_meter" step="0.1" min="0.1" value="50.0"
         style="width: 100px; padding: 4px 8px; background: var(--bg);
                border: 1px solid var(--border); border-radius: 4px; color: var(--text);" />

  <p style="margin-top: 16px;"><strong>模式</strong>: 仅识图模式只跑实体提取 + 图谱构建，跳过规则评估。
  适合在不熟悉的 PDF 上先看 builder 检出多少 rooms / doors / corridors 是否合理，
  再决定要不要让规则引擎评估违规（避免被噪声违规淹没）。</p>
  <label>
    <input type="checkbox" name="inspect_only" value="1" />
    🔍 仅识图模式（跳过规则评估，只看 builder 检出实体）
  </label>
</div>
</details>

<div class="actions">
  <button type="submit" class="btn btn-primary" id="submitBtn">▶ 跑审图</button>
  <a href="{{ url_for('demo') }}" class="btn btn-ghost">没图纸？跑内置 demo</a>
</div>
</form>

<div class="footer">
完整 README · <a href="https://github.com/kogamishinyajerry-ops/archreview-kg" target="_blank">GitHub</a> ·
能力分级 <code>archkg clause readiness</code> ·
对抗 lane 21/32 rules at F1=1.00.<br/>
本地服务，所有数据只在你这台机器上处理。
</div>

</div>

<script>
const drop = document.getElementById('drop');
const pdfInput = document.getElementById('pdfInput');
const chosen = document.getElementById('fileChosen');
const form = document.getElementById('reviewForm');
const submitBtn = document.getElementById('submitBtn');

function showFile(file) {
  if (file) {
    chosen.innerHTML = '<div class="file-pill">' + file.name +
      ' <span class="x" onclick="event.preventDefault(); pdfInput.value=\'\'; document.getElementById(\'fileChosen\').innerHTML=\'\';">×</span></div>';
  } else { chosen.innerHTML = ''; }
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
  submitBtn.disabled = true;
  submitBtn.textContent = '⏳ 处理中…大约 3 秒';
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


def create_app(state_dir: Path, *, archkg_version: str = "1.2.1") -> Flask:
    """Build the Flask app. state_dir holds the per-run output directories."""
    runs_dir = state_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)

    app = Flask(__name__, static_folder=None, template_folder=None)
    # Studio is a single-user local tool; secret key is only used for flash().
    app.secret_key = "archkg-studio-local-dev"

    @app.route("/", methods=["GET"])
    def index() -> str:
        return render_template_string(STUDIO_HTML, version=archkg_version)

    @app.route("/review", methods=["POST"])
    def review() -> Any:
        run_id = uuid.uuid4().hex[:12]
        run_dir = runs_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        pdf = request.files.get("pdf")
        if pdf is None or not pdf.filename:
            flash("请上传 PDF 平面图。")
            return redirect(url_for("index"))

        safe_pdf_name = secure_filename(pdf.filename) or "input.pdf"
        if not safe_pdf_name.lower().endswith(".pdf"):
            safe_pdf_name += ".pdf"
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

        try:
            run_pipeline(
                pdf_path,
                run_dir,
                project_meta_path=meta_path,
                room_schedule_path=room_path,
                stair_schedule_path=stair_path,
                points_per_meter=ppm,
                inspect_only=inspect_only,
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
    archkg_version: str = "1.2.1",
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
