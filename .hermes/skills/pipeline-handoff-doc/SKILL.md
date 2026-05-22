---
name: pipeline-handoff-doc
description: Mandatory pre-spawn artifact for revisable roles on Hermes. Compact handoff template — references existing artifacts by path, never duplicates content. Captures prior attempts, observed failures, intermediate hypotheses, scratchpad state. Read on every revision spawn (r2, r3) so the fresh delegate_task child has continuity.
version: 1.0.0
source: mattpocock/skills:skills/productivity/handoff/SKILL.md
metadata:
  hermes:
    tags: [pipeline, persistence, mandatory]
---

# pipeline-handoff-doc

Persistence summary template. Pipeline-internal.

**Hermes context (Doctrine delta #1)**: `delegate_task` does NOT preserve subagent conversation history across spawns. Every revision r<N+1> spawn is fresh. Handoff-doc is the ONLY continuity mechanism — it MUST be written at the end of each role's spawn AND included in the next spawn's `read_paths`.

## When to write

| Role | Trigger |
|---|---|
| architect | end of every spawn (r1, r2, r3) |
| build (per shard) | end of every spawn |
| skeptic (per review_type) | end of every spawn |
| reviewer (per axis) | end of every spawn |
| security-auditor (per review_type) | end of every spawn |
| tester | end of every spawn |
| ui-ux-designer / content-designer | end of every spawn |

One-shot roles (researcher, plan) do not write handoff.

## Output path

`<run-dir>/handoff-<role>-r<N>.md` (Hermes — revision-indexed, replaces Claude Code's timestamp suffix).

For sharded roles: `handoff-build-s<K>-r<N>.md`, `handoff-skeptic-code-r<N>.md`, `handoff-skeptic-design-r<N>.md`, etc.

## Template

```markdown
---
role: <role>
revision: r<N>
shard_id: <s<K> | null>
review_type: <design | code | null>
axis: <standards | spec | null>
date: <ISO8601>
verdict_path: <path to verdict-*-r<N>.md if written>
prior_handoff: <path to handoff-<role>-r<N-1>.md if r > 1>
---

# Handoff: <role> r<N>

## What I did this spawn
<one-paragraph behavioral summary — what changed in artifacts / state>

## Hypotheses tested
- <hypothesis 1> — result: confirmed | refuted | inconclusive
- <hypothesis 2> — ...

## Failures observed
- <failure mode + root cause if known>

## Scratchpad state (essential reasoning)
<key insights, partial deductions, open threads — what an r<N+1> spawn needs
 to NOT repeat the same dead ends>

## Next-spawn focus
<one-sentence: what r<N+1> should attempt first>
```

## Lazy-read directive (M9)

Role-skills MUST instruct the child: "Open `handoff-<role>-r<N-1>.md` + `verdict-<type>-r<N-1>.md` by default. Open earlier revisions or other artifacts only on demand. Do NOT eagerly read the full Read: set." Token cost bounded.

## See also

`pipeline-verdict-parse`, `pipeline-revision-route`.
