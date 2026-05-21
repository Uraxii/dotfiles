---
name: worktree-lifecycle
description: Pipeline shard worktree primitives — create, stale-probe, cleanup, scope-check. Wraps git worktree commands. Use by orchestrator for shard management + build for self-verify scope check.
source: pipeline-native
output-style: caveman:ultra
---

# worktree-lifecycle

Git worktree primitives for pipeline shards. Pipeline-internal.

## Invocation

Claude: `Skill(skill: "worktree-lifecycle", args: "op=<op>, ...")`

OC: `worktree-lifecycle` custom tool with `{op, ...}` args.

Script: `python3 .claude/skills/worktree-lifecycle/worktree-lifecycle.py --op <op> ...`

## Args

| Arg | Type | Required | Description |
|-----|------|----------|-------------|
| `--op` | enum | yes | `create\|probe\|cleanup\|scope-check\|drift-intersect` |
| `--run-id` | str | create | Pipeline artifact-id |
| `--shard-id` | str | create | Shard id (e.g. `s1`) |
| `--base-sha` | sha | create, scope-check | Base commit SHA |
| `--repo-root` | path | create | Repo root path |
| `--worktree-path` | path | probe, cleanup | Absolute worktree path |
| `--head` | ref | scope-check | HEAD ref (default: `HEAD`) |
| `--scope-globs` | str+ | scope-check, drift-intersect | Space-separated glob list |
| `--changed-paths-file` | path | drift-intersect | File w/ one repo-relative path per line |

## Returns

Per op (JSON):

- `create`: `{worktree_path, branch}`
- `probe`: `{status: ok|missing|STALE, path}`
- `cleanup`: `{status: removed, path}`
- `scope-check`: `{status: OK|LEAK, files: [...], leaks: [...]}`
- `drift-intersect`: `{intersecting_paths: ["scope:<p>", "doctrine:<p>", ...]}`

`glob_to_regex` canonical impl (segment-walk, `**` position-dependent) lives in
`worktree-lifecycle.py`. Orchestrator Appendix cross-refs here.

## Exit codes

- 0: success
- 1: missing required arg, git failure, file not found

## See also

`verdict-parse`, `prod-diff-sha`.
