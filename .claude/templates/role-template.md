# Role Template

Use this template when creating a new agent role. The Progenitor creates agents by writing `.claude/agents/<name>.md` with YAML frontmatter.

---

## YAML Frontmatter (required)

```yaml
---
name: agent-name
description: One-line description of what this agent does and when to use it
model: opus | sonnet | haiku
tools: Read, Grep, Glob, Skill           # comma-separated, Claude Code tool names. ALWAYS include Skill (pipeline skill invocation).
---
```

### Field reference

| Field | Required | Notes |
|-------|----------|-------|
| `name` | Yes | kebab-case identifier |
| `description` | Yes | One-line — used by Orchestrator for agent selection |
| `model` | Yes | `opus` / `sonnet` / `haiku` |
| `tools` | Yes (subagents) | Claude Code tool names. Common sets: `Read, Grep, Glob, Skill` (read-only); add `Bash, Edit, Write` for impl roles. **Root-agent carve-out**: orchestrator omits `tools:` to inherit full harness tool surface. All other agents declare `tools:`. |

Skill tool REQUIRED for every subagent — enables explicit pipeline skill invocation (memory-read, memory-write, verdict-parse, etc.).

---

## Markdown Body

Standard role contract. Keep terse.

### Required sections

#### `# Role: Name`
One-sentence purpose statement.

#### `## Startup / Runtime Policy`
- Output style: caveman:ultra.
- Memory load via skill: `Skill(skill: "memory-read", args: "role=<agent-name>")`.
- Load run context: read `<repo>/.pipeline/runs/<artifact-id>/pipeline.md` when run exists.
- (Optional) Persistence threshold + handoff-doc skill invocation for long-running roles (architect 70%, build 80%).

#### `## Memory`
- Skill ownership: `memory-read` + `memory-write`.
- Invoke `memory-write` before completion. Memory Write Decision gate handled by skill.

#### `## Inputs`
- Required reads include: run `pipeline.md`, project `CLAUDE.md` (if present), applicable `.claude/rules/<lang>.md`, `docs/adr/**` (when present).
- Add role-specific required + conditional reads.
- Read prior verdicts via `Skill(skill: "verdict-parse", args: "run-dir=<path>, type=<type>")` for gate roles.

#### `## Do`
What the agent is authorized to do.

#### `## Don't`
What the agent must NOT do.

#### `## Outputs / Artifacts`
Artifact path + required fields. For pipeline roles, write to `<repo>/.pipeline/runs/<artifact-id>/...`. Verdict roles write `verdict-<type>-r<N>.md` w/ YAML frontmatter (verdict, role, review_type, loops, revision).

#### `## Completion / Reporting`
- Cite exact artifact paths produced.
- Invoke `memory-write` skill before return.

#### `## Skill invocation rules`
- Invoke skills by-name via `Skill` tool only (no description-match auto-load — all extracted skills set `disable-model-invocation: true`).
- `dream-apply` skill is **USER-ONLY**. New agents MUST NOT invoke it.

### Optional sections

- `## Focus` — emphasis areas (review roles)
- `## Process` — numbered methodology
- `## Verdict Schema` — for gate roles (YAML frontmatter shape)
- `## Re-review Framing` — for gate roles
- `## Frontend Handoff Policy` — when UI changes need `frontend-handoff.md`

### Speech
Output style: caveman:ultra. Inherited from global CLAUDE.md.

---

## Companion files

When creating new role:
- Create `~/.pipeline/memory/<agent-name>-memory.md` empty stub.
- (Project mirror): `<project>/.pipeline/memory/<agent-name>-memory.md` empty stub.
- Memory creation handled by `memory-read` skill on first invocation if absent.
