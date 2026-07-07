---
name: demo-video-capture
description: Capture the full benchmark clip set for a nikki-net demo build (30 stratified WebP clips, 3 full-session videos, 10 paired host/client clips, 5 AV clips with audio, 1 control clip, sidecar JSON) by launching headless instances with scripted bot pilots. Use when the user says "capture clips", "record the benchmark set", "run capture for <demo>", or before demo-video-judge when no clip set exists for the build.
---

# demo-video-capture

Produces the input for demo-video-judge. Spec of record:
`docs/eval/gameplay-video-eval.md` sections 4-6 (repo copy; main copy at
`/home/nikki/Git/nikki-net/docs/eval/gameplay-video-eval.md`).

## Output contract

`captures/<demo>/<build-hash>/` containing:
- 30x 20 s WebP, >= 5 per bucket: spawn-join, traversal, core-interaction,
  contention, edge-events, idle. Distinct sessions AND seeds.
- 3x 2-3 min full-session videos (join -> play -> win -> restart).
- 10x paired host/client clips: same 20 s, same session, time-aligned by
  shared tick, composited side by side.
- 5x 20 s WebM (VP9+Opus) WITH audio: menu interaction, core action,
  score/win event.
- 1x control clip: known-good commercial game through this same pipeline.
- One sidecar JSON per clip: build hash, demo, bucket, session id, seed,
  view, start tick, capture fps.
- WebP >= 24 fps ACTUAL (verify with `webpinfo`: frames/duration), >= 720p,
  lossy q >= 90, no burned-in overlays.

## Precondition: assets optimized (before any capture)

3D assets MUST be optimized before a clip is captured: poly counts within
the GDD section 8b budgets, import settings applied, LODs present where
the budget assumes them, textures compressed (no raw PNG on GPU), static
geometry batched, sane draw-call/material counts. Confirm a STABLE frame
rate at capture resolution on the target machine via the profiler (not by
eye). Unoptimized assets drop frames that read as engine/netcode hitching
and poison A6 and gate 2. Unstable build = capture FAILED; say so, fix,
recapture.

## Procedure

1. Read `references/harness.md`. Generate/refresh the harness into
   `src/debug/gauntlet/` (gitignored by design; regenerate, never hand-copy
   between worktrees).
2. Harness rules (non-negotiable, from project CLAUDE.md): real services
   only. Host instance runs `Net.host()`; clients join over loopback or
   netem; actors spawn via `ActorService.spawn`; bot pilots submit through
   the real client input path. A bot that teleports actors or writes
   server state invalidates every clip it appears in.
3. Launch matrix per bucket: headless host + 2 headless clients via the
   Godot CLI binary (path in user CLAUDE.md, GODOT_ROOT). Seed logged.
4. Record via the harness recorder (viewport -> ffmpeg pipe). Encode WebP
   with `-c:v libwebp -q:v 90`+; AV clips as WebM.
5. netem variant: capture at least the edge-events bucket under
   `tc netem delay 60ms loss 1%` (or WAN) for the real-network gates.
6. Validate before handing off: every clip plays, fps actual >= 24,
   sidecars parse, bucket counts met, control clip present. Print the
   manifest table (bucket x count) and the output path.

Missing bucket coverage or missing control clip = capture FAILED; say so,
never pad with duplicate sessions.
