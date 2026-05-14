# slack-status

Show the current session's Slack binding status. Prints JSON state (channel, thread_ts, active, daemon pid liveness) or "unbound" if no binding exists.

Invoke the CLI verbatim. Do not paraphrase arguments.

```bash
uv run --script ~/.claude/pipeline/session_bind.py status
```

The output includes `daemon_pid_alive` (bool) indicating whether the inbox daemon process is currently running.
