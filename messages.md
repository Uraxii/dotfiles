# Message Log

Same-session sync comm within single pipeline run. Append-only.

Cross-session async → inbox system: `agents/shared/communication-mode.md`.

## Format

```
### [YYYY-MM-DD HH:MM] From: <sender> → To: <recipient> [STATUS]
<message body>
```

**Status tags:**
- `[PENDING]` — Awaiting response or action
- `[IN PROGRESS]` — Being worked on by the recipient
- `[DONE]` — Handled, no further action needed
- `[BLOCKED]` — Cannot proceed, requires resolution

---

_No messages yet._
