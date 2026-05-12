---
name: verdict-parse
description: Glob verdict-<type>-r<N>.md files in pipeline run dir, pick max N, parse YAML frontmatter. Returns verdict + role + revision + loops. Use when orchestrator routes or any gate reads prior verdict.
source: pipeline-native
output-style: caveman:ultra
---

# verdict-parse

Parse pipeline gate verdicts. Pipeline-internal.

## Invocation

```
Skill(skill: "verdict-parse", args: "run-dir=<path>, type=<design|code|ops|review|security|test|test-audit|friction>")
```

## Glob pattern

```
<run-dir>/verdict-<type>-r<N>.md
```

Where `<N>` = integer revision. Pick file w/ max `<N>`.

Regex: `^verdict-<type>-r(?P<rev>\d+)\.md$`

## Frontmatter schema

```yaml
---
verdict: Approved | Blocked | Conditional
role: <role-name>
review_type: <design|code|ops|review|security|test|test-audit>
loops: <N>
revision: r<N>
prod_diff_sha: <sha>  # optional, pinned gates only
---
```

Parse + return as structured dict.

## Routing semantics (caller)

- `Approved` → continue downstream
- `Blocked` → re-spawn upstream (revision loop)
- `Conditional` → same routing as Blocked

`prod_diff_sha` (when present) used by orchestrator for pin validation on test-only revisions.

## Versioned-only

Pipeline uses ONLY versioned verdict files (`verdict-<type>-r<N>.md`). No `verdict-<type>.md` (unversioned). Skill rejects unversioned matches.

## Don't

- No write. Read-only skill.
- No verdict mutation (caller writes new revision via own write).
- No cross-run reads (scoped to single run-dir).
