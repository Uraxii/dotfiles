---
name: prod-diff-sha
description: Compute SHA1 of production-code diff vs base_sha, excluding test paths. Used by orchestrator for test-only revision pin validation on skeptic-code/reviewer/security verdicts.
source: pipeline-native
output-style: caveman:ultra
---

# prod-diff-sha

Compute prod-code diff SHA. Pipeline-internal.

## Invocation

Claude: `Skill(skill: "prod-diff-sha", args: "base-sha=<sha>, head=<ref|HEAD>, test-paths-file=<path|none>")`

OC: `prod-diff-sha` custom tool with `{base_sha, head, test_paths_file}` args.

Script: `python3 .claude/skills/prod-diff-sha/prod-diff-sha.py --base-sha <sha> --head <ref>`

## Args

| Arg | Type | Required | Description |
|-----|------|----------|-------------|
| `--base-sha` | sha | yes | Base commit SHA |
| `--head` | ref | no | HEAD ref (default: `HEAD`) |
| `--test-paths-file` | path | no | Path to test-paths.txt override; uses DEFAULT_GLOBS if absent |

## Returns

Single 40-char hex SHA1 string (no JSON). Empty diff → `0000000000000000000000000000000000000000`.

Shell-chain pattern: `pin=$(python3 prod-diff-sha.py --base-sha $SHA --head HEAD)`

## Exit codes

- 0: success
- 1: git diff failed

## See also

`test-path-resolve`, `verdict-parse`.
