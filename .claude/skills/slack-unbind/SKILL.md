---
name: slack-unbind
description: Release current Claude Code session's binding to its Slack thread. Stops the session inbox daemon. Preserves the inbox subtree on disk for audit. Trigger on user intent like "stop slack", "unbind slack", "close slack thread", "stop posting to slack", "release slack binding", "/slack-unbind". Idempotent: re-running on an already-inactive binding is a no-op.
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
4. If `active=false` already → idempotent print "already inactive". Still SIGTERMs stale daemon pid if present (ESRCH ignored).
5. Posts `:checkered_flag: *Session ended at <iso>*` reply to bound thread.
6. Flips `active=false`, sets `ended_at`, clears `inbox_daemon_pid`.
7. SIGTERM the inbox daemon (gated on `/proc/<pid>/cmdline` match for safety).
8. Prints `ok`.

## Preserved on disk

- Inbox subtree (`.../inbox/`) — NOT pruned. Held for audit. Reactivate reuses same thread_ts.
- State file remains (active=false). Next `slack-bind` reactivates.

## Reverse

Use `slack-bind` to reactivate (reuses same thread).
