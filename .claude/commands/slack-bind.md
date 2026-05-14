# slack-bind

Bind this Claude Code session to a persistent Slack thread. Every subsequent pipeline notification, decision option, and free-form reply will land in that thread rather than creating a new per-pipeline thread.

Invoke the CLI verbatim. Do not paraphrase arguments.

```bash
uv run --script ~/.claude/pipeline/session_bind.py activate
```

The command reads `CLAUDE_CODE_SESSION_ID` from the environment, posts a root message to the configured Slack channel, persists state to `~/.claude/sessions/<sid>/slack.json`, and spawns the per-session inbox daemon. Output is JSON with `channel`, `thread_ts`, `session_id`, and `daemon_pid`.

If the session is already bound, the existing thread is reused (no new root message posted).
