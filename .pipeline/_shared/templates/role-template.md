# Role Template

This template shows the canonical frontmatter + body shape for pipeline agents on both platforms.

## Claude Code frontmatter example

```yaml
---
name: <role-slug>
description: <one-line description>
model: opus|sonnet|haiku
tools: Read, Write, Edit, Grep, Glob, Bash, Skill
---
```

Notes:
- Root agents (orchestrator) OMIT `tools:` — inherits full harness surface.
- `model`: `opus` (complex reasoning), `sonnet` (balanced), `haiku` (fast/cheap).

## OpenCode frontmatter example

```yaml
---
description: <one-line description>
mode: primary|subagent|all
color: primary|secondary|accent|success|warning|error|info|#RRGGBB
model: anthropic/claude-opus-4-5|anthropic/claude-sonnet-4-5|anthropic/claude-haiku-4-5
steps: 100
permission:
  <tool-name>: allow|ask|deny
  task:
    "*": deny
    "<agent-name>": allow
---
```

Notes:
- `name:` key absent — filename is the agent name.
- `mode: primary` for orchestrator + progenitor; `mode: subagent` for all others.
- `task:` block ONLY for mode-primary agents (orchestrator, progenitor). Omit for subagents.
- `steps:` orchestrator=100, build=80, plan=60. Others: omit (use OC default).

## Required body sections

```markdown
# Role: <Role Name>

<one-paragraph purpose>

## Startup / Runtime Policy
- Output style: caveman:ultra.
- [Memory load — via snippet include]

## Memory
[Memory Write Decision — via snippet include]

## Stance
- [core stance bullets]

## Do
- [allowed actions]

## Don't
- [prohibited actions]

## Inputs
- Required reads: [list]
- Conditional reads: [list]

## Outputs / Artifacts
- [artifacts produced]

## Revision / Loop Behavior
- [how to handle gate feedback]

## Non-Goals
- [explicit non-goals]

## Completion / Reporting
- [what to report at end]

## Skill invocation rules
- `dream-apply` skill is USER-ONLY. <Role> MUST NOT invoke it.
```
