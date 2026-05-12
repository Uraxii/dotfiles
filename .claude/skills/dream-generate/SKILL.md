<!-- GENERATED FROM .pipeline/_shared/skills/dream-generate/SKILL.md — DO NOT EDIT -->
---
name: dream-generate
description: Memory curation generator. READ-ONLY — never mutates memory files. Analyzes pipeline memory, writes diff artifact only. Used by friction-reviewer end-of-run when memory mutated.
source: pipeline-native
output-style: caveman:ultra
---

# dream-generate

Memory curation diff generator. Pipeline-internal. READ-ONLY.

This skill was split from the original `dream` skill to separate read-only analysis (dream-generate) from mutating application (dream-apply). Split-by-construction eliminates arg-flip bypass risk.

## Invocation

Claude: `Skill(skill: "dream-generate", args: "scope=<run|background>, run-id=<id|none>")`

OC: `dream-generate` custom tool with `{scope, run_id}` args. Permission: `allow` (read-only).

## Scopes

- `scope=run` — memory files mutated during current run only. Used by friction-reviewer end-of-run.
- `scope=background` — all pipeline memory files. Used by USER-triggered `/loop` or background cron.

## Five operations (analysis only — writes diff, never mutates)

1. **Consolidate duplicates** — identify entries restating same rule under different artifact-ids.
2. **Remove stale entries** — identify rules superseded by later entries; rules tied to retired roles/files.
3. **Extract patterns** — identify N occurrences of same fact across distinct artifact-ids.
4. **Reorg by signal** — identify frequently-referenced rules for promotion.
5. **Tier-promotion** — identify rules appearing across ≥3 distinct role-memory files for core promotion.

## Output

Writes diff artifact: `~/.pipeline/dreams/<iso8601>-<scope>.diff.md`.

Returns diff path. Diff is NEVER auto-applied. User runs `/dream-apply` separately.

## Security

This skill never opens any file for writing except the diff artifact under `~/.pipeline/dreams/`. Memory files are read-only from this skill's perspective.
