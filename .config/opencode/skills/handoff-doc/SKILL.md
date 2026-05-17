---
name: handoff-doc
description: Compact persistence-rotation summary template. References existing artifacts by path, never duplicates content. Used by any persistent role at context threshold (architect 70%, all other persistent roles 80%).
source: mattpocock/skills:skills/productivity/handoff/SKILL.md
output-style: caveman:ultra
---

# handoff-doc

Persistence-rotation summary template. Pipeline-internal.

## Per-role thresholds (config in role file, NOT this skill)

| Role | Threshold | task_id key |
|---|---|---|
| architect | 70% | role |
| build | 80% | (role, shard_id) |
| skeptic | 80% | (role, review_type) |
| reviewer | 80% | (role, axis) |
| security-auditor | 80% | (role, review_type) |
| tester | 80% | role |
| ui-ux-designer | 80% | role |
| content-designer | 80% | role |

One-shot roles (researcher, plan, friction-reviewer) do not rotate — they complete in a single spawn.

## Invocation

Claude: `Skill(skill: "handoff-doc", args: "role=<agent>, run-dir=<path>, next-focus=<text>")`

OC: `handoff-doc` custom tool with `{role, run_dir, next_focus}` args.

## Output path

`<run-dir>/handoff-<role>-<iso8601>.md`

## Template

```markdown
# Handoff: <role> → fresh session

**Run**: <artifact-id>
**Timestamp**: <ISO8601>

## Next session focus
<next-focus arg>

## Referenced artifacts (by path)
- pipeline: <run-dir>/pipeline.md
- brief: <run-dir>/brief.md

## State summary
Session rotated at context threshold. Resume in fresh session using task_id if supported by harness; otherwise spawn fresh + read referenced artifacts.
```
