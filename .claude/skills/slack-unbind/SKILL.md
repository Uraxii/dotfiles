---
name: slack-unbind
description: Release current Claude Code session's binding to its Slack thread. Removes binding entry; host router drops the route on next poll. Preserves the inbox subtree on disk for audit. Trigger on user intent like "stop slack", "unbind slack", "close slack thread", "stop posting to slack", "release slack binding", "/slack-unbind". Idempotent: re-running on an already-inactive binding is a no-op.
source: pipeline-native
output-style: caveman:ultra
---

# slack-unbind

Deactivate session-bound Slack threading. Pipeline-internal.

## Invocation

Claude: `Skill(skill: "slack-unbind")` or run CLI directly.

CLI (preferred):

```bash
uv run --script ~/.claude/pipeline/session_bind.py deactivate
```

## Behaviour

1. Reads `CLAUDE_CODE_SESSION_ID`. Refuses if missing.
2. flock `.lock` (mutex w/ activate).
3. Reads state file. If missing → exit non-zero "not bound".
4. If `active=false` already → idempotent print "already inactive".
5. Posts `:checkered_flag: *Session ended at <iso>*` reply to bound thread.
6. Flips `active=false`, sets `ended_at`.
7. Prints `ok`.

Router behavior: removes binding entry from state file. Host router (`comms/router.py`)
drops this session's route on its next 3s poll. Router stays alive to serve other
bound sessions. For immediate router shutdown: `pkill -f comms/router.py`.
Router idle-exits automatically after 30 min if no other sessions remain bound.

## Preserved on disk

- Inbox subtree (`.../inbox/`) — NOT pruned. Held for audit. Reactivate reuses same thread_ts.
- State file remains (active=false). Next `slack-bind` reactivates.

## Reverse

Use `slack-bind` to reactivate (reuses same thread).
