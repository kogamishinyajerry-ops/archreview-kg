"""Assemble M6 product demo from REAL UI screen recording + voice cards.

Pipeline:
  1. Title card (PNG)              → 19.7s clip, gentle zoom-in
  2. Real UI demo recording        → 40.2s slice (t=8 to t=48.2), cropped to 16:9, scaled 1920x1080
  3. Closing card (PNG)            → 25.3s clip, gentle zoom-out
  4. Crossfade-concat the three
  5. Concatenate the three voiceover .wav files (with short silence between)
  6. Mux V + A into final mp4

Final duration ≈ 85.2s. Matches voiceover.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DEMO_DIR = ROOT / ".planning/m6/demo"
CAP_DIR = DEMO_DIR / "captures"
CARDS_DIR = DEMO_DIR / "cards"
CLIPS_DIR = DEMO_DIR / "clips_v2"
CLIPS_DIR.mkdir(exist_ok=True, parents=True)

W, H, FPS = 1920, 1080, 30
CROSSFADE_S = 0.4

# Voiceover segment durations (measured)
VO_INTRO = CAP_DIR / "vo_SHOT_INTRO.wav"
VO_DEMO = CAP_DIR / "vo_SHOT_DEMO_BODY.wav"
VO_CLOSE = CAP_DIR / "vo_SHOT_CLOSING.wav"
SILENCE_GAP_S = 0.6

# Card durations (slightly longer than VO so VO never overruns the visual)
INTRO_DUR = 19.8       # ≥ 19.74
DEMO_DUR = 40.3        # ≥ 40.16
CLOSE_DUR = 25.4       # ≥ 25.31
# UI demo slice — the most informative 40s of the 75s raw recording
UI_DEMO_START = 8.0
UI_DEMO_LEN = DEMO_DUR

FINAL = DEMO_DIR / "archreview_kg_demo_final.mp4"


def run(cmd: list[str]) -> None:
    print(">>>", " ".join(cmd[:7]), "...")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-3000:])
        raise RuntimeError(f"ffmpeg failed: {' '.join(cmd[:3])}")


def render_card_clip(png: Path, dur: float, zoom_dir: str, idx: int) -> Path:
    out = CLIPS_DIR / f"card_{idx}.mp4"
    n_frames = int(dur * FPS)
    if zoom_dir == "in":
        zexpr = f"min(1.0+0.05*on/{n_frames},1.05)"
    else:  # out
        zexpr = f"max(1.05-0.05*on/{n_frames},1.0)"
    filt = (
        f"scale={W*2}:{H*2}:flags=lanczos,"
        f"zoompan=z='{zexpr}':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
        f"s={W}x{H}:fps={FPS},"
        f"format=yuv420p"
    )
    run([
        "ffmpeg", "-y", "-loop", "1", "-framerate", str(FPS),
        "-t", f"{dur:.3f}", "-i", str(png),
        "-vf", filt,
        "-c:v", "libx264", "-preset", "medium", "-crf", "19",
        "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-an",
        str(out),
    ])
    return out


def render_ui_clip(src: Path, start: float, length: float) -> Path:
    """Slice + crop + scale the real UI recording to 1920x1080.

    Source is 3456x2234 retina. We crop menu-bar + dock+ Chrome chrome
    to leave a clean 16:9 of just the workbench content, then scale.
    """
    out = CLIPS_DIR / "ui.mp4"
    # Crop: top 150px (Chrome bookmarks + tabs/url bar visible), bottom 140px (dock).
    # 3456 x (2234-150-140) = 3456 x 1944 — exact 16:9.
    filt = (
        "crop=3456:1944:0:150,"
        f"scale={W}:{H}:flags=lanczos,"
        "format=yuv420p"
    )
    run([
        "ffmpeg", "-y",
        "-ss", f"{start:.3f}",
        "-i", str(src),
        "-t", f"{length:.3f}",
        "-vf", filt,
        "-c:v", "libx264", "-preset", "medium", "-crf", "19",
        "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-an",
        str(out),
    ])
    return out


def crossfade_concat(clips: list[Path], durations: list[float], out: Path) -> None:
    inputs: list[str] = []
    for c in clips:
        inputs.extend(["-i", str(c)])

    filter_parts: list[str] = []
    prev_label = "0:v"
    running = durations[0]
    for i in range(1, len(clips)):
        offset = running - CROSSFADE_S
        next_label = f"v{i}"
        filter_parts.append(
            f"[{prev_label}][{i}:v]xfade=transition=fade:duration={CROSSFADE_S}:offset={offset:.3f}[{next_label}]"
        )
        prev_label = next_label
        running = running + durations[i] - CROSSFADE_S

    run([
        "ffmpeg", "-y", *inputs,
        "-filter_complex", ";".join(filter_parts),
        "-map", f"[{prev_label}]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "19",
        "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-an",
        str(out),
    ])


def build_voiceover(out: Path) -> None:
    """Concatenate the 3 VO wavs with SILENCE_GAP_S between them."""
    silence = CLIPS_DIR / "silence.wav"
    run([
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", f"anullsrc=channel_layout=stereo:sample_rate=44100",
        "-t", f"{SILENCE_GAP_S}",
        str(silence),
    ])
    concat_list = CLIPS_DIR / "vo_concat.txt"
    with open(concat_list, "w") as f:
        for w in [VO_INTRO, silence, VO_DEMO, silence, VO_CLOSE]:
            f.write(f"file '{w}'\n")
    run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(concat_list),
        "-ar", "44100", "-ac", "2",
        str(out),
    ])


def mux(silent_v: Path, audio: Path, out: Path) -> None:
    run([
        "ffmpeg", "-y",
        "-i", str(silent_v),
        "-i", str(audio),
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k",
        "-map", "0:v:0", "-map", "1:a:0",
        str(out),
    ])


def main() -> None:
    title = CARDS_DIR / "title.png"
    closing = CARDS_DIR / "closing.png"
    raw = CAP_DIR / "raw_ui_demo.mov"
    assert title.exists(), title
    assert closing.exists(), closing
    assert raw.exists(), raw
    assert VO_INTRO.exists() and VO_DEMO.exists() and VO_CLOSE.exists()

    print("--- title card clip")
    c1 = render_card_clip(title, INTRO_DUR, "in", 1)
    print("--- UI demo clip (real screencap)")
    c2 = render_ui_clip(raw, UI_DEMO_START, UI_DEMO_LEN)
    print("--- closing card clip")
    c3 = render_card_clip(closing, CLOSE_DUR, "out", 3)

    silent = CLIPS_DIR / "silent_concat.mp4"
    print("\n--- crossfade-concat")
    crossfade_concat([c1, c2, c3], [INTRO_DUR, DEMO_DUR, CLOSE_DUR], silent)

    full_vo = CLIPS_DIR / "voiceover_full.wav"
    print("\n--- voiceover concat")
    build_voiceover(full_vo)

    print("\n--- mux")
    mux(silent, full_vo, FINAL)

    print(f"\n✅ {FINAL}")
    p = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration:stream=width,height,codec_name",
         "-of", "json", str(FINAL)],
        capture_output=True, text=True,
    )
    print(p.stdout)


if __name__ == "__main__":
    main()
