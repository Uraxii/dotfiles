# Engineering skills

Pipeline build/test/git mechanical skills. Invoked by pipeline agents via Skill tool.

| Skill | Description |
|-------|-------------|
| [prod-diff-sha](prod-diff-sha/SKILL.md) | Compute SHA1 of production-code diff vs base_sha, excluding test paths. Used for test-only revision pin validation. |
| [worktree-lifecycle](worktree-lifecycle/SKILL.md) | Pipeline shard worktree create/probe/cleanup primitives. |
