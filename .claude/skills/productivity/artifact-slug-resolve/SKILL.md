---
name: artifact-slug-resolve
description: Resolve canonical artifact-id via runtime-aware artifact-slug tool. Returns slug-hex6 identifier for plan + run dirs. Use by orchestrator at intake.
disable-model-invocation: true
source: pipeline-native
output-style: caveman:ultra
---

# artifact-slug-resolve

Canonical artifact-id resolution. Pipeline-internal. Used at intake only.

## Invocation

```
Skill(skill: "artifact-slug-resolve")
```

No args. Returns: `<slug>-<hex6>` string.

## Runtime branch

- **OpenCode**: call `artifact-slug` custom tool.
- **Claude Code**: invoke `python3 ~/.config/opencode/tools/artifact-slug.py` via Bash.
- **OpenCode fallback**: if custom tool unavailable, use Bash helper.

Detection: if Claude Code harness, no `artifact-slug` tool exists; use python3 invocation directly.

## Scope rule

- ONLY for canonical plan/run IDs.
- NOT for timestamps, freshness checks, unrelated naming, filenames other than canonical artifact IDs.

## Binding

Caller must:
1. Bind returned value as `artifact-id`
2. Use exact value for run dir: `<repo>/.pipeline/runs/<artifact-id>/`
3. Use exact value for plan: `~/.pipeline/plans/<project-slug>/<artifact-id>.md`
4. Reuse same value everywhere in intake for current run
5. No second invocation during same intake unless user requests new run

## Format

`<slug>-<hex6>` — e.g. `zazzy-riding-popcorn-a3f29b`.

## Don't

- No re-invocation per phase (intake only).
- No timestamps embedded in slug.
- No filename derivation for non-canonical artifacts.
