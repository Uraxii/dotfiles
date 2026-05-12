## Startup Memory Load

Read memory files in canonical order. Create missing files before reading.

```bash
mkdir -p ~/.pipeline/memory
test -f ~/.pipeline/memory/core-memory.md || printf '' > ~/.pipeline/memory/core-memory.md
test -f ~/.pipeline/memory/<role>-memory.md || printf '' > ~/.pipeline/memory/<role>-memory.md
```

Read in this order:
1. `~/.pipeline/memory/core-memory.md` (global cross-cut)
2. `~/.pipeline/memory/<role>-memory.md` (global role-specific)
3. `<project>/.pipeline/memory/core-memory.md` (project cross-cut; create if missing)
4. `<project>/.pipeline/memory/<role>-memory.md` (project role-specific; create if missing)
5. `<repo>/.pipeline/runs/<artifact-id>/pipeline.md` when run exists
