#!/usr/bin/env python3
"""Convert a gameplay clip (animated WebP / AVI / MP4) into a small,
mobile-viewable file for sending to the user.

Default output: MP4 (H.264, yuv420p, +faststart) scaled to <=720p, CRF-tuned
so a ~20s clip lands well under 10MB. --gif emits a palette-optimized GIF
(the Claude-supported animated-image fallback when MP4 preview is unavailable).

Usage:
    python3 convert.py <input.(webp|avi|mp4)> <output.mp4> [options]

Options:
    --gif          Emit a palette-optimized GIF instead of MP4.
    --maxsec N     Trim to the first N seconds.
    --height H     Scale to at most H pixels tall (default 720; GIF default 480).
    --crf N        Override x264 CRF (default 30). Lower = bigger/higher quality.
    --fps N        Override output framerate (GIF default 15; MP4 keeps source).

ffmpeg cannot demux animated WebP, so WebP frames are extracted with PIL first
and re-encoded from a PNG sequence.

Run standalone; no LLM/ffmpeg reasoning required.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

SIZE_WARN_BYTES = 10 * 1024 * 1024
DEFAULT_MP4_HEIGHT = 720
DEFAULT_GIF_HEIGHT = 480
DEFAULT_CRF = 30
DEFAULT_GIF_FPS = 15
FALLBACK_FPS = 30.0


def die(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def probe_webp_frames(path: Path) -> tuple[int, float]:
    """Return (frame_count, fps) for an animated WebP via PIL."""
    from PIL import Image

    with Image.open(path) as im:
        n = getattr(im, "n_frames", 1)
        durations_ms: list[int] = []
        for i in range(n):
            im.seek(i)
            d = im.info.get("duration") or 0
            durations_ms.append(int(d))
    total_ms = sum(durations_ms)
    fps = (n / (total_ms / 1000.0)) if total_ms > 0 else FALLBACK_FPS
    return n, fps


def extract_webp_frames(path: Path, out_dir: Path, max_frames: int | None) -> tuple[int, float]:
    """Dump WebP frames as zero-padded PNGs; return (written, fps)."""
    from PIL import Image

    n, fps = probe_webp_frames(path)
    limit = min(n, max_frames) if max_frames else n
    written = 0
    with Image.open(path) as im:
        for i in range(limit):
            im.seek(i)
            frame = im.convert("RGB")
            frame.save(out_dir / f"frame_{i:05d}.png", compress_level=1)
            written += 1
    if written == 0:
        die("no frames extracted from WebP")
    return written, fps


def encode_mp4(input_args: list[str], out: Path, height: int, crf: int, maxsec: float | None) -> None:
    scale = f"scale=-2:'min({height},ih)':flags=lanczos"
    cmd = ["ffmpeg", "-y", *input_args]
    if maxsec:
        cmd += ["-t", str(maxsec)]
    cmd += [
        "-vf", f"{scale},format=yuv420p",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf),
        "-movflags", "+faststart", "-an", str(out),
    ]
    res = run(cmd)
    if res.returncode != 0 or not out.exists():
        die(f"ffmpeg mp4 encode failed:\n{res.stderr[-1500:]}")


def encode_gif(input_args: list[str], out: Path, height: int, fps: int, maxsec: float | None) -> None:
    vf = f"fps={fps},scale=-2:'min({height},ih)':flags=lanczos"
    palette = (
        f"{vf},split[s0][s1];[s0]palettegen=stats_mode=diff[p];"
        f"[s1][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle"
    )
    cmd = ["ffmpeg", "-y", *input_args]
    if maxsec:
        cmd += ["-t", str(maxsec)]
    cmd += ["-vf", palette, "-loop", "0", str(out)]
    res = run(cmd)
    if res.returncode != 0 or not out.exists():
        die(f"ffmpeg gif encode failed:\n{res.stderr[-1500:]}")


def validate_mp4(out: Path) -> str:
    res = run([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=codec_name,width,height",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=0", str(out),
    ])
    if res.returncode != 0:
        die(f"ffprobe could not read output:\n{res.stderr}")
    if "codec_name=h264" not in res.stdout:
        die(f"output is not H.264:\n{res.stdout}")
    return res.stdout.strip()


def validate_gif(out: Path) -> str:
    from PIL import Image

    with Image.open(out) as im:
        if im.format != "GIF":
            die(f"output is not a GIF (got {im.format})")
        return f"format=GIF frames={getattr(im, 'n_frames', 1)} size={im.size[0]}x{im.size[1]}"


def build_input_args(src: Path, tmp: Path, maxsec: float | None) -> tuple[list[str], float | None]:
    """Return (ffmpeg input args, effective maxsec for ffmpeg -t).

    For WebP we pre-extract frames and feed a PNG sequence, so trimming happens
    during extraction and ffmpeg needs no -t. A GIF request still keeps the
    source fps here; encode_gif resamples via its fps= filter.
    """
    if src.suffix.lower() == ".webp":
        frames_dir = tmp / "frames"
        frames_dir.mkdir()
        _, src_fps = probe_webp_frames(src)
        max_frames = int(maxsec * src_fps) if maxsec else None
        extract_webp_frames(src, frames_dir, max_frames)
        return ["-framerate", f"{src_fps:g}", "-i", str(frames_dir / "frame_%05d.png")], None
    return ["-i", str(src)], maxsec


def main() -> None:
    ap = argparse.ArgumentParser(description="Convert a clip to a small mobile-viewable file.")
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--gif", action="store_true")
    ap.add_argument("--maxsec", type=float, default=None)
    ap.add_argument("--height", type=int, default=None)
    ap.add_argument("--crf", type=int, default=DEFAULT_CRF)
    ap.add_argument("--fps", type=int, default=DEFAULT_GIF_FPS)
    args = ap.parse_args()

    src = Path(args.input).expanduser()
    out = Path(args.output).expanduser()
    if not src.exists():
        die(f"input not found: {src}")
    if src.suffix.lower() not in {".webp", ".avi", ".mp4"}:
        die(f"unsupported input type: {src.suffix} (want .webp/.avi/.mp4)")
    out.parent.mkdir(parents=True, exist_ok=True)

    height = args.height or (DEFAULT_GIF_HEIGHT if args.gif else DEFAULT_MP4_HEIGHT)

    with tempfile.TemporaryDirectory() as tmpname:
        tmp = Path(tmpname)
        input_args, ff_maxsec = build_input_args(src, tmp, args.maxsec)
        if args.gif:
            encode_gif(input_args, out, height, args.fps, ff_maxsec)
            detail = validate_gif(out)
        else:
            encode_mp4(input_args, out, height, args.crf, ff_maxsec)
            detail = validate_mp4(out)

    size = out.stat().st_size
    mb = size / (1024 * 1024)
    verdict = "PASS" if size < SIZE_WARN_BYTES else "PASS (WARN: >10MB, consider --maxsec/--height/--crf)"
    print(f"output: {out}")
    print(f"size:   {mb:.2f} MB ({size} bytes)")
    print(f"stream: {detail}")
    print(verdict)


if __name__ == "__main__":
    main()
