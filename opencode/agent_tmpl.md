# Agent Template

Use this file as canonical authoring template for `.config/opencode/agents/*.md`.

## Frontmatter

```yaml
---
description: <one-line role purpose>
mode: <primary|subagent|all>
color: <primary|secondary|success|warning|error|accent>
model: openai/gpt-5.3-codex
skill:
  <skill-name>: <allow>
disable: false
---
```

`permission` block optional. Prefer global `opencode.json` unless agent needs override.

## Required sections

All agent files must include every section below. If section not relevant, keep it and write `N/A`.

````md
# Role: <RoleName>

<one-paragraph mission>

## Startup / Runtime Policy
- Output style: caveman:ultra unless explicit exception.
- Read startup context in this order:
  1. `~/.pipeline/memory/core-memory.md`
  2. `~/.pipeline/memory/<role>-memory.md`
  3. `<project>/.pipeline/memory/core-memory.md`
  4. `<project>/.pipeline/memory/<role>-memory.md`
  5. `<repo>/.pipeline/runs/<artifact-id>/pipeline.md` when run exists
- Create any missing memory file before reading it.

## Memory
- Required files:
  - `~/.pipeline/memory/core-memory.md`
  - `~/.pipeline/memory/<role>-memory.md`
  - `<project>/.pipeline/memory/core-memory.md`
  - `<project>/.pipeline/memory/<role>-memory.md`
- Create missing files, then read.
- Agent may update own role memory + matching project-role memory with durable lessons only.
- Cross-cutting lessons go to core memory only via Monitor unless user explicitly requests otherwise.

## Do
- <authorized actions>

## Don't
- <hard boundaries>

## Inputs
- Required reads: <artifacts/files>
- Conditional reads: <artifacts/files or N/A>

## Outputs / Artifacts
- Write/update: <artifacts>
- Output schema: <required fields/sections>

## Revision / Loop Behavior
- <how to react to blocked/conditional verdicts>
- <loop limits or N/A>

## Non-Goals
- <explicit out-of-scope items>

## Completion / Reporting
- Record durable lessons only.
- Reference exact artifact paths written.
- If role is gate, use machine-first verdict frontmatter.
````

## Gate-role addendum

Gate roles must also include:

````md
## Review Types
- <typed review modes>

## Verdict Schema
```yaml
verdict: Approved | Blocked | Conditional
role: <role>
review_type: <design|code|ops|review|security-design|security-code|test>
loops: <N>
revision: r<N>
```

## Re-review Framing
1. Verify prior blockers/conditionals resolved.
2. Review current artifact for new issues.
3. Keep findings scoped to accepted brief/design.
````

## Shared policy notes

- `Conditional` routes same as `Blocked`.
- Loop cap for blocked/conditional verdicts: 3, then escalate to user.
- `pipeline.md` is machine-first run index + handoff summary, not optional metadata.
- No same-file parallel edits without explicit isolation support.
- Code-changing runs require tester verdict, friction report, then monitor pass.
