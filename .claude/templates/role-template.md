# Role Template

Use this template when creating a new agent role. The Progenitor creates agents by writing `~/.claude/agents/<name>.md` with YAML frontmatter.

---

## YAML Frontmatter (required)

```yaml
---
name: agent-name
description: One-line description of what this agent does and when to use it
tools: Read, Grep, Glob                # comma-separated, Claude Code tool names
---
```

### Field reference

| Field | Required | Notes |
|-------|----------|-------|
| `name` | Yes | kebab-case identifier |
| `description` | Yes | One-line — used by Orchestrator for agent selection |
| `tools` | Yes | Claude Code tool names. Common sets: `Read, Grep, Glob` (read-only); add `Bash, Edit, Write` for impl roles |

---

## Markdown Body

Standard role contract. Keep terse.

### Required sections

#### `# Role: Name`
One-sentence purpose statement.

#### `## Do`
What the agent is authorized to do.

#### `## Don't`
What the agent must NOT do.

#### `## Output`
Artifact path + required fields. For pipeline roles, write to `<repo>/.pipeline_runs/<run-id>/...`. Verdict roles write `verdict-<type>-r<N>.md` w/ YAML frontmatter (verdict, role, review_type, loops, revision).

### Optional sections

- `## Focus` — emphasis areas (review roles)
- `## Process` — numbered methodology
- `## Verdict Policy` — Approved/Blocked rules
- `## Frontend Handoff Policy` — when UI changes need `frontend-handoff.md`
- `## Re-review Discipline` — for gate roles

### Speech
Output style: caveman:ultra. Inherited from global CLAUDE.md.
