---
name: slack-bind
description: Bind current Claude Code session to a persistent Slack thread. After bind, every pipeline notification, decision option, and pipeline-emitted Slack post lands in that thread instead of creating a new per-pipeline thread. User-reply capture into per-session inbox dir. Trigger on user intent like "use slack", "bind slack", "open a slack thread for this session", "use slack from now on", "send to slack", "start posting to slack", "/slack-bind". Idempotent: re-running on an already-bound session reuses the existing thread.
source: pipeline-native
output-style: caveman:ultra
---

# slack-bind

Activate session-bound Slack threading for current Claude Code process. Pipeline-internal.

## Invocation

Claude: `Skill(skill: "slack-bind")` or run the CLI directly via Bash.

CLI (preferred — deterministic, no model paraphrase):

```bash
uv run --script ~/.claude/pipeline/session_bind.py activate
```

OC: `skill({ name: "slack-bind" })` — body invokes same CLI.

## Behaviour

1. Reads `CLAUDE_CODE_SESSION_ID` from env. Refuses if missing.
2. flock `~/.claude/sessions/<sid>/.lock` (mutex; rejects concurrent activate).
3. Resolves Slack channel: `~/.claude/pipeline/slack.env.local` `SLACK_CHANNEL` (global) → `<cwd>/.pipeline/pipeline.toml [slack].channel` (per-project override).
4. Reaps any surviving legacy `slack_listener.py` processes (one-shot migration step).
5. If state file exists + `active=true` → idempotent return (status `already_active`). Updates `last_bound_at`. Ensures host router alive.
6. If state file exists + `active=false` → reactivate. Reuses existing `thread_ts`. Posts a "Session reopened" reply (not new root). Ensures host router alive.
7. Else → posts root message `:hourglass_flowing_sand: *Session started* <sid-short> (cwd=~)` to channel. Captures `thread_ts`. Writes `~/.claude/sessions/<sid>/slack.json` mode 600. Spawns host router (`comms/router.py`) if not already alive.
8. Prints JSON `{channel, thread_ts, session_id, status}` to stdout.

## Output contract

Stdout = single JSON object. `status` ∈ `{activated, reactivated, already_active}`.

Exit non-zero on:
- `CLAUDE_CODE_SESSION_ID` missing
- Slack token / channel unresolvable
- flock contention
- Slack API failure (network, auth)
- Schema version mismatch

## Side effects

- Creates `~/.claude/sessions/<sid>/` (mode 700) on first bind.
- Ensures host router (`comms/router.py`) is alive; spawns detached if absent or stale PID.
  Router is host-scoped (not session-scoped): one process serves all bindings.
  Router survives session crash; idle-exits at 30 min when binding set is empty.
- Posts one root Slack message per fresh bind. Reactivate posts a small reply, not a new root.
- Reaps any orphan `slack_listener.py` processes found on the host (migration cleanup).
- One-shot reap of legacy `~/.claude/slack-router/` daemon before spawning new daemon.

## Reverse

Use `slack-unbind` skill or `uv run --script ~/.claude/pipeline/session_bind.py deactivate`.

## State

- `~/.claude/sessions/<sid>/slack.json` — binding state, mode 600
- `~/.claude/sessions/<sid>/inbox/<msg_ts>.json` — user replies routed by host router
- `~/.claude/comms-router/router.{pid,log}` — host-level router process state (NOT per-session)

## Related

- `slack-status` — query current binding
- `slack-unbind` — release binding (removes session route; router stays alive for other sessions)
- `decision-elicitation`, `question-elicitation` — pipeline stages that auto-route into bound thread when binding active
