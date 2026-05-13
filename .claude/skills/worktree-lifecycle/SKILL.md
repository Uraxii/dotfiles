---
name: worktree-lifecycle
description: Pipeline shard worktree primitives — create, stale-probe, cleanup, scope-check. Wraps git worktree commands. Use by orchestrator for shard management + build for self-verify scope check.
source: pipeline-native
output-style: caveman:ultra
---

# worktree-lifecycle

Git worktree primitives for pipeline shards. Pipeline-internal.

## Invocation

Claude: `Skill(skill: "worktree-lifecycle", args: "op=<create|probe|cleanup|scope-check>, ...")`

OC: `worktree-lifecycle` custom tool with `{op, ...}` args.

## Operations

### create

Args: `op=create, run_id=<artifact-id>, shard_id=s<K>, base_sha=<sha>, repo_root=<path>`

```bash
WT_PATH=<repo>/.pipeline/runs/<run-id>/worktrees/<shard-id>/
BRANCH=pipeline/<run-id>/<shard-id>
git worktree add "$WT_PATH" -b "$BRANCH" <base-sha>
```

### probe (stale check)

Args: `op=probe, worktree_path=<path>`

```bash
if test -d <path> && ! git worktree list | grep -q <path>; then
  echo STALE  # halt; surface to user; no auto-delete
fi
```

### cleanup

Args: `op=cleanup, worktree_path=<path>`

```bash
git worktree remove --force <path>
```

### scope-check

Args: `op=scope-check, base_sha=<sha>, head=<ref>, scope_globs=<globs>`

Diffs `base_sha..head`, checks each changed file is within declared scope globs. Returns `OK` or `LEAK` with offending paths.

## Returns

JSON: `{status, ...}`. Non-zero exit on error.
