# Gauntlet capture harness spec

Generated into `src/debug/gauntlet/` (gitignored). Regenerate per
worktree from this spec; adapt node/service names to the demo. All of
it obeys the project CLAUDE.md playground rules: real services, real
session, real input path.

## Files

```
src/debug/gauntlet/
  launcher.sh          # spawns host + N clients, per-bucket scenario
  capture_host.tscn    # demo scene + recorder + bot autoloads (host)
  capture_client.tscn  # same, client role
  bot_pilot.gd         # goal-script bot driving real input actions
  recorder.gd          # viewport -> ffmpeg pipe -> webp/webm
  scenarios/<bucket>.gd# per-bucket bot goal scripts
  sidecar.gd           # writes per-clip JSON metadata
```

## launcher.sh

- `GODOT` binary from ~/.claude/rules/godot.md (GODOT_ROOT, Godot 4.6 path).
- Args: demo scene, bucket, seed, session count, out dir.
- Host: `"$GODOT" --headless --path src res://debug/gauntlet/capture_host.tscn -- --bucket=X --seed=N --out=DIR`
  (custom args after `--`, read via `OS.get_cmdline_user_args()`).
- Clients (x2): same with capture_client.tscn + `--join=127.0.0.1`.
- Headless has no viewport to grab: run recording instances NON-headless
  under `xvfb-run -s "-screen 0 1280x720x24"` per instance, or use a
  Movie Maker mode variant; verify actual fps either way.
- netem variant: wrap client launch in `sudo tc qdisc add dev lo root
  netem delay 60ms loss 1%` / teardown after (or use a netns per client
  to avoid polluting lo).
- Pairing: host and one client both record the same wall segment;
  recorder stamps start/end tick in the sidecar; a post step trims both
  to the shared tick window and composites side by side (ffmpeg hstack).

## bot_pilot.gd

- Runs ONLY on client instances (and optionally host-local player).
- Reads scenario script: sequence of goals (move-to, interact, chase,
  idle, disconnect/reconnect at t) with per-goal timeouts.
- Emits input by calling the demo's real input-submission path (the
  same funcs/actions a human-driven client uses; Input.parse_input_event
  with action events if the demo reads actions). NEVER sets transforms,
  NEVER touches server state, NEVER calls host-only APIs.
- Deterministic: seeded RNG passed from launcher; all timing in ticks,
  not wall clock.
- Human-plausibility: rate-limit turns (max deg/s), add seeded jitter to
  target points, 100-250 ms reaction delay after stimulus events. The
  believability axes judge this footage; robot-perfect input fails B2.

## recorder.gd

- Grabs `get_viewport().get_texture().get_image()` on a fixed cadence
  (every Nth frame to hit >= 24 fps at stable cost), pipes raw frames to
  ffmpeg via `OS.execute_with_pipe` (or writes PNG sequence then
  encodes; slower but simpler, acceptable for v1).
- Encode: WebP `ffmpeg -framerate F -i - -c:v libwebp -lossless 0
  -q:v 90 -loop 0 out.webp`; AV clips capture audio via
  `AudioEffectRecord` on the master bus, mux WebM (VP9+Opus).
- No overlays on frames. Sidecar JSON via sidecar.gd: build hash
  (`git rev-parse --short HEAD` passed in by launcher), demo, bucket,
  session id, seed, view, start/end tick, fps.
- Clip clock: 20 s +- 0.5 s; long-session mode records continuously and
  is sliced by the launcher post step.

## Control clip

Any locally runnable, known-good commercial game (or a polished Godot
showcase title) captured through the SAME xvfb+ffmpeg path and encode
settings. Store under `captures/_control/` and reuse across runs; only
recapture when the pipeline changes.

## Validation step (launcher post)

- `webpinfo` every WebP: frame count / duration >= 24 fps, else FAIL.
- `ffprobe` AV clips: audio stream present, else FAIL.
- Sidecars: parse + required keys, else FAIL.
- Manifest: bucket x count table; missing bucket = FAIL (no padding).
