---
name: pipeline-artifact-slug
description: Generate canonical pipeline artifact-id (adjective-middle-noun-hex6 slug). Used by orchestrator at intake to bind run dir + plan id. Wraps artifact-slug tool.
source: pipeline-native
output-style: caveman:ultra
---

# pipeline-artifact-slug

Generate pipeline artifact-id. Pipeline-internal.

## Invocation

Claude: `Skill(skill: "pipeline-artifact-slug", args: "seed=<int|none>")`

OC: `pipeline-artifact-slug` custom tool with `{seed?}` arg.

## Algorithm

```bash
python3 ~/.config/opencode/tools/artifact-slug.py [--seed <int>]
```

Returns: `<adjective>-<middle>-<noun>-<hex6>` on stdout.

Example: `icy-beaming-wave-d08d97`.

## Returns

Single-line slug string. Bind once; reuse for run dir + plan id everywhere in intake.

## Notes

- `secrets.token_hex(3)` → 6-char hex suffix. Collision-resistant for plan corpus.
- `--seed` deterministic for tests only. Omit in prod.
- Word lists in tool source: 32 adjectives × 16 middles × 16 nouns × 16^6 hex.
