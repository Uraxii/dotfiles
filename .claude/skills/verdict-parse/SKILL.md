<!-- GENERATED FROM .pipeline/_shared/skills/verdict-parse/SKILL.md — DO NOT EDIT -->
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

## Verdict types (canonical 5 skeptic values + friction)

`design|code|ops|review|test-audit|friction`

## Glob pattern

`<run-dir>/verdict-<type>-r<N>.md`

Where `<N>` = integer revision. Pick file w/ max `<N>`.

## Frontmatter schema

```yaml
---
verdict: Approved | Blocked | Conditional
role: <role-name>
review_type: <design|code|ops|review|test-audit>
loops: <N>
revision: r<N>
prod_diff_sha: <sha>  # optional, pinned gates only
---
```

## Returns

JSON: `{verdict, role, review_type, loops, revision, prod_diff_sha, path}`

Non-zero exit if no file found.
