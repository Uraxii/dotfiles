---
name: decision-elicitation
description: Pipeline decision-point stage. Elicits human pick between N options (N ≤ 4). Sync delivery via AskUserQuestion or async via Slack Socket Mode listener. Records pick in decision-r<N>.md. Use when brief/plan declares decision_points or a role flags ambiguity.
source: pipeline-native
output-style: caveman:ultra
---

# decision-elicitation

Pipeline stage. Elicits human decision between option set. Sync or async. Orchestrator-owned (no subagent). Pipeline-internal.

## Invocation

Claude: `Skill(skill: "decision-elicitation", args: "run-dir=<path>, decision-id=d<N>, mode=<sync|async>")`

`mode` default = `sync`. `async` requires `<project>/.pipeline/pipeline.toml` w/ `[slack].channel`, Slack creds at `~/.claude/pipeline/slack.env.local`, and the listener script at `~/.claude/pipeline/slack_listener.py`; else skill falls back to `sync` and warns. The listener is spawned per-run by the orchestrator on demand — no daemon to install.

## Inputs (caller writes before invoking)

- `<run-dir>/options-r<N>.md` — required canonical option set
- `<run-dir>/options-r<N>.html` — optional visual companion (Phase 1+; not required for POC)

## options-r<N>.md schema

```yaml
---
decision_id: d<N>
topic: <one-line topic>
requesting_role: <role-name>
count: <2|3|4>
delivery_default: sync|async
timeout_days: 7  # async only; default 7
---

## Option A: <title>
- **Tradeoff:** <one-line>
- **Description:** <prose, ≤5 lines>
- **Artifacts:** [<optional paths>]

## Option B: <title>
...
```

## Trigger

Brief or plan declares `decision_points:`:

```yaml
decision_points:
  - id: d1
    after: <role>              # stage after which to inject
    topic: <one-line>
    options_source: <role>     # role that emits options-rN.md
    delivery: sync|async       # default sync
    timeout_days: 7            # async only
```

Orchestrator inserts decision-elicitation stage after `<role>` completes. `<options_source>` role spawns w/ `decision_emission: d<N>` flag in spawn template; it emits `options-r<N>.md` instead of (or alongside) its normal output. Post-decision, role re-spawns w/ `decision-r<N>.md` in Read set → emits pinned final output.

## Delivery: sync

1. Read `options-r<N>.md`.
2. Build `AskUserQuestion` call:
   - Question = `topic` from frontmatter
   - Header = `Decision d<N>`
   - Options = N entries, label = "Option A/B/C/D: <title>", description = `Tradeoff` one-liner
   - Preview = compact summary (description prose, ≤10 lines monospace)
3. User picks → write `decision-r<N>.md` (see schema below).
4. Return to dependency graph.

## Delivery: async (Slack Socket Mode)

Outbound-only architecture. No inbound port. No public URL. Per-run listener
process spawned by the orchestrator when async mode is entered. The listener
opens a Slack Socket Mode WebSocket, watches its run dir via inotify, posts
each new `awaiting-decision-r<N>.md` to the project's channel as a threaded
message with buttons. Each button's `value` carries
`<run-id>|<decision-id>|<choice>` — listener routes click →
`<run-dir>/decision-r<N>.md`, isolating concurrent runs by `artifact-slug`.
Pipeline polls file existence on wake.

### Preconditions

- `~/.claude/pipeline/slack.env.local` populated (`SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`, `SLACK_CHANNEL`).
- `~/.claude/pipeline/slack_listener.py` present + executable.
- `command -v uv` resolves (listener uses PEP 723 inline deps via `uv run`).

Optional: `<project>/.pipeline/pipeline.toml` `[slack].channel` overrides the env-level `SLACK_CHANNEL` for one project; `[slack].project_name` overrides the dir-basename default in the parent thread message.

Any precondition fails → emit warning to `pipeline.md`, fall back to sync.

### pipeline.toml schema (optional, per-project override)

```toml
[slack]
channel = "C0123ABC456"   # Slack channel ID. Overrides SLACK_CHANNEL env var.
project_name = "myproject"  # Optional. Shown in parent thread message. Defaults to dir basename.
```

Channel resolution order:
1. `<project>/.pipeline/pipeline.toml` `[slack].channel` (per-project override).
2. `SLACK_CHANNEL` env var from `~/.claude/pipeline/slack.env.local` (global default).
3. Neither set → `AskUserQuestion` (sync) asks user to pick: paste channel + persist to env-level default, OR fall back to sync delivery for this run.

### Session binding (r1)

When `CLAUDE_CODE_SESSION_ID` is set and an active session binding exists
(`~/.claude/sessions/<sid>/slack.json` with `active=true`), the listener is
spawned with `--session-thread CHANNEL:TS`. All decision posts land in the
bound session thread rather than creating a new per-run thread. Each message
is prefixed with `[<run-id>]`. Button routing is unchanged: `value` field
carries `<run-id>|<decision-id>|<choice>`.

If no binding is active, legacy per-pipeline thread applies unchanged (AC6).

If a brief declares async delivery and no session binding exists at intake,
degrade to sync `AskUserQuestion` and log the reason to `pipeline.md`
`slack.warning`. Pipeline continues; does not abort (AC10).

### Flow

1. Verify preconditions; degrade to sync on failure (log to pipeline.md).
2. Ensure listener alive (idempotent):
   - Check `<run-dir>/slack-listener.pid`. If file exists, read PID and call
     `os.kill(pid, 0)` — alive → skip spawn.
   - Else spawn via `session_slack.spawn_listener(<project>, <run-id>)` which
     adds `--session-thread CHANNEL:TS` when a binding is active. Shell-
     equivalent executed by the helper:
     ```bash
     uv run --script ~/.claude/pipeline/slack_listener.py \
         "$PROJECT" "$RUN_ID" \
         [--session-thread CHANNEL:TS]   # included when binding active
     ```
     Log path: `<run-dir>/slack-listener.log`.
3. Write `<run-dir>/awaiting-decision-r<N>.md` (schema below). Listener picks
   it up via inotify; orchestrator does NOT call Slack API directly.
4. Update `pipeline.md` `paused_on_decision:` block. Set top-level
   `status: paused_on_decision`.
5. `ScheduleWakeup(delaySeconds=600, prompt="<<resume-pipeline-<artifact-id>>>", reason="polling decision d<N> @10min")`.
6. Halt. Control returns to user.

Listener behavior (informative; not orchestrator's concern):
- Session-bound: posts `[<run-id>] :rocket: Pipeline started — brief: ...` header
  on first artifact per run. Decision posts prefixed `[<run-id>]`.
- Legacy: on `awaiting-decision-r<N>.md` create → posts thread parent for run (first
  decision only) + decision msg w/ buttons.
- On button click → writes `decision-r<N>.md` w/ `verdict: chosen`, deletes the
  awaiting file, edits Slack msg to "locked", posts confirmation in thread.
- State persisted in `<run-dir>/slack-state.json`. Per-run.
- Idle exit after `SLACK_LISTENER_IDLE_TIMEOUT` seconds (default 86400 = 24h) with
  no open decisions. Orchestrator re-spawns idempotently if a later decision lands.

## Resume (async only)

Triggers:
- ScheduleWakeup fires w/ resume sentinel
- User manually re-invokes orchestrator w/ "resume <artifact-id>"
- Orchestrator startup detects `awaiting-decision-*.md` in active runs (opportunistic)

Poll procedure (every wake):
1. Check `<run-dir>/decision-r<N>.md` existence.
   - Exists → parse `verdict` + `chosen_option` → remove `paused_on_decision` block from `pipeline.md` → resume pipeline (re-spawn options_source w/ decision file in Read set).
2. Else check `<run-dir>/awaiting-decision-r<N>.md` `timeout_at`.
   - `now >= timeout_at` → write `decision-r<N>.md` w/ `verdict: timeout` → halt + surface to user.
3. Else check listener health: read `<run-dir>/slack-listener.pid`, then
   `os.kill(pid, 0)`.
   - File missing OR process dead → respawn listener (idempotent spawn, see
     Flow step 2). If respawn fails 2 cycles in a row, warn in pipeline.md +
     offer sync fallback via `AskUserQuestion`.
4. Else → update `awaiting-decision-r<N>.md` `last_polled_at` + `next_wake_at`; `ScheduleWakeup(delaySeconds=600, ...)`.

## awaiting-decision-r<N>.md schema

```yaml
---
decision_id: d<N>
delivery_mode: async
slack_channel: <channel-id>
opened_at: <iso8601>
timeout_at: <iso8601>          # opened_at + timeout_days
poll_cadence_s: 600            # 10 minutes
last_polled_at: <iso8601|null>
next_wake_at: <iso8601>
requesting_role: <role>
options_source: <role>
topic: <one-line>
---
```

## decision-r<N>.md schema

```yaml
---
decision_id: d<N>
verdict: chosen | timeout | cancelled
chosen_option: A | B | C | D | null
delivery_mode: sync | async
decided_at: <iso8601>
decided_by_slack_user: <U0123...|null>   # async only
opened_at: <iso8601|null>                # async only
requesting_role: <role>
options_source: <role>
---

## Pick rationale
<user free-form notes from AskUserQuestion OR "(no notes; chose via Slack button)"; empty if none>

## Source options
- Path: options-r<N>.md
```

## pipeline.md schema extension

Add to frontmatter when paused:

```yaml
paused_on_decision:
  decision_id: d<N>
  stage: <requesting-role>
  delivery_mode: sync | async
  slack_channel: <channel-id|null>
  opened_at: <iso8601>
  timeout_at: <iso8601|null>
  next_wake_at: <iso8601|null>
```

Remove block when resumed. Set top-level `status: paused_on_decision` while waiting.

## Guardrails

- `N ≤ 4` (matches AskUserQuestion limit + Slack actions block 5-button soft cap).
- One paused decision per run max. Multi-decision runs sequence them.
- Timeout default 7d. Configurable per decision via `timeout_days`.
- friction-reviewer end-of-run audit: scan `<run-dir>/awaiting-decision-*.md`. Any remaining = anomaly → log + leave for next orchestrator startup scan.
- Async pre-check failures degrade to sync (don't hard-fail).
- Slack listener is per-run; spawned by orchestrator at async-mode entry, exits 30s after the run's awaiting set clears. Concurrent runs = independent listeners. Failed spawn = sync fallback; pipeline does not retry-with-Slack mid-run.
- Confirmation message posted in thread BEFORE pipeline reads decision file. Listener writes file last; pipeline-side poll cannot fire on partial state.
- `<run-dir>/slack-state.json` and `<run-dir>/slack-listener.pid` are listener-owned. Orchestrator reads PID only for liveness check; never writes either file. Both gitignored.

## Failure modes

| Case | Policy |
|---|---|
| `pipeline.toml` missing `[slack].channel` | `AskUserQuestion`: enter channel + persist, or fall back to sync. |
| Listener spawn fails (Popen returns nonzero, exits immediately) | Tail `<run-dir>/slack-listener.log` for traceback. Fall back to sync. |
| `slack.env.local` tokens missing/invalid | Listener exits with `SLACK_BOT_TOKEN and SLACK_APP_TOKEN required` in log. Fall back to sync. |
| Bot not in channel | Listener logs `not_in_channel`. Orchestrator detects via inactivity beyond 2 wake cycles + still no decision file. Fall back to sync. |
| User dismisses Slack msg without clicking | Awaits until `timeout_at`. Then `verdict: timeout`, halt + surface. |
| Decision file written but missing fields | Resume reads `chosen_option=null` → treat as cancelled. Surface to user. |
| Pipeline session dies during wait | Resume on next orchestrator invocation via startup `awaiting-*.md` scan. |
| ScheduleWakeup unavailable (not in /loop context) | User manually re-invokes "resume <artifact-id>"; orchestrator polls on demand. |
| Slack workspace outage | Listener WebSocket reconnects automatically (slack_bolt handles). Worst case: missed button click → user re-clicks → idempotent (decision-r<N>.md write is overwrite-OK on a single decision). |

## Notes

- `<<resume-pipeline-<artifact-id>>>` sentinel: orchestrator startup parses incoming prompt; if matches sentinel pattern, route directly to resume logic, skip intake.
- POC: only fixed-button clicks parsed. Free-form Slack reply parsing = future phase.
- POC: HTML companion not required. Markdown options-rN.md sufficient. HTML = Phase 1.
- Two-mode design (sync default, async opt-in) keeps fast-path latency unchanged for terminal-attached runs.
- See `docs/pipeline-slack.md` for setup instructions (Slack app creation, channel + bot invite, listener smoke test).
