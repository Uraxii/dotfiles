# Pipeline skills

Reusable procedures invoked by pipeline agents via the `Skill` tool. Files are editable directly — no generator.

| Skill | Description |
|-------|-------------|
| [verdict-parse](verdict-parse/SKILL.md) | Glob `verdict-<type>-r<N>.md`, pick max N, parse YAML frontmatter. |
| [handoff-doc](handoff-doc/SKILL.md) | Persistence-rotation summary template for persistent roles at context threshold. |
| [agent-brief-format](agent-brief-format/SKILL.md) | `brief.md` template: durable-over-precise (no file paths/line numbers). |
| [artifact-slug](artifact-slug/SKILL.md) | Resolve canonical artifact-id via runtime-aware artifact-slug tool. |
| [test-path-resolve](test-path-resolve/SKILL.md) | Canonical test-path glob set; reads optional `test-paths.txt` manifest. |
| [prod-diff-sha](prod-diff-sha/SKILL.md) | Compute SHA1 of production-code diff vs `base_sha`, excluding test paths. |
| [worktree-lifecycle](worktree-lifecycle/SKILL.md) | Pipeline shard worktree primitives: create / probe / cleanup / scope-check. |
| [decision-elicitation](decision-elicitation/SKILL.md) | Orchestrator-owned decision-point flow (sync/async, gh issue, resume). |
| [frontend-design](frontend-design/SKILL.md) | Optional build-time aesthetics guidance for UI implementation. |
| [caveman](caveman/SKILL.md) | Output-style autoload — drops articles/filler, preserves technical substance. |

## Deprecated (retained for rollback only; not invoked by pipeline)

| Skill | Status |
|-------|--------|
| [memory-read](memory-read/SKILL.md) | DEPRECATED 2026-05-13 — memory files removed from pipeline |
| [memory-write](memory-write/SKILL.md) | DEPRECATED 2026-05-13 — memory files removed from pipeline |
