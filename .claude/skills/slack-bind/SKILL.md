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
4. If state file exists + `active=true` → idempotent return (status `already_active`). Updates `last_bound_at`. No new root msg.
5. If state file exists + `active=false` → reactivate. Reuses existing `thread_ts`. Posts a "Session reopened" reply (not new root). Respawns inbox daemon.
6. Else → posts root message `:hourglass_flowing_sand: *Session started* <sid-short> (cwd=~)` to channel. Captures `thread_ts`. Writes `~/.claude/sessions/<sid>/slack.json` mode 600. Spawns `session_inbox.py` daemon.
7. Prints JSON `{channel, thread_ts, session_id, daemon_pid, status}` to stdout.

## Output contract

Stdout = single JSON object. `status` ∈ `{activated, reactivated, already_active}`.

Exit non-zero on:
- `CLAUDE_CODE_SESSION_ID` missing
- Slack token / channel unresolvable
- flock contention
- Slack API failure (network, auth)
- Schema version mismatch

## Side effects

- Creates `~/.claude/sessions/<sid>/` (mode 700) on first bind
- Spawns `session_inbox.py` background daemon (Bolt Socket Mode listener for thread-message events). Daemon survives across listener restarts and pipeline runs.
- Posts one root Slack message per fresh bind. Reactivate posts a small reply, not a new root.

## Reverse

Use `slack-unbind` skill or `uv run --script ~/.claude/pipeline/session_bind.py deactivate`.

## State

- `~/.claude/sessions/<sid>/slack.json` — binding state, mode 600
- `~/.claude/sessions/<sid>/inbox/<msg_ts>.json` — user replies captured by daemon
- `~/.claude/sessions/<sid>/inbox-daemon.{pid,log}` — daemon process state

## Related

- `slack-status` — query current binding
- `slack-unbind` — release binding + stop daemon (preserves inbox subtree for audit)
- `decision-elicitation`, `question-elicitation` — pipeline stages that auto-route into bound thread when binding active
