---
name: handoff-doc
description: Compact persistence-rotation summary template. References existing artifacts by path, never duplicates content. Use when architect (70% context) or build (80% context) rotates fresh session.
disable-model-invocation: true
source: mattpocock/skills:skills/productivity/handoff/SKILL.md
output-style: caveman:ultra
---

# handoff-doc

Persistence-rotation summary template. Pipeline-internal.

Per role threshold (config in role file, NOT this skill):
- architect: 70%
- build: 80%

## Invocation

```
Skill(skill: "handoff-doc", args: "role=<agent>, run-dir=<path>, next-focus=<text>")
```

## Output path

`<run-dir>/handoff-<role>-<iso8601>.md` via `mktemp` parent.

## Template

```markdown
# Handoff: <role> → fresh session

**Run**: <artifact-id>
**From task_id**: <old>
**To task_id**: <new>
**Timestamp**: <ISO8601>

## Next session focus
<next-focus arg>

## Referenced artifacts (by path)
- brief: <run-dir>/brief.md
- plan: <plan.ref path>
- design: <run-dir>/design.md  (if architect ran)
- verdicts: <run-dir>/verdict-*-r*.md  (latest)
- evidence: <run-dir>/build-evidence-r<N>-s<K>.md  (per shard)

## Suggested skills for next session
- <e.g. memory-read, verdict-parse, prod-diff-sha>

## State recap (concise)
<one-paragraph: current revision, gates passed/blocked, open issues>
```

## Rules

- **Reference artifacts by path; do NOT duplicate content.** Pipeline runs already have artifacts on disk. Handoff doc points fresh session at them.
- Keep state recap concise. Verbose recaps duplicate verdict files.
- Threshold value (70%/80%) belongs to role config, not this skill.

## Don't

- No content duplication. References only.
- No threshold logic (role decides when to rotate).
- No mid-session writes (rotation = end-of-session).
