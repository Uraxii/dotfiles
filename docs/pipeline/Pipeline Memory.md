# Pipeline Memory

Each agent has a memory file that accumulates durable rules across runs. Memory is append-only during runs and curated end-of-run (or out-of-band) by the `dream` skill. Static project conventions go in CLAUDE.md, not memory.

## Memory tiers

Four files per agent role, read at startup in this order:

1. `~/.pipeline/memory/core-memory.md` — global cross-cutting
2. `~/.pipeline/memory/<role>-memory.md` — global role-specific
3. `<project>/.pipeline/memory/core-memory.md` — project cross-cutting (mirror)
4. `<project>/.pipeline/memory/<role>-memory.md` — project role-specific (mirror)

Plus the run ledger when a run is open:

5. `<repo>/.pipeline/runs/<artifact-id>/pipeline.md`

Line caps: `core-memory.md` ≤ 40 lines. Role-specific files ≤ 20 lines. Caps are enforced via `dream` curation, not silent truncation.

Loading is handled by the `memory-read` skill (`Skill(skill: "memory-read", args: "role=<agent-name>")`). Missing files are created as empty stubs before reading.

## Entry format

Every entry has the same shape:

```markdown
## <ISO8601-date> <artifact-id>
- <rule>. Why: <reason>. Apply: <when/where>.
```

Example from `~/.pipeline/memory/skeptic-memory.md`:

```
## 2026-05-12 zazzy-riding-popcorn-rev4
- Permission allow-list audits must scrape source-of-truth agent files for actual shell commands, not infer coverage from plan claims. Why: plan claims drift from real agent usage; source-of-truth scrape catches gaps. Apply: for any "expand permissions" plan, demand scrape-derived command inventory from .claude/agents/*.md + .claude/skills/*/**/SKILL.md before approving allow-list.
```

## Memory Write Decision (the gate)

At completion, every agent invokes the `memory-write` skill. The skill body decides whether to write:

**Worth writing**:
- Rule or heuristic that survived this task
- Non-obvious gotcha
- Failed approach + reason
- Surprising constraint
- Recurring pattern worth naming

**Skip silently** (no filler):
- Run-specific facts (paths, ticket IDs, this commit's diff)
- Restatements of agent spec or CLAUDE.md
- One-shot trivia

The skill enforces this contract once. Before extraction, the decision block was duplicated across all 11 agent files — drift surface gone after the skill refactor.

## Write routing (two branches)

`memory-write` skill routes based on the rule's scope:

| Scope | Destination |
|-------|-------------|
| Pipeline doctrine (e.g. "skeptic must read prebuild before evidence") | Append to memory file directly |
| Project-wide convention candidate (e.g. "this codebase always uses X over Y") | Append to memory file with tag `## <date> CLAUDE.md-candidate` PLUS write `<run>/.pipeline/runs/<artifact-id>/claudemd-proposal.md` |

**No agent writes to project CLAUDE.md directly.** USER reviews proposals + merges manually via separate commit. This is enforced by:

- Doctrine: `memory-write` skill body
- `permissions.deny` entry: `Write(CLAUDE.md)`, `Edit(CLAUDE.md)`
- Audit: friction-reviewer Phase-4 checklist

CLAUDE.md is human-curated, checked into git, treated as project-doctrine surface.

## Dream skill (curation, between sessions)

The `dream` skill performs five operations on memory:

1. **Consolidate duplicates** — merge entries restating the same rule under different artifact-ids.
2. **Remove stale entries** — drop rules superseded by later entries; drop rules tied to retired roles or deleted files.
3. **Extract patterns** — collapse N occurrences of the same fact into a single canonical entry with a source-ref list.
4. **Reorg by signal** — promote frequently-referenced rules to top of file, demote rarely-used ones.
5. **Tier-promotion** — when a rule appears in ≥3 role-memory files, promote to `core-memory.md` + remove from role memories.

**Review mode is the default.** Dream never auto-mutates memory files. It writes a diff artifact at `~/.pipeline/dreams/<iso8601>-<scope>.diff.md` listing proposed changes (unchanged-entries referenced by path only; to-merge, to-remove with `before:` excerpts, to-promote, to-demote, to-tier).

To apply the diff, USER invokes the `dream-apply` skill (separately, by name). Agents are forbidden from invoking `dream-apply` — enforced by three layers:

1. SKILL.md frontmatter `invoke-from: user-only`
2. Every agent body explicitly excludes `dream-apply` from invokable skill names
3. friction-reviewer Phase-4 audit scans transcripts for `Skill.*dream-apply` invocations — any match → friction Blocked

Permission engine cannot match on skill-name arguments, so defense is doctrine + audit, not permission rule.

## When dream fires

- **End of run** (primary): friction-reviewer invokes `dream` skill after writing its findings, **if memory was mutated during the run**. Failure is non-fatal — warns in friction report, does not block run completion.
- **Background** (optional): USER-triggered via `/loop` or cron / systemd timer for periodic cross-run pass. Scope = all pipeline memory files.

## Archive recovery hatch

`dream-apply` preserves removed entries to `~/.pipeline/memory/.archive/<iso8601>/<role>-memory-removed.md` before mutating the live memory file. 30-day retention configured via the setup script at `.claude/skills/productivity/dream-apply/scripts/setup-archive-prune.py` (cron or systemd, USER-installed).

If `dream` removes something useful, recover by reading the archive copy and re-appending manually.

## Memory-as-instruction defense

Memory entries are DATA. The `dream` skill body explicitly treats memory content as text-to-analyze, never commands-to-execute. If a memory entry contains text resembling skill-invocation patterns (e.g. `Skill(skill: "dream-apply", ...)`), the diff flags `# WARNING: potential injection in entry at line L` and does not execute the embedded text.

This is doctrine, not enforcement. The model still reads memory as text. The defense rests on the skill body's framing + the human review pass in `dream-apply`.

## Related

- [[Pipeline Overview]]
- [[Pipeline Skills]] — `memory-read`, `memory-write`, `dream`, `dream-apply`
- [[Pipeline Permissions]] — CLAUDE.md write denial + dream-apply non-invocation audit
