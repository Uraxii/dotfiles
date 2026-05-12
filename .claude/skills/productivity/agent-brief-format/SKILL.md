---
name: agent-brief-format
description: Pipeline brief.md template. Durable-over-precise (no file paths, no line numbers). Behavioral not procedural. Complete acceptance criteria. Explicit out-of-scope. Use by orchestrator at intake.
disable-model-invocation: true
source: mattpocock/skills:skills/engineering/triage/AGENT-BRIEF.md
output-style: caveman:ultra
---

# agent-brief-format

Pipeline brief.md template. Pipeline-internal. Used by orchestrator intake.

## Invocation

```
Skill(skill: "agent-brief-format", args: "run-dir=<path>, raw-request=<user text>")
```

Writes `<run-dir>/brief.md`.

## Principles

### Durability over precision
- DO describe interfaces, types, behavioral contracts
- DO name types/function signatures/config shapes by symbol
- DON'T reference file paths (stale)
- DON'T reference line numbers (stale)
- DON'T assume current impl structure persists

### Behavioral not procedural
- Good: "SkillConfig type should accept optional `schedule` field of type CronExpression"
- Bad: "Open src/types/skill.ts and add schedule field on line 42"

### Complete acceptance criteria
Every brief has concrete testable AC. Each independently verifiable.
- Good: `gh issue list --label needs-triage returns issues that have been through initial classification`
- Bad: "Triage should work correctly"

### Explicit scope boundaries
State what is OUT of scope. Prevents gold-plating + adjacent-feature drift.

## Template

```markdown
## Brief

**Category:** bug | enhancement | refactor | ops
**Summary:** one-line description

**Current behavior:**
What happens now. Bugs = broken behavior. Enhancements = status quo.

**Desired behavior:**
What should happen after work complete. Specific about edge cases + error conditions.

**Key interfaces:**
- `TypeName` — what changes + why
- `functionName()` return type — current vs desired
- Config shape — new options needed

**Acceptance criteria:**
- [ ] Specific testable criterion 1
- [ ] Specific testable criterion 2
- [ ] Specific testable criterion 3

**Out of scope:**
- Thing NOT changed in this issue
- Adjacent feature that's separate
```

## Don't

- No file paths.
- No line numbers.
- No vague AC ("works correctly").
- No "what to do" procedural steps.
