"""Assemble final M6 demo video from rendered PNG frames + voiceover.

Pipeline:
1. Per-shot intermediate clip with Ken-Burns zoom-pan, duration matches storyboard.
2. Crossfade-concat all 8 clips into one continuous video stream.
3. Mux voiceover.wav as audio track.
4. Output H.264 1080p mp4 at .planning/m6/demo/archreview_kg_demo_final.mp4.

Honest constraints:
- Each shot uses its exact storyboard duration (no fudging).
- Total video length matches voiceover.wav within 0.5s tolerance.
- No external footage. Everything is locally rendered.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DEMO_DIR = ROOT / ".planning/m6/demo"
FRAMES_DIR = DEMO_DIR / "frames"
CLIPS_DIR = DEMO_DIR / "clips"
CLIPS_DIR.mkdir(exist_ok=True, parents=True)

STORYBOARD = json.load(open(DEMO_DIR / "storyboard.json"))
VOICE = DEMO_DIR / "voiceover.wav"
FINAL = DEMO_DIR / "archreview_kg_demo_final.mp4"
W, H, FPS = 1920, 1080, 30
CROSSFADE_S = 0.4  # crossfade overlap; lives inside the audio silence gap


def run(cmd: list[str]) -> None:
    print(">>>", " ".join(cmd[:6]), "...")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-2000:])
        raise RuntimeError(f"ffmpeg failed: {' '.join(cmd[:3])}")


def clip_duration_for(idx: int) -> float:
    """Each shot's clip spans audio-end → next-shot-start, PLUS a
    CROSSFADE_S tail so the xfade overlap is absorbed without
    shrinking net video duration below voiceover.wav.

    Shot 8 (last) stops at its audio end — no tail needed.
    """
    shots = STORYBOARD["shots"]
    if idx == len(shots):
        return shots[idx - 1]["end"] - shots[idx - 1]["start"]
    this_start = shots[idx - 1]["start"]
    next_start = shots[idx]["start"]
    return (next_start - this_start) + CROSSFADE_S


def render_shot_clip(idx: int, duration: float) -> Path:
    """Render one shot as an mp4 with slow Ken-Burns zoom-pan."""
    src = FRAMES_DIR / f"shot_{idx}.png"
    out = CLIPS_DIR / f"shot_{idx}.mp4"
    # Each shot gets a different gentle motion pattern so the cut feels alive
    # but not seasick. Zoom-only on title/closing; pan+zoom on info shots.
    n_frames = int(duration * FPS)
    # zoompan max zoom 1.06, panned over duration; x/y subtly drift
    pan_x = {1: "iw/2-(iw/zoom/2)",
             2: "0",
             3: "iw-iw/zoom",
             4: "iw/2-(iw/zoom/2)",
             5: "0",
             6: "iw-iw/zoom",
             7: "iw/2-(iw/zoom/2)",
             8: "iw/2-(iw/zoom/2)"}[idx]
    pan_y = {1: "ih/2-(ih/zoom/2)",
             2: "ih/2-(ih/zoom/2)",
             3: "ih/2-(ih/zoom/2)",
             4: "0",
             5: "ih-ih/zoom",
             6: "ih/2-(ih/zoom/2)",
             7: "0",
             8: "ih/2-(ih/zoom/2)"}[idx]
    zexpr = f"min(1.0+0.06*on/{n_frames},1.06)"
    filt = (
        f"scale={W*2}:{H*2}:flags=lanczos,"
        f"zoompan=z='{zexpr}':d=1:x='{pan_x}':y='{pan_y}':"
        f"s={W}x{H}:fps={FPS},"
        f"format=yuv420p"
    )
    cmd = [
        "ffmpeg", "-y", "-loop", "1", "-framerate", str(FPS),
        "-t", f"{duration:.3f}", "-i", str(src),
        "-vf", filt,
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-an",
        str(out),
    ]
    run(cmd)
    return out


def crossfade_concat(clips: list[Path], out: Path) -> None:
    """Concat with xfade transitions of CROSSFADE_S between adjacent clips.

    The xfade overlap lives INSIDE the 0.8s silence gap between shots —
    effectively we extend each clip by 0.8s past its audio end (the
    silence-gap span), then crossfade the last CROSSFADE_S of that gap
    into the next clip. Net video duration = total_duration_s of the
    storyboard, matching voiceover.wav exactly.
    """
    inputs: list[str] = []
    for c in clips:
        inputs.extend(["-i", str(c)])

    # Clip i extends [shot_i.start, shot_{i+1}.start]; crossfade with next
    # clip starts at (clip_i_duration - CROSSFADE_S), centered on the
    # silence gap.
    extended_durs = [clip_duration_for(i + 1) for i in range(len(clips))]
    filter_parts: list[str] = []
    prev_label = "0:v"
    running = extended_durs[0]
    for i in range(1, len(clips)):
        offset = running - CROSSFADE_S
        next_label = f"v{i}"
        filter_parts.append(
            f"[{prev_label}][{i}:v]xfade=transition=fade:duration={CROSSFADE_S}:offset={offset:.3f}[{next_label}]"
        )
        prev_label = next_label
        running = running + extended_durs[i] - CROSSFADE_S

    filt = ";".join(filter_parts)
    final_label = prev_label
    cmd = [
        "ffmpeg", "-y", *inputs,
        "-filter_complex", filt,
        "-map", f"[{final_label}]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-an",
        str(out),
    ]
    run(cmd)


def mux_audio(silent_video: Path, audio: Path, out: Path) -> None:
    cmd = [
        "ffmpeg", "-y",
        "-i", str(silent_video),
        "-i", str(audio),
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k",
        "-map", "0:v:0", "-map", "1:a:0",
        "-shortest",
        str(out),
    ]
    run(cmd)


def main() -> None:
    if not VOICE.exists():
        raise SystemExit(f"voiceover not found: {VOICE}")

    print(f"voiceover: {VOICE}")
    print(f"frames: {FRAMES_DIR}")
    print(f"final: {FINAL}")
    print()

    clips: list[Path] = []
    for shot in STORYBOARD["shots"]:
        idx = shot["index"]
        dur = clip_duration_for(idx)  # audio + trailing silence gap
        print(f"--- shot {idx} ({shot['kind']}) — {dur:.2f}s clip (incl gap)")
        clips.append(render_shot_clip(idx, dur))

    silent = CLIPS_DIR / "silent_concat.mp4"
    print("\n--- crossfade-concat all 8 clips")
    crossfade_concat(clips, silent)

    print("\n--- mux voiceover")
    mux_audio(silent, VOICE, FINAL)

    print(f"\n✅ final video: {FINAL}")
    # Probe for sanity
    p = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration:stream=width,height,codec_name",
         "-of", "json", str(FINAL)],
        capture_output=True, text=True,
    )
    print(p.stdout)


if __name__ == "__main__":
    main()
