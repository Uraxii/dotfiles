<!-- GENERATED FROM .pipeline/_shared/skills/dream-apply/SKILL.md — DO NOT EDIT -->
---
name: dream-apply
description: USER-ONLY. Apply dream diff to memory files. Mutates memory; archives removed entries; writes apply-receipt. Never invoked by pipeline agents; agent invocation is forbidden + audited.
disable-model-invocation: true
source: pipeline-native
output-style: caveman:ultra
---

**USER-ONLY. Pipeline agents MUST NOT invoke this skill. Invoke via `/dream-apply` slash command only.**

This skill exists as doctrine documentation — it is present in both Claude and OpenCode skill trees for discoverability. The underlying capability takes a `diff_path` argument supplied by the `/dream-apply` slash command, NOT by skill invocation.

## Permission boundary

This skill MUST NOT be invoked by any pipeline agent. Enforcement layers:

1. **OC permission**: `permission.skill.dream-apply: deny` globally in `opencode.json`
2. **Bash ask gate**: `python3 .../dream-apply.py *` is set to `ask` — user must approve
3. **Slash command only**: invoke via `/dream-apply <diff-path>` in user session
4. **Agent body prohibition**: every pipeline agent file explicitly prohibits invocation
5. **Split by construction**: `dream-generate` (read-only) and `dream-apply` (mutating) are separate tools; no arg flip possible

## Invocation (USER only)

```
/dream-apply ~/.pipeline/dreams/<iso8601>-<scope>.diff.md
```

The slash command invokes `python3 ~/.config/opencode/tools/dream-apply.py --diff-path <path>` via bash. The bash `ask` gate presents the command to the user for approval.

## What it does

1. Read diff at path. Parse sections: to-merge, to-remove.
2. For each affected memory file: apply merge/remove operations.
3. Archive removed entries to `~/.pipeline/memory/.archive/`.
4. Write apply-receipt to `~/.pipeline/memory/.archive/apply-receipt-<iso8601>.md`.
5. Return receipt path.

## Audit

friction-reviewer Phase 4 scans run transcripts for `Skill.*dream-apply` invocations. Any match → friction Blocked.
