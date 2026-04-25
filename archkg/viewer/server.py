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
from datetime import datetime
from importlib.resources import files
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape


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

    issues = json.loads(issues_path.read_text("utf-8")) if issues_path.exists() else []
    graph = json.loads(graph_path.read_text("utf-8")) if graph_path.exists() else {}
    primitives = (
        json.loads(primitives_path.read_text("utf-8")) if primitives_path.exists() else {}
    )
    report_md = report_path.read_text("utf-8") if report_path.exists() else "(report.md missing)"

    n_lines = sum(len(p.get("lines", [])) for p in primitives.get("pages", []))
    n_texts = sum(len(p.get("texts", [])) for p in primitives.get("pages", []))
    applicable = len(graph.get("rooms", [])) + len(graph.get("doors", [])) + len(graph.get("corridors", []))

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
    )
    index_path = out_dir / "index.html"
    index_path.write_text(html, encoding="utf-8")
    return index_path


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
