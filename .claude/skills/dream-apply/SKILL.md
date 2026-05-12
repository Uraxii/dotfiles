---
name: dream-apply
description: USER-ONLY. Apply dream diff to memory files. Mutates memory; archives removed entries; writes apply-receipt. Never invoked by pipeline agents; agent invocation is forbidden + audited.
disable-model-invocation: true
invoke-from: user-only
source: pipeline-native
output-style: caveman:ultra
---

# dream-apply

**USER-ONLY** skill. Apply dream diff to memory files. Mutates memory.

## Permission boundary

This skill MUST NOT be invoked by any pipeline agent. Enforcement:

1. **Frontmatter**: `invoke-from: user-only`
2. **Agent body exclusion**: every pipeline agent file explicitly excludes `dream-apply` from invokable skill names
3. **Audit**: friction-reviewer Phase 4 scans run transcripts for `Skill.*dream-apply` invocations; any match → friction Blocked

Permission engine cannot enforce skill-name at allow/deny level. Defense is doctrine + audit, not permission.

## Invocation (USER only)

```
/dream-apply <diff-path>
```

Or via Skill tool when USER invokes (not from agent transcript):

```
Skill(skill: "dream-apply", args: "diff=<path>")
```

## Procedure

1. Read diff at `<path>`. Parse sections: to-merge, to-remove, to-promote, to-demote, to-tier.
2. For each affected memory file:
   a. Read current content.
   b. Apply mutations per diff blocks.
   c. Archive removed entries to `~/.pipeline/memory/.archive/<diff-iso8601>/<role>-memory-removed.md`.
   d. Write new memory file content.
3. Write apply-receipt: `~/.pipeline/dreams/<diff-iso8601>-apply-receipt.md`.
4. Mark diff as applied: rename to `<diff-iso8601>-<scope>.diff.applied.md`.

## Apply-receipt schema

```markdown
# Dream apply receipt: <iso8601>

**Diff source**: ~/.pipeline/dreams/<iso8601>-<scope>.diff.md
**Applied at**: <iso8601-apply-time>
**Files mutated**:
- ~/.pipeline/memory/<file> (N entries removed, M entries added/modified)
- (... per file)

**Archive location**: ~/.pipeline/memory/.archive/<iso8601>/

**Verification**:
- All removed entries archived (count match)
- All added entries match diff to-merge/to-promote/to-tier blocks
- No memory file exceeds line cap (core 40, role 20)
```

## Archive rotation (USER cron-configured)

Bundled setup script: `scripts/setup-archive-prune.py`. USER-invoked. Pipeline agents MUST NOT invoke.

```bash
# Default (cron, 30-day retention, 03:00 daily):
.claude/skills/dream-apply/scripts/setup-archive-prune.py

# Custom retention + time:
setup-archive-prune.py --days 60 --hour 4 --minute 30

# Systemd user timer alternative (more transparent than cron):
setup-archive-prune.py --mode systemd

# Inspect changes without applying:
setup-archive-prune.py --dry-run

# Uninstall:
setup-archive-prune.py --remove
```

Idempotent: re-runs replace prior entry. Tags entries `# dream-apply-archive-prune` so detection survives across versions.

Raw recipe (if scripting unavailable):

```bash
find ~/.pipeline/memory/.archive -mindepth 1 -maxdepth 1 -type d -mtime +30 -exec rm -rf {} \;
```

Pipeline does not auto-prune. Script is opt-in.

## Safety

- Mutations are NOT atomic across files. If apply fails mid-batch, partial mutations remain. Use git to recover (memory files under version control recommended; otherwise archive is recovery hatch).
- Verify line caps after apply. Cap exceedance = bug in diff (dream should not propose over-cap state).

## Don't

- NEVER invoked by pipeline agent.
- No diff modification (read-only on diff).
- No archive deletion (rotation = user cron only).
