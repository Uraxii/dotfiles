<!-- GENERATED FROM .pipeline/_shared/skills/agent-brief-format/SKILL.md — DO NOT EDIT -->
---
name: agent-brief-format
description: Pipeline brief.md template. Durable-over-precise (no file paths, no line numbers). Behavioral not procedural. Complete acceptance criteria. Explicit out-of-scope. Use by orchestrator at intake.
---

# agent-brief-format

Pipeline brief.md template. Pipeline-internal. Used by orchestrator intake.

**Caller MUST provide `run-dir` and `raw-request` inline in the invocation prompt. This skill is invoked WITHOUT `args:` field; data passes via caller-provided context, NOT typed parameters.**

## Invocation

Claude: `Skill(skill: "agent-brief-format", args: "run-dir=<path>, raw-request=<user text>")`

OC: `skill({ name: "agent-brief-format" })` — caller provides `run-dir` and `raw-request` inline in calling prompt.

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
# AGENT-BRIEF

**Run**: <artifact-id>
**Brief type**: feature | bugfix | research | ops | refactor | docs
**Date**: <ISO8601>

## Request (raw)
<raw user request — verbatim>

## Interpreted request
<one-sentence behavioral description — what changes, not how>

## Scope
<what is IN scope — behavioral boundaries>

## Out of scope
<what is explicitly NOT scope — prevent gold-plating>

## Acceptance criteria
- [ ] AC1: <concrete, independently verifiable>
- [ ] AC2: ...

## Dependencies / assumptions
- <known constraints, required context>

## Open questions
- <unresolved high-impact ambiguity>
```
