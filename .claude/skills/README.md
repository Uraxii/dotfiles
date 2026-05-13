# Pipeline skills

Reusable procedures invoked by pipeline agents via the `Skill` tool. Files are editable directly — no generator.

| Skill | Description |
|-------|-------------|
| [memory-read](memory-read/SKILL.md) | Load pipeline agent memory files at startup in canonical order (global core, global role, project core, project role, run ledger). Use at agent startup before any task work. |
| [memory-write](memory-write/SKILL.md) | Memory Write Decision gate. Before completion, determines if run surfaced a lesson worth persisting. Routes pipeline doctrine to memory files, project conventions to claudemd-proposal.md. |
| [verdict-parse](verdict-parse/SKILL.md) | Glob `verdict-<type>-r<N>.md`, pick max N, parse YAML frontmatter. |
| [handoff-doc](handoff-doc/SKILL.md) | Persistence-rotation summary template; references existing artifacts by path. |
| [agent-brief-format](agent-brief-format/SKILL.md) | `brief.md` template: durable-over-precise (no file paths/line numbers). |
| [artifact-slug-resolve](artifact-slug-resolve/SKILL.md) | Resolve canonical artifact-id via runtime-aware artifact-slug tool. |
| [test-path-resolve](test-path-resolve/SKILL.md) | Canonical test-path glob set; reads optional `test-paths.txt` manifest. |
| [prod-diff-sha](prod-diff-sha/SKILL.md) | Compute SHA1 of production-code diff vs `base_sha`, excluding test paths. |
| [worktree-lifecycle](worktree-lifecycle/SKILL.md) | Pipeline shard worktree primitives: create / probe / cleanup / scope-check. |
| [dream](dream/SKILL.md) | Memory curation: dedup, stale-removal, pattern-extract, signal-reorg, tier-promote. Review-mode default. |
| [dream-apply](dream-apply/SKILL.md) | **USER-ONLY**. Apply dream diff. Mutates memory files. Archive recovery hatch. |

Only `dream-apply` blocks model invocation (`disable-model-invocation: true` + `invoke-from: user-only`). The other 12 are agent-invokable via `Skill(skill: "...")` and may auto-load on matching prompts — keep `description` text precise to avoid misfires.
