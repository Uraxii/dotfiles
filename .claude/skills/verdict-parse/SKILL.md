---
name: verdict-parse
description: Glob verdict-<type>-r<N>.md files in pipeline run dir, pick max N, parse YAML frontmatter. Returns verdict + role + revision + loops. Use when orchestrator routes or any gate reads prior verdict.
source: pipeline-native
output-style: caveman:ultra
---

# verdict-parse

Parse pipeline gate verdicts. Pipeline-internal.

## Invocation

Claude: `Skill(skill: "verdict-parse", args: "run-dir=<path>, type=<type>")`

OC: `verdict-parse` custom tool with `{run_dir, type}` args.

Script: `python3 .claude/skills/verdict-parse/verdict-parse.py --run-dir <path> --type <type>`

## Args

| Arg | Type | Required | Description |
|-----|------|----------|-------------|
| `--run-dir` | path | yes | Pipeline run directory |
| `--type` | enum | yes | `design\|code\|ops\|review\|test-audit\|friction` |

## Returns

Single-line JSON:
```json
{
  "verdict": "Approved|Conditional|Blocked",
  "role": "<role-name>",
  "review_type": "<type>",
  "loops": "<N>",
  "revision": "r<N>",
  "prod_diff_sha": "<sha|empty>",
  "blocker_class": ["<enum>", ...],
  "path": "<abs-path-to-verdict-file>"
}
```

`blocker_class`: non-empty only when `verdict=Blocked`. Parsed from single-line
YAML flow-seq `[a, b]`. Empty list when field absent.

**Conditional verdicts MUST have ## Conditions section in body; orchestrator
verifies before proceeding.**

## Exit codes

- 0: success
- 1: run-dir not found, no verdict file, frontmatter parse failed

## See also

`revision-route`, `worktree-lifecycle`.
