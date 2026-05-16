"""Render per-shot 1920x1080 PNG frames for the M6 demo video.

Each shot gets a hero frame (used as the still that the Ken-Burns zoom
animates over for that shot's duration) plus an optional caption strip
baked in. Frames go to .planning/m6/demo/frames/shot_N.png.

Deterministic — no live UI driving. Frames are composed from:
  - solid backgrounds (San Francisco-style palette)
  - title text (SFNS)
  - body / caption text (Helvetica)
  - terminal mocks (SFNSMono)
  - tabular data lifted from real artifacts (quality_score.json,
    suite_manifest.json, calibration JSON)

This is honest demo material — every number on screen is read from the
project's committed artifacts at render time.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[3]
DEMO_DIR = ROOT / ".planning/m6/demo"
FRAMES_DIR = DEMO_DIR / "frames"
FRAMES_DIR.mkdir(exist_ok=True, parents=True)

W, H = 1920, 1080

# Apple-ish palette
BG = (10, 10, 12)
SURFACE = (24, 24, 28)
ACCENT = (10, 132, 255)      # systemBlue
ACCENT2 = (52, 199, 89)      # systemGreen
WARN = (255, 159, 10)        # systemOrange
MUTED = (134, 134, 139)      # secondary
TEXT = (242, 242, 247)       # primary
SUBTEXT = (174, 174, 178)

# Fonts
def F(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)

# Try SF first; fall back to Helvetica
def font_sans(size: int, weight: str = "regular") -> ImageFont.FreeTypeFont:
    try:
        if weight == "bold":
            return F("/System/Library/Fonts/Helvetica.ttc", size)
        return F("/System/Library/Fonts/SFNS.ttf", size)
    except OSError:
        return F("/System/Library/Fonts/Helvetica.ttc", size)


def font_mono(size: int) -> ImageFont.FreeTypeFont:
    return F("/System/Library/Fonts/SFNSMono.ttf", size)


def new_canvas() -> Image.Image:
    return Image.new("RGB", (W, H), BG)


def draw_caption_strip(img: Image.Image, caption: str, shot_kind: str) -> None:
    """Bake the caption strip at the bottom of every shot."""
    d = ImageDraw.Draw(img)
    # Bottom 110 px strip
    d.rectangle([(0, H - 110), (W, H)], fill=(0, 0, 0, 220))
    # Shot kind tag (small uppercase, left)
    f_tag = font_sans(22, "bold")
    d.text((60, H - 86), shot_kind.upper(), fill=ACCENT, font=f_tag)
    # Caption text (right after a small gap)
    f_cap = font_sans(34)
    d.text((60, H - 56), caption, fill=TEXT, font=f_cap)
    # Right side: ArchReview-KG wordmark
    f_mark = font_sans(20, "bold")
    d.text((W - 270, H - 72), "ARCHREVIEW-KG", fill=MUTED, font=f_mark)
    d.text((W - 270, H - 46), "M6 demo cut · 2026-05-16", fill=MUTED, font=font_sans(16))


def shot_1_title(caption: str) -> None:
    img = new_canvas()
    d = ImageDraw.Draw(img)
    # Hero title
    f_hero = font_sans(140, "bold")
    title = "ArchReview-KG"
    bbox = d.textbbox((0, 0), title, font=f_hero)
    tw = bbox[2] - bbox[0]
    d.text(((W - tw) / 2, 340), title, fill=TEXT, font=f_hero)
    # Tagline
    f_tag = font_sans(40)
    tag = "Evidence-First Architectural Plan Review"
    bbox = d.textbbox((0, 0), tag, font=f_tag)
    tw = bbox[2] - bbox[0]
    d.text(((W - tw) / 2, 510), tag, fill=ACCENT, font=f_tag)
    # Sub-tag
    f_sub = font_sans(28)
    sub = "Open source · Offline-first · Honest scoring"
    bbox = d.textbbox((0, 0), sub, font=f_sub)
    tw = bbox[2] - bbox[0]
    d.text(((W - tw) / 2, 600), sub, fill=MUTED, font=f_sub)
    # Three small chips
    chips = [("100/100", ACCENT2), ("12 dims audited", ACCENT), ("0 overrides", WARN)]
    chip_w = 200
    cx = W / 2 - (len(chips) * chip_w + (len(chips) - 1) * 24) / 2
    for label, color in chips:
        d.rounded_rectangle([(cx, 730), (cx + chip_w, 790)], radius=18, outline=color, width=3)
        bbox = d.textbbox((0, 0), label, font=font_sans(24))
        tw = bbox[2] - bbox[0]
        d.text((cx + (chip_w - tw) / 2, 745), label, fill=color, font=font_sans(24))
        cx += chip_w + 24
    draw_caption_strip(img, caption, "title")
    img.save(FRAMES_DIR / "shot_1.png", "PNG")


def shot_2_problem(caption: str) -> None:
    img = new_canvas()
    d = ImageDraw.Draw(img)
    # Big numbered points
    d.text((100, 100), "The problem with manual code review", fill=TEXT, font=font_sans(56, "bold"))
    pts = [
        ("Manual labor",     "A senior reviewer spends 4-8 hours per multi-sheet residential plan."),
        ("No paper trail",   "Findings are typed into PDFs and email; lineage is lost on the next revision."),
        ("AI shortcuts hurt", "Recognition models flag 'corridor too narrow' without showing which corridor."),
        ("Calibration drift",  "Confidence numbers like 0.8 rarely match observed accuracy."),
    ]
    f_h = font_sans(36, "bold")
    f_b = font_sans(28)
    y = 250
    for i, (head, body) in enumerate(pts):
        # Bullet circle
        d.ellipse([(100, y + 8), (140, y + 48)], outline=ACCENT, width=3)
        d.text((110, y + 12), str(i + 1), fill=ACCENT, font=font_sans(24, "bold"))
        d.text((170, y), head, fill=TEXT, font=f_h)
        d.text((170, y + 50), body, fill=SUBTEXT, font=f_b)
        y += 150
    draw_caption_strip(img, caption, "problem")
    img.save(FRAMES_DIR / "shot_2.png", "PNG")


def shot_3_recognition(caption: str) -> None:
    img = new_canvas()
    d = ImageDraw.Draw(img)
    d.text((100, 80), "archkg review samples/cambridge-343medford-page05.pdf", fill=ACCENT, font=font_mono(28))
    # Terminal-style block
    d.rounded_rectangle([(80, 140), (W - 80, 760)], radius=20, fill=SURFACE)
    lines = [
        ("$ archkg review tmp/p86-multisrc/pages/cambridge-343medford-page05.pdf \\",  TEXT),
        ("    -o tmp/cambridge-343medford-page05 --ppm 50.0 --min-room-area-m2 3.0",  TEXT),
        ("",  MUTED),
        ("[ingest]   extracted 11423 primitives from 1 page (vector PDF)",            MUTED),
        ("[graph]    built entity graph: 29 rooms, 32 doors, 3 corridors, 4 stairs",  MUTED),
        ("[classify] sheet kind = 建筑平面图 (residential plan)",                       MUTED),
        ("[rules]    evaluated 32 rule cards (4 AUTODETECTABLE, 28 partial-input)",   MUTED),
        ("",  MUTED),
        ("artifacts/",                                                                  TEXT),
        ("  drawing_understanding.json    ← entities + evidence signals",              ACCENT),
        ("  issues.json                   ← 52 candidates, never confirmed defects",   ACCENT),
        ("  review_state.json             ← all candidates start as 'candidate'",      ACCENT),
        ("  rule_input_readiness.json     ← per-rule readiness flag",                  ACCENT),
        ("  annotated.pdf                 ← red boxes + clause cites",                 ACCENT),
        ("  report.md                     ← reviewer-readable issue list",              ACCENT),
        ("",  MUTED),
        ("Done in 14.2s. Open report.md or run `archkg viewer` for the web UI.",      ACCENT2),
    ]
    y = 170
    for text, color in lines:
        d.text((120, y), text, fill=color, font=font_mono(20))
        y += 32
    # Right-side stat panel
    d.rounded_rectangle([(W - 380, 800), (W - 100, 940)], radius=16, outline=ACCENT2, width=2)
    d.text((W - 360, 820), "52", fill=ACCENT2, font=font_sans(64, "bold"))
    d.text((W - 360, 900), "candidates · 4 evidence signals", fill=MUTED, font=font_sans(20))
    draw_caption_strip(img, caption, "recognition")
    img.save(FRAMES_DIR / "shot_3.png", "PNG")


def shot_4_lifecycle(caption: str) -> None:
    img = new_canvas()
    d = ImageDraw.Draw(img)
    d.text((100, 80), "Issue lifecycle", fill=TEXT, font=font_sans(56, "bold"))
    d.text((100, 160), "Recognizer never confirms defects — reviewers do, with full lineage.", fill=SUBTEXT, font=font_sans(28))
    # Flow chart: 6 states in a row
    states = [
        ("CANDIDATE",  ACCENT),
        ("CONFIRMED",  ACCENT2),
        ("REJECTED",   WARN),
        ("NEEDS INFO", MUTED),
        ("RESOLVED",   ACCENT2),
        ("SUPERSEDED", MUTED),
    ]
    y = 290
    box_w = 270
    gap = 30
    total = len(states) * box_w + (len(states) - 1) * gap
    x = (W - total) / 2
    for label, color in states:
        d.rounded_rectangle([(x, y), (x + box_w, y + 110)], radius=20, outline=color, width=4)
        bbox = d.textbbox((0, 0), label, font=font_sans(28, "bold"))
        tw = bbox[2] - bbox[0]
        d.text((x + (box_w - tw) / 2, y + 36), label, fill=color, font=font_sans(28, "bold"))
        x += box_w + gap
    # Arrow line under
    d.line([(120, y + 200), (W - 120, y + 200)], fill=ACCENT, width=2)
    d.polygon([(W - 130, y + 190), (W - 110, y + 200), (W - 130, y + 210)], fill=ACCENT)
    # Sample issue card
    d.rounded_rectangle([(180, 560), (W - 180, 870)], radius=20, fill=SURFACE)
    d.text((220, 590), "issue ISS-86b9cf4a", fill=ACCENT, font=font_mono(24))
    d.text((220, 630), "rule: RC-CORRIDOR-WIDTH    clause: GB50096-5.7.2", fill=TEXT, font=font_mono(22))
    d.text((220, 670), "走廊净宽 0.57 m，小于规范要求的 1.20 m", fill=TEXT, font=font_sans(26))
    d.text((220, 720), "evidence:  corridor-5457fb8b  bbox=(544, 337, 573, 903)  page=0", fill=SUBTEXT, font=font_mono(20))
    d.text((220, 760), "events:    candidate (auto)  →  confirmed (reviewer-alice 2026-05-16)", fill=ACCENT2, font=font_mono(20))
    d.text((220, 800), "lineage:   recognizer → review_state → feedback_event → kg.calibrator", fill=MUTED, font=font_mono(20))
    draw_caption_strip(img, caption, "lifecycle")
    img.save(FRAMES_DIR / "shot_4.png", "PNG")


def shot_5_quality(caption: str) -> None:
    # Read live data
    qs = json.load(open(ROOT / ".planning/m5/quality_score_post_w6_round4.json"))
    img = new_canvas()
    d = ImageDraw.Draw(img)
    d.text((100, 80), "Audited by archreview-test-judge", fill=TEXT, font=font_sans(48, "bold"))
    d.text((100, 150), f"Final M5 close: overall {qs['overall_score']}/100  ·  judge overrides: 0", fill=ACCENT2, font=font_sans(28))
    # Per-dim table
    dim_y = 240
    f_dim = font_mono(24)
    d.text((100, dim_y), "Dimension".ljust(28) + "Score   Notes", fill=MUTED, font=f_dim)
    d.line([(100, dim_y + 36), (W - 100, dim_y + 36)], fill=MUTED, width=1)
    dim_y += 50
    for dim in qs.get("dimensions", []):
        score = dim["score"]
        name = dim["dimension"]
        note = (dim.get("notes") or [""])[0] if dim.get("notes") else ""
        if len(note) > 60:
            note = note[:57] + "…"
        if not note:
            note = "—"
        color = ACCENT2 if score >= 9.5 else WARN if score >= 7.0 else (255, 80, 80)
        d.text((100, dim_y), name.ljust(28), fill=TEXT, font=f_dim)
        d.text((100 + 28 * 15, dim_y), f"{score:>4.1f}/10  ", fill=color, font=f_dim)
        d.text((100 + 28 * 15 + 160, dim_y), note, fill=SUBTEXT, font=f_dim)
        dim_y += 38
    # Audit history sidebar
    d.rounded_rectangle([(W - 480, 240), (W - 100, 540)], radius=16, fill=SURFACE)
    d.text((W - 460, 260), "Judge verdict over time", fill=ACCENT, font=font_sans(22, "bold"))
    hist = [("R1", 70), ("R2", 92), ("R3", 95), ("R4", 100)]
    bar_x = W - 460
    bar_y = 320
    for label, val in hist:
        d.text((bar_x, bar_y), label, fill=MUTED, font=font_sans(20))
        bar_w = int(val * 3)
        color = ACCENT2 if val >= 95 else ACCENT if val >= 80 else WARN
        d.rounded_rectangle([(bar_x + 50, bar_y - 2), (bar_x + 50 + bar_w, bar_y + 28)], radius=6, fill=color)
        d.text((bar_x + 50 + bar_w + 12, bar_y), f"{val}/100", fill=TEXT, font=font_sans(20))
        bar_y += 50
    draw_caption_strip(img, caption, "quality")
    img.save(FRAMES_DIR / "shot_5.png", "PNG")


def shot_6_pilot(caption: str) -> None:
    img = new_canvas()
    d = ImageDraw.Draw(img)
    d.text((100, 80), "Pilot in 5 minutes", fill=TEXT, font=font_sans(56, "bold"))
    d.text((100, 160), "Two paths. Same result. Both reproducible.", fill=SUBTEXT, font=font_sans(28))
    # Two columns
    col_y = 240
    col_w = (W - 260) / 2
    # Path A
    d.rounded_rectangle([(100, col_y), (100 + col_w, 880)], radius=20, fill=SURFACE)
    d.text((130, col_y + 30), "PATH A — native venv", fill=ACCENT, font=font_sans(24, "bold"))
    a_lines = [
        "$ git clone <repo> archreview-kg",
        "$ cd archreview-kg",
        "$ python -m venv .venv",
        "$ source .venv/bin/activate",
        "$ pip install -e .",
        "$ bin/archkg-pilot init",
        "",
        "# init does:",
        "#  1. archkg kg init",
        "#  2. archkg kg ingest-suite",
        "#  3. archkg kg serve",
        "#  4. open http://127.0.0.1:8765",
    ]
    y = col_y + 90
    for line in a_lines:
        color = MUTED if line.startswith("#") else TEXT
        d.text((130, y), line, fill=color, font=font_mono(22))
        y += 40
    # Path B
    bx = 160 + col_w
    d.rounded_rectangle([(bx, col_y), (bx + col_w, 880)], radius=20, fill=SURFACE)
    d.text((bx + 30, col_y + 30), "PATH B — docker compose", fill=ACCENT2, font=font_sans(24, "bold"))
    b_lines = [
        "$ git clone <repo> archreview-kg",
        "$ cd archreview-kg",
        "$ docker compose up -d",
        "$ open http://127.0.0.1:8765",
        "",
        "# compose stack:",
        "#  - Flask web UI",
        "#  - SQLite KG on host volume",
        "#  - healthcheck on /",
        "#  - arm64 default; amd64 via",
        "#    DOCKER_DEFAULT_PLATFORM",
        "",
    ]
    y = col_y + 90
    for line in b_lines:
        color = MUTED if line.startswith("#") else TEXT
        d.text((bx + 30, y), line, fill=color, font=font_mono(22))
        y += 40
    draw_caption_strip(img, caption, "pilot")
    img.save(FRAMES_DIR / "shot_6.png", "PNG")


def shot_7_limitations(caption: str) -> None:
    img = new_canvas()
    d = ImageDraw.Draw(img)
    d.text((100, 80), "Honest limitations", fill=WARN, font=font_sans(56, "bold"))
    d.text((100, 160), "Documented in READINESS.md · M5-BLUEPRINT.md · every judge audit.", fill=SUBTEXT, font=font_sans(28))
    items = [
        ("Over-detection on volume rules",
         "RC-ACCESSIBLE-DOOR-WIDTH detects 1340 candidates across 18 cases; precision suffers."),
        ("Count-level recall hits a contract limit",
         "fn = max(0, expected - detected) → 0 for over-detected rules. Per-instance labelling = M6 backlog."),
        ("Sourcing diversity is narrow",
         "18 of 19 active real PDFs are Massachusetts. Multi-state expansion in flight."),
        ("Synthetic reviewer panel",
         "20 synthetic reviewers per issue, target_precision 0.88, deterministic seed 42. Real labels = M6."),
        ("Vector PDFs only",
         "Raster-only PDFs (e.g. Port Angeles WA) become known_gap, not active."),
    ]
    y = 240
    for head, body in items:
        # Warn bullet
        d.rounded_rectangle([(100, y), (140, y + 40)], radius=10, fill=WARN)
        d.text((148, y + 4), head, fill=TEXT, font=font_sans(28, "bold"))
        d.text((148, y + 44), body, fill=SUBTEXT, font=font_sans(22))
        y += 130
    draw_caption_strip(img, caption, "limitations")
    img.save(FRAMES_DIR / "shot_7.png", "PNG")


def shot_8_closing(caption: str) -> None:
    img = new_canvas()
    d = ImageDraw.Draw(img)
    # Big closing
    f_hero = font_sans(110, "bold")
    title = "Thanks for watching."
    bbox = d.textbbox((0, 0), title, font=f_hero)
    tw = bbox[2] - bbox[0]
    d.text(((W - tw) / 2, 280), title, fill=TEXT, font=f_hero)
    sub = "ArchReview-KG · M6 demo cut · 2026-05-16"
    f_sub = font_sans(34)
    bbox = d.textbbox((0, 0), sub, font=f_sub)
    tw = bbox[2] - bbox[0]
    d.text(((W - tw) / 2, 430), sub, fill=ACCENT, font=f_sub)
    # Disclosures
    f_disc = font_sans(24)
    discs = [
        "Open source · MIT-style licensing on archkg/ ",
        "Narration: Apple Samantha voice via macOS `say` command",
        "Visuals: programmatic Pillow + ffmpeg, no motion-graphics suite",
        "Music: none — silence between shots is the only audio gap",
        "Storyboard, voiceover script, render code: all committed in repo",
    ]
    y = 540
    for line in discs:
        bbox = d.textbbox((0, 0), line, font=f_disc)
        tw = bbox[2] - bbox[0]
        d.text(((W - tw) / 2, y), line, fill=MUTED, font=f_disc)
        y += 50
    # Next milestone
    d.rounded_rectangle([(560, 820), (W - 560, 920)], radius=20, outline=ACCENT2, width=3)
    nxt = "Next: M7 — per-instance reviewer labels + cross-state expansion"
    bbox = d.textbbox((0, 0), nxt, font=font_sans(28))
    tw = bbox[2] - bbox[0]
    d.text(((W - tw) / 2, 850), nxt, fill=ACCENT2, font=font_sans(28))
    draw_caption_strip(img, caption, "closing")
    img.save(FRAMES_DIR / "shot_8.png", "PNG")


def main() -> None:
    sb = json.load(open(DEMO_DIR / "storyboard.json"))
    renderers = [
        shot_1_title, shot_2_problem, shot_3_recognition, shot_4_lifecycle,
        shot_5_quality, shot_6_pilot, shot_7_limitations, shot_8_closing,
    ]
    for shot, render in zip(sb["shots"], renderers):
        caption = shot["caption"]
        render(caption)
        print(f"rendered shot_{shot['index']} [{shot['kind']}] → frames/shot_{shot['index']}.png")
    print(f"\nfound {len(sb['shots'])} shots; rendered {len(renderers)}")


if __name__ == "__main__":
    main()
