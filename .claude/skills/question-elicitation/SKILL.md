---
name: question-elicitation
description: Ask human a free-form question mid-task via Slack and block until answered. Use when a role needs human input on an ad-hoc question with 2-4 button options. Distinct from decision-elicitation, which is orchestrator-owned and triggered by pre-declared decision_points in brief/plan.
source: pipeline-native
output-style: caveman:ultra
---

# question-elicitation

CLI-based human-in-loop. Any role calls `pipeline_ask.py`, blocks until human picks an option in Slack, gets answer key on stdout.

## When to use

- Mid-task ambiguity needing structural pick (not free-text response)
- 2-4 mutually-exclusive options
- Synchronous fit (you can wait — caller blocks)
- NOT for pre-declared structural picks → use `decision-elicitation` (orchestrator-owned, artifact-based)

## Invocation

```
Bash(
  command="python3 ~/.claude/pipeline/pipeline_ask.py "
          "--run <artifact-id> "
          "--header 'Auth method' "
          "--prompt 'Which auth do we use?' "
          "--opt A:OAuth --opt B:JWT "
          "--role <role-name> "
          "--hard-timeout 86400",
  timeout=86400000,
  description="Ask human auth choice"
)
```

`timeout` is the Bash tool's per-call ceiling (ms). Set to match `--hard-timeout` (s × 1000) or shorter. Default `BASH_MAX_TIMEOUT_MS=86400000` (24h) in `~/.claude/settings.json` permits long blocks.

## Attachments (optional)

When option text alone is not enough to explain the choices, attach one or
more files (HTML report, diff, image, design doc) to the question post.
The listener uploads each file to the run's thread *before* posting the
button message, so the reviewer reads context first and sees buttons last.

```
--attach /abs/path/options-report.html
--attach /abs/path/design-diff.png
```

- `--attach` is repeatable; one path per flag
- Paths must be absolute (or resolvable from CLI cwd)
- File must exist when CLI runs; missing file → CLI exits 4
- Slack file size cap: 1GB upload, 50MB inline preview
- HTML renders as a text file viewer in Slack (no live web rendering); use
  PNG/markdown for visual reports
- Idempotent on listener restart: state map keyed by
  `attach:<run>:<qid>:<path>` skips re-upload

Example — design review w/ HTML report:

```
Bash(
  command="python3 ~/.claude/pipeline/pipeline_ask.py "
          "--run <id> --header 'Design' "
          "--prompt 'Approve the design in the attached report?' "
          "--opt A:approve --opt B:revise "
          "--attach /tmp/design-options-r1.html",
  timeout=86400000,
)
```

## Output contract

| Exit | Stdout | Meaning |
|------|--------|---------|
| 0 | `A` (or chosen key) | answered |
| 3 | `TIMEOUT q<N>` | `--hard-timeout` reached, answer file written w/ verdict=timeout |
| 4 | (stderr) | malformed args or environment |

If harness SIGKILLs the Bash call (timeout exceeded), question artifact persists. Re-invoke same command with `--id q<N>` to resume blocking — listener daemon still alive, no duplicate Slack post.

## Retry pattern

Caller wraps Bash call. On non-zero exit or SIGKILL:

```
1st call:  ... pipeline_ask.py --run X --header H --prompt P --opt A:foo --opt B:bar ...
           → SIGKILL after Bash timeout
2nd call:  ... pipeline_ask.py --run X --id q1
           → resumes block; listener respawned if dead
```

On exit 3 (`TIMEOUT q<N>`): treat as cancelled; do not retry. Answer file has `verdict: timeout`.

## Artifact lifecycle

| File | Owner | Lifetime |
|------|-------|----------|
| `question-r<N>.md` | CLI (first call) | run-dir lifetime; never deleted |
| `answer-r<N>.md` | Listener (on button click) OR CLI (on hard-timeout) | run-dir lifetime |
| `slack-listener.pid` | Listener | until idle-exit |
| `slack-state.json` | Listener | run-dir lifetime |

`answer-r<N>.md` existence = satisfied signal for both CLI poll loop + listener IdleMonitor.

## Preconditions

- `~/.claude/pipeline/pipeline_ask.py` executable
- `~/.claude/pipeline/slack_listener.py` present
- `~/.claude/pipeline/slack.env.local` w/ `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`
- `<project>/.pipeline/pipeline.toml` w/ `[slack].channel` OR `SLACK_CHANNEL` env
- `uv` on PATH (listener uses PEP 723 inline deps)
- Run dir exists: `<project>/.pipeline/runs/<artifact-id>/`

Missing preconditions → CLI exits 4 OR listener fails to spawn → no answer ever lands → hard-timeout → exit 3. Caller should validate setup before first use per run.

## Guardrails

- 2-4 options. CLI rejects outside range.
- Keys typically A/B/C/D (listener registers `question_pick_<A..D>` action handlers).
- One `--header` ≤12 chars (Slack truncates beyond).
- Listener idle-exits 30s after all questions answered AND all decisions resolved.
- Concurrent questions in same run: listener handles fine; multiple `question-r<N>.md` files coexist; each gets own Slack message.

## Sync fallback

Not supported in this CLI. Sync path = orchestrator uses `AskUserQuestion` tool directly without invoking this skill. CLI is async-Slack-only by design (keeps surface tiny).

## See also

- `decision-elicitation` — pre-declared orchestrator-owned variant w/ artifact pause/resume
- `~/.claude/pipeline/slack_listener.py` — shared listener daemon (also serves decisions)
