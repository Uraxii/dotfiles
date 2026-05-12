# Pipeline Shards

Build runs in isolated git worktrees. A run has at least one shard (`s1`); plans can declare up to 4 shards with disjoint file scope for parallel implementation. The orchestrator owns the worktree lifecycle and the PR-publish step.

## Why shards

- **Isolation**: each shard branches from a frozen `base_sha`. Build agents cannot stomp on each other's edits.
- **Parallelism**: K disjoint shards run in parallel (single message, multiple `Agent` tool calls).
- **Targeted re-runs**: build revisions re-spawn only the `failed` shards — passing shards keep their commit chain.
- **Atomic merge**: each shard becomes its own PR. PRs land in dep-topology order with immediate auto-merge.

K=1 is the default. The orchestrator synthesizes an implicit `s1` shard covering `scope: ["."]` if the plan didn't declare one.

## Plan-side shard declaration

In the canonical plan at `~/.pipeline/plans/<slug>/<id>.md`:

```yaml
parallel_shards:
  - id: s1
    scope: [path/glob, ...]      # disjoint w/ other shards when K>=2
    tasks: [task-id, ...]        # ids from the plan's main Tasks section
    depends_on: []               # other shard ids; empty = independent
  - id: s2
    scope: [...]
    tasks: [...]
    depends_on: [s1]
```

Intake validates: K ≤ 4, pairwise scope-glob disjoint, `depends_on` refs resolvable. Failures reject the plan before any worktree is created.

Omit `parallel_shards:` for work that touches lockfiles, migrations, codegen, cross-cutting refactors, or anything where parallelism isn't worth it. Orchestrator falls back to implicit `s1`.

## Worktree lifecycle

Driven by the [[Pipeline Skills|worktree-lifecycle skill]] (`Skill(skill: "worktree-lifecycle", args: "op=...")`).

```
op=create
  Path:   <repo>/.pipeline/runs/<artifact-id>/worktrees/s<K>/
  Branch: pipeline/<artifact-id>/s<K>
  Cmd:    git worktree add <path> -b <branch> <base_sha>

op=probe
  Stale check: path exists but not in `git worktree list` → halt + surface to user. No auto-delete.

op=cleanup
  Cmd: git worktree remove <path>
  Idempotent — succeeds if already gone.

op=scope-check (build self-verify)
  CHANGED = git diff --name-only <base_sha>...HEAD
  Verify CHANGED ⊆ shard scope globs.
  Scope leak → abort shard, mark Blocked, cite leak in evidence.
```

The build self-verify is mandatory before writing `build-evidence-r<N>-s<K>.md`. The orchestrator also recomputes [[Pipeline Skills|prod-diff-sha]] after evidence write as a safety net.

## Failure semantics (fail-deferred)

When a shard exits non-zero:

1. Mark the shard `failed` in `pipeline.md` `shards:` map.
2. Sibling shards continue to natural completion.
3. Once all shards are terminal: zero failed → proceed to gates; ≥1 failed → skip gates, enter revision loop on failed shards only.

Passing shards keep their last commit. Build revisions stack new commits on the same `s<K>` branch.

Dependent shards whose `depends_on` includes a `failed` shard are marked `skipped_due_to_dep`. They get no PR and no build evidence — just a single line in `pr-report.md`.

## Tester combined-state (K ≥ 2 only)

K=1 runs tests directly in the `s1` worktree. K ≥ 2 needs a combined-state merge to catch shard interactions:

1. Pre-cleanup any dangling ref: `git update-ref -d refs/heads/pipeline/<artifact-id>/test-merge 2>/dev/null`.
2. Build temp ref by merging all approved shard branches `--no-ff` onto `base_sha`.
3. Run the full test suite against the temp merge.
4. **Merge conflict** at this step → Blocked with conflict report (shard pair + conflicting paths). Surface to user. No auto-resolve.
5. **Test failure** in combined state → attribution probe: re-run failing tests against each shard branch in isolation.
   - Exactly one shard reproduces → revision loop targets that shard.
   - Zero or multiple shards reproduce → halt + surface to user. No auto-blame.
6. Temp ref deleted after verdict written. No push.

## PR publishing (orchestrator-owned, no subagent)

After all gates Approved:

1. **Base SHA stability check**: `git rev-parse <base_ref>` must equal `base_sha` from intake. If not (base advanced during the run), abort + surface to user.
2. **Per shard**, in dep-topology order (independent first):
   1. Squash: `git reset --soft <base_sha>` + recommit. Commit message references the shard's `tasks:` ids.
   2. Push: `git push origin pipeline/<artifact-id>/s<K>`.
   3. PR: `gh pr create --base <base_ref> --head pipeline/<artifact-id>/s<K>`.
   4. **Immediate merge**: `gh pr merge <num> --squash --delete-branch`. No CI wait, no manual review pause. Capture merge commit SHA from `gh pr view --json mergeCommit`.
   5. `git fetch origin <base_ref>` between shards so dependents see prior merges.
3. **Merge failure** (`gh pr merge` non-zero): halt remaining merges, surface to user. Already-merged shards stay merged. Unmerged shards' PRs left open.
4. **Worktree cleanup** per merged shard via `worktree-lifecycle` skill.
5. Write `pr-report.md` with per-shard PR URL, PR number, merge commit SHA, status.

### PR title format

- K=1: `[<artifact-id>] <task-summary>`
- K≥2: `[<artifact-id>] <task-summary> (shard s<K>/<declared-total>)`

`<task-summary>` is the first task title in the shard's `tasks:` (fallback: shard id + scope globs). `<declared-total>` is the declared shard count including skipped ones.

## Branches-only fallback

If GitHub preconditions fail at intake (`gh` absent, `gh auth status` not clean, or remote isn't GitHub), the run continues in `github_delivery: branches-only` mode. PR publish skips the merge step; `pr-report.md` lists manual `gh pr create` + `gh pr merge` commands.

## Loop budget

Revision counter `r<N>` is global per run. Shard suffix `s<K>` is stable across revisions. Loop limit = 3 code-loop revisions (not 3 shard spawns).

Worst case (K=4, 3 code revisions): 12 build spawns + 12 gate spawns = 24 subagent invocations. With test-audit + pin invalidation cascades the upper bound is ~45.

## Related

- [[Pipeline Overview]]
- [[Pipeline Stages]] — build agent contract
- [[Pipeline Gates]] — test-only revision + pin mechanism
- [[Pipeline Skills]] — `worktree-lifecycle` and `prod-diff-sha`
