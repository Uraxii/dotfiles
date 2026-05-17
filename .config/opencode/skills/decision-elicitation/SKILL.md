---
name: decision-elicitation
description: Pipeline decision-point stage. Elicits human pick between N options (N ≤ 4). Sync delivery via AskUserQuestion or async via Slack (requires active session binding). Records pick in decision-r<N>.md. Use when brief/plan declares decision_points or a role flags ambiguity.
source: pipeline-native
output-style: caveman:ultra
---

# decision-elicitation

Pipeline stage. Elicits human decision between option set. Sync or async. Orchestrator-owned (no subagent). Pipeline-internal.

## Invocation

Claude: `Skill(skill: "decision-elicitation", args: "run-dir=<path>, decision-id=d<N>, mode=<sync|async>")`

`mode` default = `sync`. `async` requires an active session binding (`slack-bind` first), `<project>/.pipeline/pipeline.toml` w/ `[slack].channel`, and Slack creds at `~/.config/opencode/pipeline/slack.env.local`; else skill falls back to `sync` and warns.

## Inputs (caller writes before invoking)

- `<run-dir>/options-r<N>.md` — required canonical option set
- `<run-dir>/options-r<N>.html` — optional visual companion (not required for POC)

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

## Delivery: async (Slack)

Outbound-only architecture. No inbound port. No public URL. Decision posted
via `pipeline_notify.py --kind decision` into the active session-bound thread.
Button click is handled by the host-bound router daemon (`comms/router.py`),
which writes `decision-r<N>.md` in the run dir. Pipeline polls file existence
on wake.

### Preconditions

- **Active session binding required.** Run `slack-bind` before entering async mode.
  No binding → degrade to sync + log `slack.warning` to `pipeline.md`. Do NOT
  silently hang or spawn a daemon.
- `~/.config/opencode/pipeline/slack.env.local` populated (`SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`, `SLACK_CHANNEL`).
- `command -v uv` resolves (notify uses PEP 723 inline deps via `uv run`).

Optional: `<project>/.pipeline/pipeline.toml` `[slack].channel` overrides the env-level `SLACK_CHANNEL`.

Any precondition fails → emit warning to `pipeline.md`, fall back to sync.

### pipeline.toml schema (optional, per-project override)

```toml
[slack]
channel = "C0123ABC456"   # Slack channel ID. Overrides SLACK_CHANNEL env var.
project_name = "myproject"  # Optional. Shown in parent thread message.
```

Channel resolution order:
1. `<project>/.pipeline/pipeline.toml` `[slack].channel` (per-project override).
2. `SLACK_CHANNEL` env var from `~/.config/opencode/pipeline/slack.env.local` (global default).
3. Neither set → fall back to sync delivery.

### Flow

1. Verify preconditions (active binding + tokens + channel). Degrade to sync on failure (log to pipeline.md).
2. Call `pipeline_notify.py --kind decision --run-dir <path> --run <run-id> --did d<N>`.
   - notify reads `options-r<N>.md` + `awaiting-decision-r<N>.md` from disk for prompt/options.
   - notify posts `chat_postMessage` with button blocks into bound thread.
   - Button `value` format: `<phash8>|<run-id>|d<N>|<choice>` where `phash8 = sha1(project_path)[:8]`.
   - notify writes run-index entry to `~/.config/opencode/comms-router/run-index/<run-id>.json`.
   - Orchestrator does NOT call Slack API directly.
3. Write `<run-dir>/awaiting-decision-r<N>.md` (schema below).
4. Update `pipeline.md` `paused_on_decision:` block. Set top-level `status: paused_on_decision`.
5. `ScheduleWakeup(delaySeconds=600, prompt="<<resume-pipeline-<artifact-id>>>", reason="polling decision d<N> @10min")`.
6. Halt. Control returns to user.

Router behavior (informative; not orchestrator's concern):
- Host-bound daemon (`comms/router.py`) handles `decision_pick_<A..D>` action events.
- On button click → validates `phash8` matches run-index entry; writes `decision-r<N>.md` +
  deletes `awaiting-decision-r<N>.md`; confirms in thread via `chat_update` + reply.
- Single router process serves all sessions; idle-exits at 30 min empty binding set.
- Router enforces strict `<adj>-<mid>-<noun>-<hex6>` artifact-slug format for
  `<run-id>` in the button payload (regex). Mismatched ids → ephemeral toast
  naming the rejection reason; no decision file written. Use the
  `artifact-slug` tool to generate run-ids.

## Resume (async only)

Triggers:
- ScheduleWakeup fires w/ resume sentinel
- User manually re-invokes orchestrator w/ "resume <artifact-id>"
- Orchestrator startup detects `awaiting-decision-*.md` in active runs (opportunistic)

Poll procedure (every wake):
1. Check `<run-dir>/decision-r<N>.md` existence.
   - Exists → parse `verdict` + `chosen_option` → remove `paused_on_decision` block from `pipeline.md` → resume pipeline.
2. Else check `<run-dir>/awaiting-decision-r<N>.md` `timeout_at`.
   - `now >= timeout_at` → write `decision-r<N>.md` w/ `verdict: timeout` → halt + surface to user.
3. Else check active session binding: `session_bind.py status (reads ~/.config/opencode/sessions/<sid>/slack.json)`.
   - Not bound → warn in pipeline.md + offer sync fallback via `AskUserQuestion`.
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
- `delivery: async` requires active session binding at entry. No binding → degrade to sync with `slack.warning` logged to `pipeline.md`. Do NOT block silently.
- friction-reviewer end-of-run audit: scan `<run-dir>/awaiting-decision-*.md`. Any remaining = anomaly → log + leave for next orchestrator startup scan.
- Async pre-check failures degrade to sync (don't hard-fail).
- Router is host-bound; no per-run daemon spawned. Concurrent runs share one router.
- Confirmation message posted in thread BEFORE pipeline reads decision file.

## Failure modes

| Case | Policy |
|---|---|
| `pipeline.toml` missing `[slack].channel` | Fall back to sync; log warning. |
| No active session binding at async entry | Degrade to sync `AskUserQuestion`; log `slack.warning` to `pipeline.md`. |
| `slack.env.local` tokens missing/invalid | Degrade to sync; log warning. |
| Bot not in channel | Notify exits non-zero. Fall back to sync. |
| User dismisses Slack msg without clicking | Awaits until `timeout_at`. Then `verdict: timeout`, halt + surface. |
| Decision file written but missing fields | Resume reads `chosen_option=null` → treat as cancelled. Surface to user. |
| Pipeline session dies during wait | Resume on next orchestrator invocation via startup `awaiting-*.md` scan. |
| ScheduleWakeup unavailable (not in /loop context) | User manually re-invokes "resume <artifact-id>". |
| Slack workspace outage | Router WebSocket reconnects automatically (slack_bolt handles). |

## Notes

- `<<resume-pipeline-<artifact-id>>>` sentinel: orchestrator startup parses incoming prompt; if matches sentinel pattern, route directly to resume logic, skip intake.
- POC: only fixed-button clicks parsed. Free-form Slack reply parsing = future phase.
- Two-mode design (sync default, async opt-in) keeps fast-path latency unchanged for terminal-attached runs.
- See `docs/pipeline-slack.md` for setup instructions.
