# Pipeline Decisions

Human-in-the-loop branching for pipeline runs. Lets the orchestrator pause at declared decision points, present N options (N ≤ 4), and resume on user pick. Two delivery channels: synchronous terminal prompt (`AskUserQuestion`) or asynchronous GitHub issue + 10-minute poll.

## When the stage runs

A decision-elicitation stage is injected by the orchestrator only when:

1. The brief or canonical plan declares a `decision_points:` block, **OR**
2. (Phase 2+) A role mid-run self-flags ambiguity and asks the orchestrator to insert a decision point.

POC scope = declarative only. Self-flag = follow-up phase.

Default channel is `sync`. Use `async` when the user is off-terminal, when the decision involves stakeholders beyond the runner, or when the pipeline runs headless (e.g. cron via [[Pipeline Skills|schedule]]).

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

## Async delivery

Preconditions:

- `command -v gh` succeeds
- `gh auth status` is clean
- `git remote get-url origin` matches `github.com[:/]`

Any failure degrades to `sync` with a warning logged to `pipeline.md`.

Flow:

1. `gh issue create` with labels `pipeline-decision` and `pipeline-<artifact-id>`, assignee `@me`, body synthesized from `options-r<N>.md` plus a reply-protocol footer.
2. Write `awaiting-decision-r<N>.md` with issue URL, number, timeout, poll cadence.
3. Update `pipeline.md`: `status: paused_on_decision`, add `paused_on_decision:` block.
4. `ScheduleWakeup(delaySeconds=600, prompt="<<resume-pipeline-<artifact-id>>>", reason="polling decision issue #N @10min")`.
5. Orchestrator halts. Control returns to the user (or the harness).

The user gets a GitHub notification (email + mobile push) and replies on the issue from any device.

### Poll loop

Each wake:

1. Read `awaiting-decision-r<N>.md` to recover state.
2. `gh issue view <N> --json state,comments,closedAt`.
3. Route:
   - Issue closed without parsed reply → `verdict: cancelled`. Halt.
   - New comment from issue author matches `/pick A|B|C|D` (or `/pick 1-4`) → confirmation reply, close issue, write `decision-r<N>.md`, resume pipeline.
   - New comment but no strict match → hint comment, re-wake. After 3 hint comments → halt + surface.
   - `now >= timeout_at` → `verdict: timeout`. Comment on issue, halt.
   - Else → update `last_polled_at`, `next_wake_at`; `ScheduleWakeup` 600s.

### Resume sentinel

`<<resume-pipeline-<artifact-id>>>` is recognized at orchestrator startup. The orchestrator skips intake, locates `awaiting-decision-*.md` in the matching run dir, and routes directly to the poll procedure.

Fallback: if `ScheduleWakeup` is unavailable (no `/loop` context), the user can re-invoke manually with `resume <artifact-id>` once they've replied on the issue.

## Reply syntax

POC supports strict only:

```
/pick A
/pick option-2
/pick 3
```

(Phase 4 adds free-form LLM-parsed replies with confirmation comments.)

## Guardrails

- N ≤ 4 (matches `AskUserQuestion` limit).
- One paused decision per run. Multi-decision runs sequence them.
- Default timeout 7 days; override via `timeout_days` per point.
- Confirmation comment posted **before** any pick is acted on. Audit trail.
- Comments from non-author/non-assignee are ignored.
- [[Pipeline Stages|friction-reviewer]] end-of-run audit closes any orphaned `pipeline-<artifact-id>` labeled issues with `Run complete. Decision no longer needed.`

## Failure modes

| Case | Behavior |
|---|---|
| `gh` missing / unauthed / non-github remote | Fall back to sync, log warning |
| Issue create succeeds but state-file write fails | Close issue with abort comment, halt, surface |
| User closes issue pre-reply | `verdict: cancelled`, halt |
| Free-form comment (POC) | Hint reply, re-wake; halt after 3 hints |
| Session dies mid-wait | Resume via sentinel on next orchestrator invocation OR manual `resume <id>` |
| `ScheduleWakeup` no-op (no `/loop`) | Document fallback: user manually re-invokes; orchestrator polls on demand |

## Related

- [[Pipeline Overview]]
- [[Pipeline Stages]]
- [[Pipeline Artifacts]] — `options-r<N>.md`, `decision-r<N>.md`, `awaiting-decision-r<N>.md` schemas
- [[Pipeline Skills|decision-elicitation skill]]
- [[Pipeline Decisions Rollout]] — phased delivery plan
