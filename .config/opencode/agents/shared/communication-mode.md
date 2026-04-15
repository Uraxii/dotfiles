# Communication Mode

`<ROLE>` = agent name. `<TASK>` = assigned task/pipeline-run ID.

## Channels

| Channel | Scope | When |
|---------|-------|------|
| `messages.md` | Same-session sync | Within single pipeline run, append-only |
| Inbox | Cross-session async | Survives between sessions, task-scoped |
| Pipeline context | Stage→stage handoff | Accumulated shared context, `shared/pipeline-context-template.md` |

---

## Inbox

### Task ID

Orchestrator assigns `<TASK>` at spawn. Format: `run-YYYYMMDD-N` (e.g., `run-20260415-1`).
No task ID (standalone, not in pipeline) → use `general`.

### Routing

```
<scope>/inbox/<ROLE>/<TASK>/unread/<uuid>.yaml   # task-specific
<scope>/inbox/<ROLE>/general/unread/<uuid>.yaml   # role-wide, no task context
```

| Scope | Base path | When |
|-------|-----------|------|
| Global | `~/.config/opencode/inbox/` | Msg relevant beyond current project |
| Project | `<project>/.opencode/inbox/` | Msg tied to project pipeline/task |

Instance reads only its `<TASK>` dir + `general/`. First to process `general/` msg deletes it.

### Read (startup)

1. List `unread/*.yaml` — task dir + `general/` dir, both scopes
2. Sort: critical → high → normal → low, then oldest first
3. Read → act/incorporate → persist lessons to memory if needed → delete file

### Send

1. Generate UUID v4
2. `mkdir -p <scope>/inbox/<recipient>/<task>/unread/`
3. Write `<uuid>.yaml`

### Message Schema

```yaml
id: "f47ac10b-58cc-4372-a567-0e02b2c3d479"
from: orchestrator
to: developer
task: "run-20260415-1"
timestamp: "2026-04-15T14:32:00Z"
priority: normal
subject: "Skeptic gate failed — fix lint errors"
context:
  project: "/home/nikki/Git/project"
  pipeline_context: "review.md"
  files:
    - src/auth.ts
body: |
  Skeptic blocked. 3 lint errors in src/auth.ts.
  Fix → re-run Skeptic gate. 2 loops remain.
```

| Field | Req | Type | Notes |
|-------|-----|------|-------|
| `id` | ✓ | UUID v4 | = filename |
| `from` | ✓ | string | Sender agent |
| `to` | ✓ | string | Recipient role |
| `task` | ✓ | string | Task ID or `"general"` |
| `timestamp` | ✓ | ISO 8601 | Creation time |
| `priority` | ✓ | enum | `low` `normal` `high` `critical` |
| `subject` | ✓ | string | One-line summary |
| `context` | — | map | Flexible metadata (project, files, pipeline context, etc.) |
| `body` | ✓ | string | Message content |

### Priority

| Level | Use |
|-------|-----|
| `critical` | Blocking, security vuln, data loss |
| `high` | Gate fail, remediation, time-sensitive |
| `normal` | Handoff, info, follow-up |
| `low` | Suggestion, FYI |
