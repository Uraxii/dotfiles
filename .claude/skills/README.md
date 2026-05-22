# Pipeline skills

Reusable procedures invoked by pipeline agents via the `Skill` tool. Files are editable directly — no generator.

| Skill | Description |
|-------|-------------|
| [pipeline-verdict-parse](pipeline-verdict-parse/SKILL.md) | Glob `verdict-<type>-r<N>.md`, pick max N, parse YAML frontmatter. |
| [pipeline-handoff-doc](pipeline-handoff-doc/SKILL.md) | Persistence-rotation summary template for persistent roles at context threshold. |
| [pipeline-agent-brief-format](pipeline-agent-brief-format/SKILL.md) | `brief.md` template: durable-over-precise (no file paths/line numbers). |
| [pipeline-artifact-slug](pipeline-artifact-slug/SKILL.md) | Resolve canonical artifact-id via runtime-aware artifact-slug tool. |
| [pipeline-test-path-resolve](pipeline-test-path-resolve/SKILL.md) | Canonical test-path glob set; reads optional `test-paths.txt` manifest. |
| [pipeline-prod-diff-sha](pipeline-prod-diff-sha/SKILL.md) | Compute SHA1 of production-code diff vs `base_sha`, excluding test paths. |
| [pipeline-worktree-lifecycle](pipeline-worktree-lifecycle/SKILL.md) | Pipeline shard worktree primitives: create / probe / cleanup / scope-check. |
| [pipeline-decision-elicitation](pipeline-decision-elicitation/SKILL.md) | Orchestrator-owned decision-point flow (sync/async, gh issue, resume). |
| [pipeline-agent-preflight](pipeline-agent-preflight/SKILL.md) | Mandatory preflight + pre-emit critique + verification doctrine for gate-emitting agents. |
| [pipeline-dep-graph-compose](pipeline-dep-graph-compose/SKILL.md) | Compose ordered role execution graph for a pipeline run. |
| [pipeline-revision-route](pipeline-revision-route/SKILL.md) | Map a verdict file to next pipeline action (respawn/approved/halt). |
| [pipeline-friction-audit](pipeline-friction-audit/SKILL.md) | Deterministic post-run audit of pipeline doctrine adherence (non-gating). |
| [caveman](caveman/SKILL.md) | Output-style autoload — drops articles/filler, preserves technical substance. |
