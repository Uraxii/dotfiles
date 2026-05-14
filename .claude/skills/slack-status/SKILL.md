---
name: slack-status
description: Report whether the current Claude Code session is bound to a Slack thread; if bound, print the channel id, thread_ts, daemon pid, and daemon liveness. Trigger on user intent like "slack status", "am I bound to slack", "check slack binding", "is slack active", "/slack-status".
source: pipeline-native
output-style: caveman:ultra
---

# slack-status

Query session-bound Slack threading state. Pipeline-internal.

## Invocation

Claude: `Skill(skill: "slack-status")` or run CLI directly.

CLI (preferred):

```bash
uv run --script ~/.claude/pipeline/session_bind.py status
```

## Output

- `unbound` (single token) → no state file for current `CLAUDE_CODE_SESSION_ID`
- JSON object → state file present. Fields: `session_id`, `channel_id`, `thread_ts`, `cwd`, `started_at`, `last_bound_at`, `ended_at`, `active`, `schema_version`, `inbox_daemon_pid`, `daemon_pid_alive` (bool computed at query time).

## Use cases

- Confirm `/slack-bind` succeeded
- Check whether the inbox daemon is still alive
- Read `thread_ts` for cross-referencing with Slack UI
- Diagnose "did my pipeline post to bound thread?"

## Reverse

This is read-only. No state changes.
