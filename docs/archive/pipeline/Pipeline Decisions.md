# Pipeline Decisions

Human-in-the-loop branching for pipeline runs. Lets the orchestrator pause at declared decision points, present N options (N ≤ 4), and resume on user pick. Two delivery channels: synchronous terminal prompt (`AskUserQuestion`) or asynchronous Slack Socket Mode (outbound-only WebSocket; no inbound port required).

## When the stage runs

A decision-elicitation stage is injected by the orchestrator only when:

1. The brief or canonical plan declares a `decision_points:` block, **OR**
2. (Phase 2+) A role mid-run self-flags ambiguity and asks the orchestrator to insert a decision point.

POC scope = declarative only. Self-flag = follow-up phase.

Default channel is `sync`. Use `async` when the user is off-terminal (Slack notification on phone/desktop), when the decision involves stakeholders beyond the runner, or when the pipeline runs headless (e.g. cron via [[Pipeline Skills|schedule]]). Async delivery spawns one Slack listener per run on demand — see [[Pipeline Slack Setup]].

## Declaration

In `brief.md` or the canonical plan:

```yaml
decision_points:
  - id: d1
    after: ui-ux-designer        # stage that completes before decision injects
    topic: Onboarding screen direction
    options_source: ui-ux-designer
    delivery: sync               # or async
    timeout_days: 7              # async only
```

The orchestrator records this in `pipeline.md` `decision_points:` map and inserts the decision-elicitation stage after `after:` completes.

## Stage flow

1. **Options emission** — orchestrator re-spawns `options_source` role with a `decision_emission: d<N>` flag in the spawn template. The role emits `options-r<N>.md` (N ≤ 4 panels, each with title + tradeoff line + ≤5-line description) **instead of** its normal pinned output.
2. **Delivery** — orchestrator invokes the [[Pipeline Skills|decision-elicitation]] skill in either `sync` or `async` mode.
3. **Pick capture** — `decision-r<N>.md` is written with the chosen option + verdict (`chosen | timeout | cancelled`).
4. **Re-spawn** — `options_source` is re-spawned with `decision-r<N>.md` in its Read set; it emits its final pinned artifact (e.g. `frontend-handoff.md`).
5. Pipeline continues per the dependency graph.

## Sync delivery (default)

Blocking terminal prompt via `AskUserQuestion`:

- Question = decision `topic`
- Header = `Decision d<N>`
- Up to 4 options labeled `Option A/B/C/D: <title>`, description = tradeoff one-liner
- Preview = compact monospace summary

Fast path. No GH dependency. Best when runner is at the terminal.

## Async delivery (Slack Socket Mode)

Outbound-only architecture. The orchestrator never calls Slack directly. When a run enters async-mode decision-elicitation, the orchestrator spawns a per-run listener process (`.claude/pipeline/slack_listener.py <project> <run-id>`) detached via `subprocess.Popen(..., start_new_session=True)`. The listener opens a Slack Socket Mode WebSocket, watches its run dir via inotify, and bridges in both directions:

- New `awaiting-decision-r<N>.md` written → listener posts a threaded message with N buttons.
- Button click → listener writes `decision-r<N>.md` into the run dir + deletes the awaiting file.

The pipeline's only Slack interaction is filesystem-level: write awaiting file, poll for decision file. No tokens in pipeline code.

### Preconditions

- `~/.claude/pipeline/slack.env.local` populated with `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`, `SLACK_CHANNEL` (channel ID, not name).
- `~/.claude/pipeline/slack_listener.py` present + executable; `uv` resolves on PATH.
- Bot user invited to the channel (`/invite @your-bot` once, ever).
- Optional: `<project>/.pipeline/pipeline.toml` `[slack].channel` overrides the env default for this project only.

Any precondition fails → fall back to `sync` with a warning logged to `pipeline.md`.

### Per-project config (`<project>/.pipeline/pipeline.toml`)

```toml
[slack]
channel = "C0123ABC456"   # required; Slack channel ID (right-click channel → View details → Channel ID)
project_name = "myproject"  # optional; shown in parent thread message
```

If `pipeline.toml` is missing the `[slack]` block, the orchestrator falls back to `sync` and offers via `AskUserQuestion` to persist a channel for next time.

### Flow

1. Verify preconditions; degrade to `sync` on failure.
2. Ensure the per-run listener is alive (idempotent): read `<run-dir>/slack-listener.pid` + `os.kill(pid, 0)`. If dead/missing, spawn detached via `subprocess.Popen(..., start_new_session=True)`; redirect stdout/stderr to `<run-dir>/slack-listener.log`.
3. Write `<run-dir>/awaiting-decision-r<N>.md` (single trigger for the listener — no API call from orchestrator).
4. Update SQLite Ledger: `status=paused_on_decision`, decision row active.
5. `ScheduleWakeup(delaySeconds=600, prompt="<<resume-pipeline-<artifact-id>>>", reason="polling decision d<N> @10min")`.
6. Halt. Control returns to the user.

Listener behavior (informative):

- First decision for a run → posts a parent message (`🟡 Pipeline started <run-id>`) and captures `thread_ts`. Subsequent decisions for the same run reply in that thread. State persisted in `<run-dir>/slack-state.json` (listener-owned; gitignored).
- Each decision post = section blocks per option + an actions block with up to 4 buttons (`action_id=decision_pick_<A|B|C|D>`, `value=<run_id>|<decision_id>|<choice>`).
- On click → optional allowlist check (`SLACK_ALLOWED_USERS`), write `decision-r<N>.md` with `verdict: chosen`, edit the original message to a locked confirmation, post a thread reply (`Recorded Option B for run-id / d1. Pipeline resuming.`), delete the awaiting file.
- Self-exits 30 seconds after the run's awaiting set has been empty. Orchestrator re-spawns idempotently on the next decision in the same run.
- WebSocket reconnects automatically within a single listener lifetime; missed clicks reappear on reconnect.

### Poll loop

Each wake:

1. Read `<run-dir>/awaiting-decision-r<N>.md` to recover state.
2. Check `<run-dir>/decision-r<N>.md` existence:
   - Exists → parse `verdict` + `chosen_option`, mark decision resolved in SQLite Ledger, resume pipeline (re-spawn `options_source` with decision file in Read set).
3. Else check `now >= timeout_at`:
   - True → write `decision-r<N>.md` with `verdict: timeout`, halt + surface.
4. Else check listener health: read `<run-dir>/slack-listener.pid`, then `os.kill(pid, 0)`.
   - File missing or process dead → respawn (idempotent). After 2 consecutive wakes where respawn fails, offer sync fallback via `AskUserQuestion`.
5. Else → update `last_polled_at` + `next_wake_at`; `ScheduleWakeup` 600s.

### Resume sentinel

`<<resume-pipeline-<artifact-id>>>` is recognized at orchestrator startup. The orchestrator skips intake, locates `awaiting-decision-*.md` in the matching run dir, and routes directly to the poll procedure.

Fallback: if `ScheduleWakeup` is unavailable (no `/loop` context), the user can re-invoke manually with `resume <artifact-id>` once they've clicked the Slack button.

## Reply syntax

Click a button. No text parsing.

(Future phase: free-form Slack reply parsing via LLM, with confirmation message before acting.)

## Guardrails

- N ≤ 4 (matches `AskUserQuestion` limit + keeps the Slack actions block under the 5-button visual cap).
- One paused decision per run. Multi-decision runs sequence them; each posts in the same run thread.
- Default timeout 7 days; override via `timeout_days` per point.
- Confirmation message posted **before** the pipeline reads the decision file (listener writes the file last, after the Slack confirmation succeeds).
- Optional `SLACK_ALLOWED_USERS` allowlist (comma-separated user IDs in `slack.env`) restricts who can click.
- [[Pipeline Gates|pipeline-friction-audit]] end-of-run audit scans `<run-dir>/awaiting-decision-*.md`. Any remaining = anomaly logged; orphan cleanup deferred to next orchestrator startup scan.

## Failure modes

| Case | Behavior |
|---|---|
| `pipeline.toml` missing `[slack].channel` | `AskUserQuestion` offers to persist channel, otherwise sync fallback |
| Listener spawn fails (Popen returns nonzero or PID file never written) | Tail `<run-dir>/slack-listener.log` for traceback. Fall back to sync |
| `slack.env.local` tokens missing/invalid | Listener exits with `SLACK_BOT_TOKEN and SLACK_APP_TOKEN required` in log. Fall back to sync |
| Bot not in channel | Listener logs `not_in_channel`; orchestrator detects inactivity beyond 2 wake cycles and falls back to sync |
| User dismisses Slack message without clicking | Awaits until `timeout_at`, then `verdict: timeout`, halt + surface |
| Session dies mid-wait | Resume via sentinel on next orchestrator invocation OR manual `resume <id>` |
| `ScheduleWakeup` no-op (no `/loop`) | User manually re-invokes; orchestrator polls on demand |
| Slack workspace outage | Listener reconnects automatically. Idempotent: re-click overwrites the same `decision-r<N>.md` |

## Related

- [[Pipeline Overview]]
- [[Pipeline Stages]]
- [[Pipeline Artifacts]] — `options-r<N>.md`, `decision-r<N>.md`, `awaiting-decision-r<N>.md` schemas
- [[Pipeline Skills|decision-elicitation skill]]
- [[Pipeline Decisions Rollout]] — phased delivery plan
