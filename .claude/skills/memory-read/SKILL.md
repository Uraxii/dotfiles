---
name: memory-read
description: Load pipeline agent memory files at startup. Reads 4 canonical paths in order (global core, global role, project core, project role). Creates missing files before reading. Use when agent spawns and needs startup context.
source: pipeline-native
output-style: caveman:ultra
---

# memory-read

Load agent memory at startup. Pipeline-internal. Invoked via Skill tool by every agent in `## Startup` step.

## Invocation

```
Skill(skill: "memory-read", args: "role=<agent-name>")
```

Required arg: `role` — name of invoking agent (e.g. `skeptic`, `build`, `orchestrator`).

## Read order (canonical)

1. `~/.pipeline/memory/core-memory.md` (global cross-cut)
2. `~/.pipeline/memory/<role>-memory.md` (global role-specific)
3. `<project>/.pipeline/memory/core-memory.md` (project cross-cut)
4. `<project>/.pipeline/memory/<role>-memory.md` (project role-specific)
5. `<repo>/.pipeline/runs/<artifact-id>/pipeline.md` IF run exists (orchestrator only)

## Creation discipline

Missing memory file: create empty stub before read. Use `mkdir -p` for parent dirs.

```bash
mkdir -p ~/.pipeline/memory
test -f ~/.pipeline/memory/<role>-memory.md || printf '' > ~/.pipeline/memory/<role>-memory.md
```

Same pattern for project mirror.

## Line caps

- core-memory.md: max 40 lines
- <role>-memory.md: max 20 lines

If file exceeds cap: prefer dream skill rotation (consolidate/reorg) over silent truncation.

## Output

Return concatenated memory content w/ source-path headers. Caller reads as context.

## Don't

- Don't fetch remote memory (skill is filesystem-only).
- Don't mutate memory during read (write path = memory-write skill).
- Don't fail loudly on missing project mirror (project may not yet have `.pipeline/`).
