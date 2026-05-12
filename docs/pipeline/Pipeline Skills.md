# Pipeline Skills

Skills are reusable procedures defined under `.claude/skills/<name>/SKILL.md`. They exist to remove duplication from agent files — algorithms like `prod_diff_sha`, verdict parsing, and memory I/O were spelled out in multiple agents before the refactor.

Skills are invoked by name via the `Skill` tool. Every pipeline agent has `Skill` in its frontmatter `tools:` list. The orchestrator (root agent) has full tool inheritance.

## Directory layout

Claude Code discovers skills by scanning `.claude/skills/` for direct subdirectories — each subdir name is the skill name, and each contains a `SKILL.md`. Bucket-style nesting (`skills/<bucket>/<name>/`) is invalid: the harness ignores it.

```
.claude/skills/
├── README.md                              # human-facing inventory
├── agent-brief-format/SKILL.md
├── artifact-slug-resolve/SKILL.md
├── dream/
│   ├── SKILL.md
│   └── REFERENCE.md
├── dream-apply/
│   ├── SKILL.md
│   └── scripts/setup-archive-prune.py
├── handoff-doc/SKILL.md
├── memory-read/SKILL.md
├── memory-write/SKILL.md
├── prod-diff-sha/SKILL.md
├── test-path-resolve/SKILL.md
├── verdict-parse/SKILL.md
└── worktree-lifecycle/SKILL.md
```

Plus other top-level skill dirs not owned by the pipeline (caveman, frontend-design, etc.).

## Skill frontmatter

Every SKILL.md starts with YAML:

```yaml
---
name: <invocation-name>                       # exact name used in Skill(...)
description: <auto-load trigger + use-when>
disable-model-invocation: true                # pipeline skills: no description-match auto-load
source: pipeline-native | mattpocock/skills:<path>
output-style: caveman:ultra                   # when invoked from pipeline agent
---
```

`disable-model-invocation: true` is set on every pipeline skill. This prevents the model from picking the skill via description-match on user prompts. The only invocation path is explicit `Skill(skill: "...")` from agent or orchestrator bodies.

## Skill catalog

### `memory-read`
Loads pipeline agent memory at startup. Reads the 4 canonical paths in order, creates missing files as empty stubs, returns concatenated content with source-path headers. Used by every agent in its `## Startup` step.

### `memory-write`
Memory Write Decision gate + append. Routes pipeline doctrine to memory file, project-wide convention candidates to `claudemd-proposal.md`. Never writes to project CLAUDE.md directly. See [[Pipeline Memory]].

### `verdict-parse`
Globs `<run-dir>/verdict-<type>-r<N>.md`, picks max N, parses YAML frontmatter. Returns `{verdict, role, review_type, loops, revision, prod_diff_sha?}`. Used by orchestrator for routing and by every gate to read prior verdicts.

### `prod-diff-sha`
Computes SHA1 of the production-code diff between `base_sha` and `HEAD`, excluding test paths. Powers the test-only revision pin mechanism — see [[Pipeline Gates]]. Algorithm:

```bash
TEST_GLOBS=$(test -f test-paths.txt && cat test-paths.txt || skill:test-path-resolve)
EXCLUDES=$(for g in $TEST_GLOBS; do echo ":!$g"; done)
PROD_DIFF=$(git diff <base_sha> <head> -- $EXCLUDES)
sha=$(printf '%s' "$PROD_DIFF" | sha1sum | cut -c1-40)
```

`printf '%s'` strips the trailing newline; apply identically at write + validate or the SHA won't match.

Empty diff returns the sentinel `00…00` SHA (cannot collide with non-empty sha1sum output).

### `handoff-doc`
Persistence-rotation summary template. Architect rotates at 70% context; build at 80%. The skill writes a markdown doc that **references existing artifacts by path** rather than duplicating content. Suggested-skills line tells the resumed session which skills to load. Threshold value is role config — the skill only owns the template + write path.

### `worktree-lifecycle`
Wraps `git worktree` primitives: `op=create | probe | cleanup | scope-check`. Used by orchestrator for shard management and by build for self-verify before writing evidence. See [[Pipeline Shards]].

### `agent-brief-format`
Writes the `brief.md` template at intake. Durability-over-precision contract: no file paths, no line numbers (they go stale before the agent runs). Sections: category, summary, current behavior, desired behavior, key interfaces, acceptance criteria, out-of-scope. Pattern adapted from mattpocock/skills `triage/AGENT-BRIEF.md`.

### `artifact-slug-resolve`
Returns the canonical artifact-id `<slug>-<hex6>`. Wraps the runtime-aware shell helper at `~/.config/opencode/tools/artifact-slug.py` (Claude Code path; OpenCode has a custom tool). Used only at intake — one slug per run.

### `test-path-resolve`
Returns the test-path glob set. Reads `<run-dir>/test-paths.txt` if the build emitted one; otherwise returns the default regex set covering Python, JS/TS, C#, Java, Kotlin, Swift, Go, Ruby, Godot, Elixir, PHP, Rust. Used by `prod-diff-sha`, skeptic test-audit, and tester smuggling scan.

### `dream`
Memory curation — five operations (consolidate, remove stale, extract patterns, reorg by signal, tier-promote). Review-mode default; writes diff artifact only. See [[Pipeline Memory]].

### `dream-apply`
**USER-ONLY.** Reads a dream diff, mutates memory files, writes apply-receipt + archives removed entries. Three-layer enforcement against agent invocation: frontmatter `invoke-from: user-only`, agent-body skill exclusion, friction Phase-4 transcript scan.

Bundled at `.claude/skills/dream-apply/scripts/setup-archive-prune.py` is a setup helper for the 30-day archive retention cron (or systemd timer alternative).

## Invocation pattern

```
Skill(skill: "<name>", args: "<key>=<value>, <key>=<value>")
```

The args string is a comma-separated key=value list. Example:

```
Skill(skill: "verdict-parse", args: "run-dir=/repo/.pipeline/runs/zazzy-riding-popcorn-a3f29b, type=code")
```

Skill bodies parse the args string themselves; there's no formal schema validation.

## Progressive disclosure

Pattern: SKILL.md stays ≤ 100 lines. Anything more lives in companion files inside the same skill dir:

- `REFERENCE.md` — full algorithm details, schema specs, examples
- `scripts/` — utility scripts (e.g. `dream-apply/scripts/setup-archive-prune.py`)
- Examples or templates as needed

The `dream` skill body is ~70 lines pointing at `dream/REFERENCE.md` for the diff-format spec and algorithm details. Keeps SKILL.md fast to skim during agent execution.

## Adding a new skill

Goes through the `progenitor` agent. Progenitor:

1. Creates `.claude/skills/<name>/SKILL.md` with required frontmatter.
2. Updates `.claude/skills/README.md` skill inventory.
3. Reports any agent files that should gain a new `Skill(...)` invocation.

The progenitor cannot self-edit. Changes to progenitor itself (like the skills-authority expansion in Phase 0a of plan `zazzy-riding-popcorn`) require a USER manual edit.

## Related

- [[Pipeline Overview]]
- [[Pipeline Stages]] — every subagent's tool list includes Skill
- [[Pipeline Memory]] — memory-read / memory-write / dream / dream-apply
- [[Pipeline Permissions]] — skill name cannot be permission-denied (audit-only defense)
