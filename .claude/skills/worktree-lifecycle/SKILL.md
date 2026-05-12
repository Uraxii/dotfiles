---
name: worktree-lifecycle
description: Pipeline shard worktree primitives — create, stale-probe, cleanup. Wraps git worktree commands. Use by orchestrator for shard management + build for self-verify scope check.
source: pipeline-native
output-style: caveman:ultra
---

# worktree-lifecycle

Git worktree primitives for pipeline shards. Pipeline-internal.

## Invocation

```
Skill(skill: "worktree-lifecycle", args: "op=<create|probe|cleanup|scope-check>, ...")
```

## Operations

### create

```
op=create, run-id=<artifact-id>, shard-id=s<K>, base-sha=<sha>, repo-root=<path>
```

```bash
WT_PATH=<repo>/.pipeline/runs/<run-id>/worktrees/<shard-id>/
BRANCH=pipeline/<run-id>/<shard-id>
git worktree add "$WT_PATH" -b "$BRANCH" <base-sha>
```

### probe (stale check)

```
op=probe, worktree-path=<path>
```

```bash
if test -d <path> && ! git worktree list | grep -q <path>; then
  echo STALE  # halt; surface to user; no auto-delete
fi
```

### cleanup

```
op=cleanup, worktree-path=<path>
```

```bash
git worktree remove <path>
```

### scope-check (build self-verify)

```
op=scope-check, base-sha=<sha>, head=<ref>, scope-globs=<glob-list>
```

```bash
CHANGED=$(git diff --name-only <base-sha>...<head>)
# Verify CHANGED ⊆ scope-globs
# Fail if any file outside declared shard scope
```

## Idempotency

- `create` fails if branch exists; caller must probe first
- `cleanup` succeeds if path already gone (idempotent)
- `probe` returns STALE | OK | ABSENT

## Don't

- No automatic stale cleanup (always surface to user).
- No branch deletion outside `git worktree remove`.
- No mutation of base ref.
