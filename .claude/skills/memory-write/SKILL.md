---
name: memory-write
description: Append rule to pipeline agent memory file via Memory Write Decision gate. Routes pipeline doctrine to memory file; project-wide conventions to claudemd-proposal artifact. Use when agent completes work and may have surfaced a durable lesson.
disable-model-invocation: true
source: pipeline-native
output-style: caveman:ultra
---

# memory-write

Append rule to pipeline memory. Memory Write Decision gate. Pipeline-internal.

## Invocation

```
Skill(skill: "memory-write", args: "role=<agent-name>, artifact-id=<artifact-id>, rule=<text>, reason=<text>, scope=<when/where>")
```

## Memory Write Decision (gate)

Ask: did run surface lesson future <role> run benefits from?

**Worth writing**:
- Rule/heuristic surviving this task
- Non-obvious gotcha
- Failed approach + reason
- Surprising constraint
- Recurring pattern worth naming

**Skip silently**:
- Run-specific facts (paths, ticket IDs, this commit's diff)
- Restatements of agent spec or CLAUDE.md
- One-shot trivia

If no rule worth writing: return without write. No filler.

## Write routing

Two branches based on rule scope:

1. **Pipeline doctrine** (e.g. "skeptic must read prebuild before evidence") → append to memory file
2. **Project-wide convention candidate** (e.g. "this codebase always uses X over Y") → append to memory file w/ tag `## <date> CLAUDE.md-candidate` PLUS write proposal artifact at `<run>/.pipeline/runs/<artifact-id>/claudemd-proposal.md`

**Never write to project CLAUDE.md directly.** User reviews proposals + merges manually.

## Append schema

```
## <ISO8601-date> <artifact-id>
- <rule>. Why: <reason>. Apply: <when/where>.
```

ISO8601: `date -u +%Y-%m-%dT%H:%M:%SZ`.

Target file: `~/.pipeline/memory/<role>-memory.md` (and/or project mirror at `<project>/.pipeline/memory/<role>-memory.md`).

## Line caps

If write would exceed cap (core 40, role 20), don't truncate. Surface to caller; dream skill handles consolidation.

## Don't

- No automatic CLAUDE.md edits.
- No memory writes outside `~/.pipeline/memory/` and project mirror.
- No filler entries that fail Memory Write Decision.
