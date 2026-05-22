---
name: pipeline-decision-elicitation
description: Pipeline decision-point stage. Elicits human pick between N options (N ≤ 4). Sync via Hermes `clarify` tool (root only). Async via Discord text-reply pattern with `!decide <run_id>:d<N> <index>` sentinel. Records pick in decision-r<N>.md.
version: 1.0.0
source: pipeline-native
metadata:
  hermes:
    tags: [pipeline, decision, orchestrator]
    requires_toolsets: [pipeline, file]
---

# pipeline-decision-elicitation

Pipeline stage. Elicits human decision between option set. Sync or async. **Orchestrator-owned (no subagent).** Pipeline-internal.

**Hermes constraint (M4)**: `clarify` is blocked from leaf subagents. Decision elicitation runs at the **root orchestrator session only**, NOT inside an `options_source` spawn. options_source emits `options-r<N>.md` and returns. Orchestrator then invokes this skill.

## Inputs (caller writes before invoking)

- `<run-dir>/options-r<N>.md` — required canonical option set (≤4 options).

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

## Option B: <title>
...
```

## Trigger

Brief or plan declares `decision_points:`:

```yaml
decision_points:
  d1:
    after: <role>              # stage after which to inject
    topic: <one-line>
    options_source: <role>     # role that emits options-rN.md
    delivery: sync|async       # default sync
    timeout_days: 7            # async only
```

Orchestrator injects this stage after `<after>` role completes. `<options_source>` role spawn includes a `decision_emission: d<N>` flag in its goal/context; it emits `options-r<N>.md` and returns. Orchestrator (root) runs this skill. Post-decision, options_source re-spawn includes `decision-r<N>.md` in `read_paths` → emits pinned final output.

## Delivery: sync

1. Read `options-r<N>.md`.
2. Call `clarify(question=topic, options=[<option labels>])`.
3. User picks → write `decision-r<N>.md` (schema below).
4. Return to dep graph.

## Delivery: async (Discord)

**Hermes constraint (R5)**: `send_message` does NOT document interactive components. Use text-reply pattern.

**No custom gateway hook** — Hermes' native Discord gateway routes user replies back into the orchestrator session naturally. Orchestrator parses sentinels inline on its next turn.

1. Verify preconditions: `DISCORD_BOT_TOKEN` + `DISCORD_CHANNEL_ID` in env. Failure → degrade to sync; log `discord.warning` in pipeline.md.
2. Write `<run-dir>/awaiting-decision-r<N>.md` (schema below).
3. Append entry to `~/.hermes/pipeline-registry.json` mapping `run_id → run_dir` (for orchestrator's own cross-pipeline lookup when reply lands).
4. Update `pipeline.md` `paused_on_decision:` block. Set top-level `status: paused_on_decision`.
5. Call `send_message(target=<channel>, text=<formatted question>)`:

```
<topic>

[1] Option A: <title>
[2] Option B: <title>
[3] Option C: <title>

Reply: !decide <run_id>:d<N> <index>
```

6. Halt. Control returns to user.

**Reply handling (no gateway hook)**: when the user replies in the bound Discord channel, Hermes' native gateway delivers the message to the orchestrator session. Orchestrator parses the incoming text against `^!decide ([a-z]+(?:-[a-z]+){2}-[a-f0-9]{6}):d(\d+) (\d+)$` itself. On match:

1. Look up `run_id` in `~/.hermes/pipeline-registry.json` → resolve `run_dir`.
2. Verify `<run_dir>/awaiting-decision-r<N>.md` exists + decision_id matches.
3. Write `<run_dir>/decision-r<N>.md` with picked option index + label.
4. Remove `<run_dir>/awaiting-decision-r<N>.md`.
5. Remove registry entry.
6. Resume the pipeline.

Same flow handles `!resolve <run_id>:drift <action>` for drift menu — orchestrator parses inline.

## Resume

Resume triggers:
- User re-invokes orchestrator with `<<resume-pipeline-<artifact-id>>>` sentinel.
- Orchestrator startup scans `awaiting-decision-*.md` across active runs (opportunistic).

Procedure (every resume):
1. Check `<run-dir>/decision-r<N>.md` existence. Exists → parse + remove `paused_on_decision` from pipeline.md + resume.
2. Else check `<run-dir>/awaiting-decision-r<N>.md` `timeout_at`. `now >= timeout_at` → write `decision-r<N>.md` w/ `verdict: timeout` → halt + surface.
3. Else still pending — halt with one-line status update.

## awaiting-decision-r<N>.md schema

```yaml
---
decision_id: d<N>
delivery_mode: async
discord_channel: <channel-id>
opened_at: <iso8601>
timeout_at: <iso8601>          # opened_at + timeout_days
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
decided_by_discord_user: <user-id|null>   # async only
opened_at: <iso8601|null>                # async only
requesting_role: <role>
options_source: <role>
---

## Pick rationale
<user free-form notes from clarify OR "(chose via Discord !decide reply)"; empty if none>

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
  discord_channel: <channel-id|null>
  opened_at: <iso8601>
  timeout_at: <iso8601|null>
```

Remove block on resume. Set top-level `status: paused_on_decision` while waiting.

## Guardrails

- `N ≤ 4`.
- One paused decision per run max.
- Async timeout default 7d.
- `delivery: async` requires Discord env vars. Missing → degrade to sync.
- Async pre-check failures degrade to sync — NEVER hang silently.
- Drift menu uses same text-reply mechanism: sentinel `!resolve <run_id>:drift <rebase|abort|proceed>` (decision-router handles both).
- pipeline_friction_audit end-of-run audit: scan `<run-dir>/awaiting-decision-*.md`. Any remaining = anomaly → log + leave for next orchestrator scan.

## Failure modes

| Case | Policy |
|---|---|
| `DISCORD_BOT_TOKEN` missing | Degrade to sync; log warning. |
| `~/.hermes/pipeline-registry.json` missing | Create empty + append; warn in pipeline.md. |
| User replies with malformed sentinel | decision-router ignores message; pipeline stays paused. |
| Timeout reached | Write `decision-r<N>.md` w/ `verdict: timeout`; halt + surface. |
| Pipeline session dies during wait | Resume via `<<resume-pipeline-<id>>>` sentinel. |
| Concurrent pipelines (multiple awaiting `d1`) | run_id in sentinel disambiguates (B3 resolved). |

## See also

- `pipeline-handoff-doc` — continuity across decision pause + revision spawns.
- Decision-router hook at `~/.hermes/hooks/decision-router/handler.py`.
- Global registry at `~/.hermes/pipeline-registry.json`.
