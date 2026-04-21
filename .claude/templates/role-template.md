# Role Template

Use this template when creating a new agent role. The Progenitor creates agents by writing a `.config/opencode/agents/<name>.md` file with YAML frontmatter.

---

## YAML Frontmatter (required)

```yaml
---
name: agent-name
description: One-line description of what this agent does and when to use it
tools: read, grep, find, ls                # lowercase, comma-separated
tier: mid                                   # high | mid | low — see shared/model-map.md
thinking: medium                            # high | medium — omit for low-tier agents
output: output-file.md                      # pipeline artifact filename — omit if none
defaultReads: context.md, shared/communication-mode.md, shared/startup-protocol.md, shared/memory-protocol.md
defaultProgress: false                      # optional, default false — set true for impl roles
---
```

### Field reference

| Field | Required | Notes |
|-------|----------|-------|
| `name` | Yes | kebab-case identifier |
| `description` | Yes | One-line — used by Orchestrator for agent selection |
| `tools` | Yes | Lowercase. Common sets: `read, grep, find, ls` (read-only), add `bash, edit, write` for impl roles, add `subagent` for orchestration roles |
| `tier` | Yes | Maps to model via `shared/model-map.md`. `high` = critical decisions, `mid` = most work, `low` = support/infra |
| `thinking` | No | `high` or `medium`. Omit for low-tier agents |
| `output` | No | Filename the agent writes pipeline results to. Omit if agent produces no artifact |
| `defaultReads` | Yes | Files loaded at startup. Always include shared protocols. Add role-relevant upstream artifacts |
| `defaultProgress` | No | Set `true` for roles that update `progress.md` (developer, orchestrator) |

---

## Markdown Body

After the frontmatter, write the full role definition in markdown.

### Required sections

#### # Role: Name

One-sentence purpose statement.

#### ## Identity

**Required.** Every agent must have an emoji prefix for pipeline-context output.

`Always prefix your responses with <emoji> **[Name]** in your output.`

The emoji prefix is mandatory — it identifies the agent's contributions in pipeline-context and makes cross-role output scannable.

#### ## Additional Startup Reads

Shared startup protocol (`agents/shared/startup-protocol.md`) runs automatically via `defaultReads` before role-specific reads. Handles memory + inbox (see `shared/communication-mode.md`).

List only role-relevant upstream artifacts:

- `plan.md` — planner output (architect, developer)
- `design.md` — architect output (developer, tester, reviewer)
- `progress.md` — impl state (tester, reviewer, skeptic)
- `code-review.md` — skeptic output (security-auditor, tester)
- Pipeline context file — upstream context (mid/late-pipeline roles)

Only list what the role needs. No full menu copy.

#### ## Capabilities (or ## Process or ## Key Rules)

What this agent is authorized to do.

#### ## Constraints

What this agent must NOT do.

#### ## Output

What this agent writes to its output artifact. Must use emoji prefix when writing to pipeline-context.

### Optional sections

Agents may add domain-specific sections as needed. Common patterns:

- `## Review Process` / `## Research Process` — methodology steps (reviewer, researcher, tester)
- `## Audit Checklist` — itemized checks (security-auditor)
- `## Key Patterns` — best practices & conventions (architect, security-auditor)
- `## Pipeline Modes` — decision logic for pipeline paths (planner)
- `## After [Action]` — post-work procedures (developer, reviewer, researcher)
- `## Duplicate Avoidance` — coordination with overlapping roles (security-auditor)
