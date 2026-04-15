# Role Template

Use this template when creating a new agent role. The Progenitor creates agents by writing a `.config/opencode/agents/<name>.md` file with YAML frontmatter.

---

## YAML Frontmatter (required)

```yaml
---
name: agent-name
description: One-line description of what this agent does and when to use it
tools: Read, Grep, Glob
model: inherit
---
```

## Markdown Body

After the frontmatter, write the full role definition in markdown. Required sections:

### # Role: Name

One-sentence purpose statement.

### ## Identity

`Always prefix your responses with <emoji> **[Name]** in your output.`

### ## Startup

Shared startup protocol (`agents/shared/startup-protocol.md`) runs auto before role-specific reads. Handles memory + inbox (see `shared/communication-mode.md`).

Under `## Additional Startup Reads`, list only role-relevant resources:

- `plan.md` — planner output (architect, developer)
- `design.md` — architect output (developer, tester, reviewer)
- `progress.md` — impl state (tester, reviewer, skeptic)
- `code-review.md` — skeptic output (security-auditor, tester)
- Pipeline context file — upstream context (mid/late-pipeline roles)

Only list what role needs. No full menu copy.

### ## Capabilities (or ## Process or ## Key Rules)

What this agent is authorized to do.

### ## Constraints

What this agent must NOT do.

### ## Output

What this agent appends to pipeline context file when done.
