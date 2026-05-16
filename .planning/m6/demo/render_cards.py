"""Render title + closing card frames for the M6 product demo.

Two 1920x1080 PNGs that bookend the real UI screen recording. Style
matches the workbench's Apple-tier palette so the cuts feel native.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[3]
OUT_DIR = ROOT / ".planning/m6/demo/cards"
OUT_DIR.mkdir(exist_ok=True, parents=True)

W, H = 1920, 1080
BG = (10, 10, 12)
SURFACE = (28, 28, 30)
ACCENT = (10, 132, 255)   # systemBlue
ACCENT2 = (52, 199, 89)   # systemGreen
WARN = (255, 159, 10)     # systemOrange
TEXT = (245, 245, 247)
MUTED = (110, 110, 115)

FONT_PATHS = [
    "/System/Library/Fonts/SFNS.ttf",
    "/System/Library/Fonts/Supplemental/Helvetica.ttc",
    "/Library/Fonts/Helvetica.ttc",
]


def font(size: int) -> ImageFont.FreeTypeFont:
    for p in FONT_PATHS:
        try:
            return ImageFont.truetype(p, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def measure(draw: ImageDraw.ImageDraw, text: str, fnt) -> tuple[int, int]:
    bbox = draw.textbbox((0, 0), text, font=fnt)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def gradient_logo(im: Image.Image, cx: int, cy: int, size: int) -> None:
    draw = ImageDraw.Draw(im, "RGBA")
    for i in range(size):
        t = i / max(1, size - 1)
        r = int(10 + (94 - 10) * t)
        g = int(132 + (92 - 132) * t)
        b = int(255 + (230 - 255) * t)
        draw.rectangle((cx - size // 2, cy - size // 2 + i, cx + size // 2, cy - size // 2 + i + 1),
                       fill=(r, g, b, 255))
    # rounded mask
    mask = Image.new("L", (size, size), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle((0, 0, size, size), radius=size // 4, fill=255)
    # apply by recompositing
    logo_box = (cx - size // 2, cy - size // 2, cx + size // 2, cy + size // 2)
    region = im.crop(logo_box)
    region.putalpha(mask)
    bg = Image.new("RGB", region.size, BG)
    bg.paste(region, mask=region.split()[3])
    im.paste(bg, logo_box)


def render_title() -> Path:
    im = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(im)

    # Branded logo block centred horizontally, upper third
    logo_size = 120
    cx, cy = W // 2, 280
    gradient_logo(im, cx, cy, logo_size)

    # Hero title
    title = "ArchReview-KG"
    tfnt = font(120)
    tw, th = measure(draw, title, tfnt)
    draw.text(((W - tw) // 2, 380), title, fill=TEXT, font=tfnt)

    subtitle = "Evidence-First Plan Review"
    sfnt = font(54)
    sw, sh = measure(draw, subtitle, sfnt)
    draw.text(((W - sw) // 2, 530), subtitle, fill=MUTED, font=sfnt)

    # Status chips
    chips = [
        ("33 plans", ACCENT),
        ("148 issues", WARN),
        ("25 rules", ACCENT2),
        ("Offline · Open source", MUTED),
    ]
    chip_fnt = font(32)
    gap = 28
    total_w = 0
    sizes = []
    for label, _ in chips:
        bw, bh = measure(draw, label, chip_fnt)
        sizes.append((bw + 48, bh + 24))
        total_w += bw + 48 + gap
    total_w -= gap
    x = (W - total_w) // 2
    y = 680
    for (label, color), (cw, ch) in zip(chips, sizes):
        draw.rounded_rectangle((x, y, x + cw, y + ch), radius=ch // 2,
                               outline=color, width=2)
        bw, bh = measure(draw, label, chip_fnt)
        draw.text((x + (cw - bw) // 2, y + (ch - bh) // 2 - 4), label,
                  fill=color, font=chip_fnt)
        x += cw + gap

    # Watch directive
    watch = "watch the workbench drive itself"
    wfnt = font(36)
    ww, wh = measure(draw, watch, wfnt)
    draw.text(((W - ww) // 2, 820), watch, fill=TEXT, font=wfnt)

    # Footer
    footer = "ARCHREVIEW-KG · M6 product demo · 2026-05-16"
    ffnt = font(22)
    fw, fh = measure(draw, footer, ffnt)
    draw.text(((W - fw) // 2, H - 70), footer, fill=MUTED, font=ffnt)

    out = OUT_DIR / "title.png"
    im.save(out, "PNG")
    print(f"wrote {out}")
    return out


def render_closing() -> Path:
    im = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(im)

    title = "Thanks for watching"
    tfnt = font(110)
    tw, th = measure(draw, title, tfnt)
    draw.text(((W - tw) // 2, 280), title, fill=TEXT, font=tfnt)

    sub = "Open source. Offline. Honest."
    sfnt = font(54)
    sw, sh = measure(draw, sub, sfnt)
    draw.text(((W - sw) // 2, 430), sub, fill=ACCENT2, font=sfnt)

    lines = [
        ("Recogniser is rule-based and inspectable", ACCENT),
        ("Reviewer verdicts live in a separate review_state artifact", MUTED),
        ("AI advisor features intentionally NOT exposed in this pilot", WARN),
        ("Run docker compose up to evaluate locally in 5 minutes", ACCENT2),
    ]
    line_fnt = font(34)
    y = 580
    for text, color in lines:
        # bullet dot
        dot_x = 360
        draw.ellipse((dot_x, y + 14, dot_x + 14, y + 28), fill=color)
        draw.text((dot_x + 32, y), text, fill=TEXT, font=line_fnt)
        y += 60

    nxt = "Next milestone: real human reviewer labels"
    nfnt = font(30)
    nw, nh = measure(draw, nxt, nfnt)
    draw.text(((W - nw) // 2, H - 130), nxt, fill=MUTED, font=nfnt)

    footer = "ARCHREVIEW-KG · github · open source · 2026-05-16"
    ffnt = font(22)
    fw, fh = measure(draw, footer, ffnt)
    draw.text(((W - fw) // 2, H - 70), footer, fill=MUTED, font=ffnt)

    out = OUT_DIR / "closing.png"
    im.save(out, "PNG")
    print(f"wrote {out}")
    return out


if __name__ == "__main__":
    render_title()
    render_closing()
