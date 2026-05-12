# Productivity skills

Pipeline workflow skills. Invoked by pipeline agents via Skill tool.

| Skill | Description |
|-------|-------------|
| [memory-read](memory-read/SKILL.md) | Load pipeline agent memory files at startup (4-file canonical order). |
| [memory-write](memory-write/SKILL.md) | Append rule to memory via Memory Write Decision gate. Routes CLAUDE.md candidates to proposal artifact. |
| [verdict-parse](verdict-parse/SKILL.md) | Glob `verdict-<type>-r<N>.md`, pick max N, parse YAML frontmatter. |
| [handoff-doc](handoff-doc/SKILL.md) | Compact persistence-rotation summary template; references existing artifacts by path. |
| [agent-brief-format](agent-brief-format/SKILL.md) | brief.md template: durable-over-precise (no file paths/line numbers). |
| [artifact-slug-resolve](artifact-slug-resolve/SKILL.md) | Resolve canonical artifact-id via runtime-aware artifact-slug tool. |
| [test-path-resolve](test-path-resolve/SKILL.md) | Canonical test-path regex set; reads optional test-paths.txt manifest. |
| [dream](dream/SKILL.md) | Memory curation: dedup, stale-removal, pattern-extract, signal-reorg, tier-promote. Review-mode default; writes diff only. |
| [dream-apply](dream-apply/SKILL.md) | **USER-ONLY**. Apply dream diff. Mutates memory files. Archive recovery hatch. |
