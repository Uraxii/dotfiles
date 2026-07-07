---
name: clip-to-mobile
description: Convert a gameplay clip (animated WebP, AVI, or MP4) into a small, mobile-viewable video for sending to the user. Use whenever you are about to send/attach a recorded clip and the source is an animated WebP or an oversized MP4 — animated WebP and AVI do NOT render inline in the Claude Code mobile app. Produces a small H.264 MP4 (default) or a GIF fallback with one command; no LLM-driven ffmpeg session needed.
---

# clip-to-mobile

Turn a captured clip into something the user can actually watch on the Claude
Code mobile app, cheaply and repeatably. One command, no per-send ffmpeg
reasoning.

## Format recommendation (what to send)

| Format | Inline on mobile? | Use |
|--------|-------------------|-----|
| **MP4 (H.264 / yuv420p / +faststart)** | Yes — universal | **DEFAULT. Send this.** |
| **GIF (palette-optimized)** | Yes (Claude-supported image type) | **Fallback** if an MP4 preview ever fails to appear |
| Animated WebP | No | never send — the format that started this |
| AVI | No | source only (`/tmp/cap/`), never send |
| WebM / VP9 | Unreliable in chat/mobile | avoid |

**Default: small H.264 MP4** (`yuv420p` + `-movflags +faststart`, <=720p,
CRF 30). Most universally decoded video in mobile/chat contexts; faststart lets
it start playing before it fully downloads. **Fallback: GIF** — GIF is in
Claude's supported image list and auto-animates, but files are large (~9MB for
5s), so only reach for it if an MP4 won't preview.

Keep clips small: a ~20s 720p MP4 lands ~3-4MB (well under the ~10MB comfort
line). If a send feels heavy, trim with `--maxsec` or drop `--height`.

## Command

```bash
python3 ~/.claude/skills/clip-to-mobile/convert.py <input.(webp|avi|mp4)> <output.mp4>
```

That is the whole default flow: animated-WebP (or AVI/big MP4) in, small
mobile MP4 out. It prints the output path, size, stream info, and PASS/FAIL.

### Options

- `--gif` — emit a palette-optimized GIF instead (fallback format).
- `--maxsec N` — trim to the first N seconds (long clips → smaller files).
- `--height H` — max output height in px (default 720 for MP4, 480 for GIF).
- `--crf N` — x264 quality/size knob (default 30; lower = bigger + sharper).
- `--fps N` — GIF framerate (default 15; ignored for MP4, which keeps source fps).

### Examples

```bash
# Default: animated WebP → small mobile MP4 (send this to the user)
python3 ~/.claude/skills/clip-to-mobile/convert.py capture.webp clip.mp4

# Trim a long capture to 20s
python3 ~/.claude/skills/clip-to-mobile/convert.py capture.webp clip.mp4 --maxsec 20

# GIF fallback of the first 5 seconds
python3 ~/.claude/skills/clip-to-mobile/convert.py capture.webp clip.gif --gif --maxsec 5

# Big source MP4 → smaller MP4 (e.g. the 33MB problem case)
python3 ~/.claude/skills/clip-to-mobile/convert.py big.mp4 clip.mp4 --height 720
```

## How it works / notes

- **Animated WebP:** ffmpeg cannot demux animated WebP, so the script extracts
  frames with PIL (inferring fps from per-frame durations, 30fps fallback) and
  re-encodes from a PNG sequence. AVI/MP4 inputs go straight through ffmpeg.
- **Validation:** MP4 output is probed with ffprobe (must be an H.264 stream);
  GIF output is opened with PIL. Size is checked against a 10MB comfort line —
  over it still PASSes but prints a WARN suggesting `--maxsec`/`--height`/`--crf`.
- **Speed:** ~40s for a 470-frame 720p clip (frame extraction dominates); the
  encoder runs the `veryfast` x264 preset. Fully standalone — no model in the loop.
- **Dependencies:** ffmpeg + ffprobe + Pillow (all already installed).
