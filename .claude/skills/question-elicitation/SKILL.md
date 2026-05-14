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

## Preconditions

- `~/.claude/pipeline/pipeline_ask.py` executable
- Active session binding: run `slack-bind` first. No binding → CLI exits 4 with clear message.
- `~/.claude/pipeline/slack.env.local` w/ `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`
- `<project>/.pipeline/pipeline.toml` w/ `[slack].channel` OR `SLACK_CHANNEL` env
- `uv` on PATH (notify uses PEP 723 inline deps)
- Run dir exists: `<project>/.pipeline/runs/<artifact-id>/`

Missing preconditions → CLI exits 4. No hang, no silent failure.

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

`timeout` is the Bash tool's per-call ceiling (ms). Set to match `--hard-timeout` (s × 1000).
Default `BASH_MAX_TIMEOUT_MS=86400000` (24h) in `~/.claude/settings.json` permits long blocks.

## Attachments (optional)

Attach files to provide context before the buttons appear.

```
--attach /abs/path/options-report.html
--attach /abs/path/design-diff.png
```

- `--attach` repeatable; one path per flag
- Paths must be absolute
- File must exist when CLI runs; missing file → CLI exits 4
- HTML auto-converted to PDF for inline Slack preview

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
| 4 | (stderr) | malformed args, missing binding, or environment error |

If harness SIGKILLs the Bash call (timeout exceeded), question artifact persists.
Re-invoke same command with `--id q<N>` to resume blocking.

## Retry pattern

Caller wraps Bash call. On non-zero exit or SIGKILL:

```
1st call:  ... pipeline_ask.py --run X --header H --prompt P --opt A:foo --opt B:bar ...
           → SIGKILL after Bash timeout
2nd call:  ... pipeline_ask.py --run X --id q1
           → resumes block; re-posts via notify if needed
```

On exit 3 (`TIMEOUT q<N>`): treat as cancelled; do not retry. Answer file has `verdict: timeout`.

## How it works

1. CLI validates active session binding. Exits 4 if absent.
2. Writes `question-r<N>.md` + initial `.slack-context.json` to run dir.
3. Calls `pipeline_notify.py --kind question --run-dir <path> --qid <qid>` as subprocess.
   - notify posts button-block message into bound session thread.
   - Button `value` format: `<phash8>|<run-id>|<qid>|<choice>`.
4. Router daemon (`slack_router.py`) handles `question_pick_<A..D>` button clicks.
   - Router writes `answer-r<N>.md` in run dir.
5. CLI polls for `answer-r<N>.md` existence (1s interval).
6. On file found: reads `chosen_key`, prints to stdout, exits 0.

CLI does not spawn any Slack daemon. All Slack I/O goes through the host-bound router.

## Artifact lifecycle

| File | Owner | Lifetime |
|------|-------|----------|
| `question-r<N>.md` | CLI (first call) | run-dir lifetime; never deleted |
| `.slack-context.json` | CLI (initial); notify (updates channel/thread_ts/message_ts) | run-dir lifetime |
| `answer-r<N>.md` | Router (on button click) OR CLI (on hard-timeout) | run-dir lifetime |

`answer-r<N>.md` existence = satisfied signal for CLI poll loop.

## Guardrails

- 2-4 options. CLI rejects outside range.
- Keys typically A/B/C/D (router registers `question_pick_<A..D>` action handlers).
- One `--header` ≤12 chars (Slack truncates beyond).
- Concurrent questions in same run: each gets own Slack message; answer files are independent.

## Sync fallback

Not supported in this CLI. Sync path = orchestrator uses `AskUserQuestion` tool directly
without invoking this skill. CLI is async-Slack-only by design (keeps surface tiny).

## See also

- `decision-elicitation` — pre-declared orchestrator-owned variant w/ artifact pause/resume
- `slack-bind` — required prerequisite; activates session binding
- `~/.claude/pipeline/slack_router.py` — host-bound router daemon (handles button clicks)
- `~/.claude/pipeline/session_slack.py` — session binding helper (stdlib-only)
