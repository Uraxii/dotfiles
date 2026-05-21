---
name: test-path-resolve
description: Canonical test-path regex set. Reads optional test-paths.txt manifest in run-dir; falls back to default regex set. Use by skeptic + tester for prod-vs-test partitioning + prod-diff-sha.
source: pipeline-native
output-style: caveman:ultra
---

# test-path-resolve

Canonical test-path glob set. Pipeline-internal.

## Invocation

Claude: `Skill(skill: "test-path-resolve", args: "run-dir=<path>")`

OC: `test-path-resolve` custom tool with `{run_dir}` arg.

Script: `python3 .claude/skills/test-path-resolve/test-path-resolve.py --run-dir <path>`

## Args

| Arg | Type | Required | Description |
|-----|------|----------|-------------|
| `--run-dir` | path | yes | Pipeline run directory |

## Resolution order

1. `<run-dir>/test-paths.txt` exists → read lines; skip empty + `#`-prefixed.
2. Else → emit DEFAULT_GLOBS (21 patterns covering py/ts/js/go/java/rb/cs/gd).

## Returns

Newline-separated list of glob patterns (no JSON — shell-chain compat).

## Exit codes

- 0: success
- 1: run-dir not found

## See also

`prod-diff-sha`.
