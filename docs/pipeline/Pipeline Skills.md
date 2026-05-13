# Pipeline Skills

Skills are reusable procedures defined under `.claude/skills/<name>/SKILL.md`. They exist to remove duplication from agent files — algorithms like `prod_diff_sha`, verdict parsing, and worktree primitives were spelled out in multiple agents before the refactor.

Skills are invoked by name via the `Skill` tool. Every pipeline agent has `Skill` in its frontmatter `tools:` list. The orchestrator (root agent) has full tool inheritance.

## Directory layout

Claude Code discovers skills by scanning `.claude/skills/` for direct subdirectories — each subdir name is the skill name, and each contains a `SKILL.md`. Bucket-style nesting (`skills/<bucket>/<name>/`) is invalid: the harness ignores it.

```
.claude/skills/
├── README.md                              # human-facing inventory
├── agent-brief-format/SKILL.md
├── artifact-slug/SKILL.md
├── caveman/SKILL.md
├── decision-elicitation/SKILL.md
├── frontend-design/SKILL.md
├── handoff-doc/SKILL.md
├── prod-diff-sha/SKILL.md
├── test-path-resolve/SKILL.md
├── verdict-parse/SKILL.md
└── worktree-lifecycle/SKILL.md
```

## Skill frontmatter

Every SKILL.md starts with YAML:

```yaml
---
name: <invocation-name>                       # exact name used in Skill(...)
description: <auto-load trigger + use-when>
source: pipeline-native | mattpocock/skills:<path>
output-style: caveman:ultra                   # when invoked from pipeline agent
---
```

**Invocation semantics**: agent-invokable skills omit `disable-model-invocation`. Default behavior: Claude can both auto-load (description match) AND invoke via `Skill` tool. Auto-load risk is mitigated by precise `description` text — keep triggers narrow.

## Skill catalog

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
Persistence-rotation summary template. Used by any persistent role at its context threshold (architect 70%, all other persistent roles 80%). The skill writes a markdown doc that **references existing artifacts by path** rather than duplicating content. Threshold + task_id key are role config — the skill owns the template + write path only.

### `worktree-lifecycle`
Wraps `git worktree` primitives: `op=create | probe | cleanup | scope-check`. Used by orchestrator for shard management and by build for self-verify before writing evidence. See [[Pipeline Shards]].

### `agent-brief-format`
Writes the `brief.md` template at intake. Durability-over-precision contract: no file paths, no line numbers (they go stale before the agent runs). Sections: category, summary, current behavior, desired behavior, key interfaces, acceptance criteria, out-of-scope.

### `artifact-slug`
Returns the canonical artifact-id `<slug>-<hex6>`. Wraps the runtime helper at `~/.config/opencode/tools/artifact-slug.py`. Used only at intake — one slug per run.

### `test-path-resolve`
Returns the test-path glob set. Reads `<run-dir>/test-paths.txt` if the build emitted one; otherwise returns the default regex set covering Python, JS/TS, C#, Java, Kotlin, Swift, Go, Ruby, Godot, Elixir, PHP, Rust. Used by `prod-diff-sha`, skeptic test-audit, and tester smuggling scan.

### `decision-elicitation`
Orchestrator-owned decision-point flow. Elicits human pick between N options (N ≤ 4). Sync delivery via `AskUserQuestion`; async via Slack Socket Mode listener (`.claude/pipeline/slack_listener.py`, per-project systemd unit) + 10-minute `ScheduleWakeup` poll. Records pick in `decision-r<N>.md`. Triggers when brief/plan declares `decision_points:` or a role flags ambiguity. Setup: [[Pipeline Slack Setup]].

### `frontend-design`
Optional build-time aesthetics guidance for UI implementation. Distinct from `ui-ux-designer` agent — this is a stylistic helper for build, not a role.

### `caveman`
Output-style autoload. Drops articles/filler/pleasantries while preserving technical substance. Code blocks unchanged. Errors quoted verbatim.

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
- `scripts/` — utility scripts
- Examples or templates as needed

## Adding a new skill

Goes through the `progenitor` agent. Progenitor:

1. Creates `.claude/skills/<name>/SKILL.md` with required frontmatter.
2. Updates `.claude/skills/README.md` skill inventory.
3. Reports any agent files that should gain a new `Skill(...)` invocation.

The progenitor cannot self-edit.

## Related

- [[Pipeline Overview]]
- [[Pipeline Stages]] — every subagent's tool list includes Skill
- [[Pipeline Permissions]] — skill name cannot be permission-denied (audit-only defense)
