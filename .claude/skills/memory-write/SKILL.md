---
name: memory-write
description: Memory Write Decision gate. Before completion, determines if run surfaced a lesson worth persisting. Routes pipeline doctrine to memory files, project conventions to claudemd-proposal.md. Run before every agent completion.
source: pipeline-native
output-style: caveman:ultra
---

# memory-write

Memory write gate. Run before completing.

## Invocation

Claude: `Skill(skill: "memory-write", args: "role=<role>")`

OC: `memory-write(role=<role>)`

## Procedure

## Memory Write Decision

Before completion, ask: did this run surface a lesson a future run of this role benefits from?

**Worth writing**:
- Rule/heuristic surviving this task
- Non-obvious gotcha
- Failed approach + reason
- Surprising constraint
- Recurring pattern worth naming

**Not worth writing**:
- Run-specific facts (paths, ticket IDs, this commit's diff)
- Restatements of agent spec or CLAUDE.md
- One-shot trivia

If yes → append to `~/.pipeline/memory/<role>-memory.md` (and/or project mirror):

```
## <ISO8601-date> <artifact-id>
- <rule>. Why: <reason>. Apply: <when/where>.
```

If no → skip silently. Do not write filler.

**Write routing**:
- Pipeline doctrine → memory file
- Project-wide convention candidate → write `<run-dir>/claudemd-proposal.md` (do NOT mutate CLAUDE.md directly)

