# slack-unbind

Deactivate the current session's Slack thread binding. Posts a closing message in the bound thread, flips the binding to inactive, and stops the inbox daemon.

Invoke the CLI verbatim. Do not paraphrase arguments.

```bash
uv run --script ~/.claude/pipeline/session_bind.py deactivate
```

The inbox directory and all its files are preserved after deactivation (audit trail). Only the active flag is flipped. Re-running `/slack-bind` later reuses the original thread.
