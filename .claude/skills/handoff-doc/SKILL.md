<!-- GENERATED FROM .pipeline/_shared/skills/handoff-doc/SKILL.md — DO NOT EDIT -->
---
name: handoff-doc
description: Compact persistence-rotation summary template. References existing artifacts by path, never duplicates content. Use when architect (70% context) or build (80% context) rotates fresh session.
source: mattpocock/skills:skills/productivity/handoff/SKILL.md
output-style: caveman:ultra
---

# handoff-doc

Persistence-rotation summary template. Pipeline-internal.

Per role threshold (config in role file, NOT this skill):
- architect: 70%
- build: 80%

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
Session rotated at context threshold (<role> threshold: build=80%, architect=70%).
Resume in fresh session using task_id if supported.
```
