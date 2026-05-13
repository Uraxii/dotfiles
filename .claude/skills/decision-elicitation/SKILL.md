---
name: decision-elicitation
description: Pipeline decision-point stage. Elicits human pick between N options (N ≤ 4). Sync delivery via AskUserQuestion or async via GH issue + 10min ScheduleWakeup poll. Records pick in decision-r<N>.md. Use when brief/plan declares decision_points or a role flags ambiguity.
source: pipeline-native
output-style: caveman:ultra
---

# decision-elicitation

Pipeline stage. Elicits human decision between option set. Sync or async. Orchestrator-owned (no subagent). Pipeline-internal.

## Invocation

Claude: `Skill(skill: "decision-elicitation", args: "run-dir=<path>, decision-id=d<N>, mode=<sync|async>")`

`mode` default = `sync`. `async` requires `gh` CLI authenticated + origin on github.com; else skill falls back to `sync` and warns.

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

## Delivery: async

Preconditions:
- `command -v gh` exit 0
- `gh auth status` exit 0
- `git remote get-url origin` matches `github.com[:/]`

Failure → emit warning to pipeline.md, fall back to sync.

Flow:
1. Synthesize issue body from `options-r<N>.md` + reply protocol footer:
   ```
   ## Reply protocol
   Reply with `/pick A` (or B/C/D, or `1`/`2`/`3`/`4`, or option title).
   Free-form replies parsed by bot w/ confirmation comment before action.
   Timeout: <timeout_at>. After timeout: run halts, surface to terminal.

   Run: <artifact-id>
   Decision: d<N>
   Requesting role: <role>
   ```
2. `gh issue create --title "[<artifact-id>] Decision d<N>: <topic>" --body-file <synthesized> --assignee @me --label pipeline-decision --label "pipeline-<artifact-id>"`
3. Capture issue URL + number.
4. Write `<run-dir>/awaiting-decision-r<N>.md` (schema below).
5. Update `pipeline.md` `paused_on_decision:` block.
6. `ScheduleWakeup(delaySeconds=600, prompt="<<resume-pipeline-<artifact-id>>>", reason="polling decision issue #<N> @10min")`.
7. Halt. Control returns to user.

## Resume (async only)

Triggers:
- ScheduleWakeup fires w/ resume sentinel
- User manually re-invokes orchestrator w/ "resume <artifact-id>"
- Orchestrator startup detects `awaiting-decision-*.md` in active runs (opportunistic)

Poll procedure (every wake):
1. Read `awaiting-decision-r<N>.md` → issue_number, timeout_at.
2. `gh issue view <N> --json state,comments,closedAt`.
3. Branch:
   - `state == "CLOSED"` AND no decision parsed → cancel; write `decision-r<N>.md` w/ `verdict: cancelled`; halt.
   - New comment from `issue.author` (or `@me`) after `awaiting.last_polled_at` → parse:
     - Strict regex `/^\s*\/pick\s+(?:option-)?([A-Da-d]|[1-4])\s*$/im` on comment body.
     - On match → confirm via reply comment: `Interpreted as Option <X>. Proceeding now.` Close issue. Write `decision-r<N>.md`. Resume pipeline (re-spawn options_source w/ decision in Read set).
     - No strict match → free-form (Phase 4 LLM parse); for POC: post hint comment `Reply not parsed. Use /pick A|B|C|D. Re-polling at <next_wake_at>.` Re-wake.
   - `now >= timeout_at` → write `decision-r<N>.md` w/ `verdict: timeout`; comment on issue `Decision timed out. Pipeline halted.` (do not close). Halt + surface.
   - Else → update `awaiting-decision-r<N>.md` `last_polled_at` + `next_wake_at`; `ScheduleWakeup(delaySeconds=600, ...)`.

## awaiting-decision-r<N>.md schema

```yaml
---
decision_id: d<N>
issue_url: <url>
issue_number: <int>
opened_at: <iso8601>
timeout_at: <iso8601>          # opened_at + timeout_days
poll_cadence_s: 600            # 10 minutes
last_polled_at: <iso8601|null>
next_wake_at: <iso8601>
requesting_role: <role>
options_source: <role>
delivery_mode: async
---
```

## decision-r<N>.md schema

```yaml
---
decision_id: d<N>
verdict: chosen | timeout | cancelled
chosen_option: A | B | C | D | null
delivery_mode: sync | async
issue_url: <url|null>
opened_at: <iso8601|null>      # async only
decided_at: <iso8601>
requesting_role: <role>
options_source: <role>
---

## Pick rationale
<user free-form notes from comment body OR from AskUserQuestion notes; empty if none>

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
  issue_url: <url|null>
  issue_number: <int|null>
  opened_at: <iso8601>
  timeout_at: <iso8601|null>
  next_wake_at: <iso8601|null>
```

Remove block when resumed.

Set top-level `status: paused_on_decision` while waiting.

## Guardrails

- `N ≤ 4` (matches AskUserQuestion limit).
- One paused decision per run max. Multi-decision runs sequence them.
- Timeout default 7d. Configurable per decision via `timeout_days`.
- friction-reviewer end-of-run audit: scan `gh issue list --label pipeline-<artifact-id> --state open`. Any open at run-complete → close w/ comment `Run complete. Decision no longer needed.`
- Async pre-check failures degrade to sync (don't hard-fail).
- Comment from non-author/non-assignee = ignored.
- Confirmation comment posted BEFORE acting on parsed pick. Audit trail.

## Failure modes

| Case | Policy |
|---|---|
| `gh` missing | Fall back to sync. Warn in pipeline.md. |
| `gh` auth fail | Fall back to sync. Warn in pipeline.md. |
| Origin not github.com | Fall back to sync. Warn in pipeline.md. |
| Issue created but write to `awaiting-*.md` fails | Close issue w/ `Pipeline state write failed. Aborted.`; halt + surface. |
| User closes issue before reply | `verdict: cancelled`. Pipeline halts. |
| Free-form comment (POC: no LLM parse) | Hint comment, re-wake. After 3 hint comments → halt + surface. |
| Pipeline session dies during wait | Resume on next orchestrator invocation via startup `awaiting-*.md` scan. |
| ScheduleWakeup unavailable (not in /loop context) | Document fallback: user manually re-invokes "resume <artifact-id>"; orchestrator polls on demand. |

## Notes

- `<<resume-pipeline-<artifact-id>>>` sentinel: orchestrator startup parses incoming prompt; if matches sentinel pattern, route directly to resume logic, skip intake.
- POC: only strict `/pick` syntax parsed. Free-form LLM parse = Phase 4.
- POC: HTML companion not required. Markdown options-rN.md sufficient. HTML = Phase 1.
- Two-mode design (sync default, async opt-in) keeps fast-path latency unchanged for terminal-attached runs.
