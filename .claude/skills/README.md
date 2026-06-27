# Claude Code skills

User-level skills loaded by Claude Code from `~/.claude/skills/`. Each skill is a directory with a `SKILL.md` (frontmatter + body) plus optional bundled resources.

Tree maintained as the Claude Code source of truth. Hermes-equivalent skills live under `.hermes/skills/` with omerxx-style frontmatter; opencode versions under `opencode/skills/`. Edit files directly — no generator.

## Skills

| Skill | Description |
|-------|-------------|
| [caveman](caveman/SKILL.md) | Terse smart-caveman output style; pin via memory for persistent activation. |
| [handoff](handoff/SKILL.md) | Compact the current conversation into a durable handoff doc in `$TMPDIR` for another session. |
| [diagnose](diagnose/SKILL.md) | Disciplined diagnosis loop for hard bugs / perf regressions. |
| [tdd](tdd/SKILL.md) | Red-green-refactor TDD loop. |
| [prototype](prototype/SKILL.md) | Throwaway prototype to flesh out a design before committing to it. |
| [triage](triage/SKILL.md) | State-machine-driven issue triage. |
| [yeet](yeet/SKILL.md) | Stage + commit + push + open PR in one flow. |
| [grill-with-docs](grill-with-docs/SKILL.md) | Stress-test a plan against project domain language + ADRs. |
| [improve-codebase-architecture](improve-codebase-architecture/SKILL.md) | Find deepening / refactor opportunities. |
| [write-a-skill](write-a-skill/SKILL.md) | Author new skills with proper structure. |
| [artifact-serve](artifact-serve/SKILL.md) | Serve generated artifacts over HTTP / Tailscale + collect feedback. |
| [zoom-out](zoom-out/SKILL.md) | Broader-context recap for unfamiliar code. |
