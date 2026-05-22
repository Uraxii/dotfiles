---
name: pipeline-agent-preflight
description: Mandatory preflight + pre-emit critique + pre-emit verification doctrine for all gate-emitting agents. Reduces revision loops by forcing self-critique + tool-augmented verification BEFORE artifact emission. Used by architect, build, skeptic-*, reviewer, security-auditor, tester, ui-ux-designer, content-designer.
version: 1.0.0
source: pipeline-native
metadata:
  hermes:
    tags: [pipeline, doctrine, gate]
---

# pipeline-agent-preflight

Three doctrine elements every gate-emitting agent applies. Pipeline-internal. Applied inline by the role-skill — NOT slash-invoked.

## When to apply

Apply ALL THREE on every `delegate_task` spawn for revisable roles:
1. **Preflight statement** — first action.
2. **Pre-emit verification** — before producing emit.
3. **Pre-emit critique** — after verification, before return.

## 1. Preflight statement (first action of spawn)

First line of your return MUST be a single-line preflight statement:

`Preflight: role=<your-role>, verdict-enum=Approved|Conditional|Blocked, doctrine-loaded-from=<your-role-skill-path>.`

Purpose: anchors loaded doctrine to current file content; defeats training-prior drift.

If loaded behavior contradicts the role-skill (e.g., you would emit a legacy enum value like "Approved with notes"), STOP and return:

`Preflight FAIL: doctrine-mismatch on <specific>; refusing spawn`

Orchestrator re-spawns or escalates.

## 2. Pre-emit verification (mandatory; tool-augmented)

For every emitted claim that is countable or pattern-checkable, run the deterministic tool BEFORE writing the claim:

| Claim | Tool |
|---|---|
| Char count of label `<L>` ≤ N | `terminal: printf '%s' "<L>" \| wc -c` |
| Line count of file `<F>` ≤ N | `terminal: wc -l <F>` |
| Regex match present in `<F>` | `terminal: grep -nE '<pattern>' <F>` |
| File exists | `terminal: test -f <F> && echo yes` |
| Schema conformance | invoke relevant `pipeline_*` plugin tool |
| Verdict revision lookup | `pipeline_verdict_parse` |

Cite tool output VERBATIM in verdict/evidence body. Do not assert countable facts without tool backing.

Example (good):
```
Drift menu option 3 label "Proceed on original base_sha":
$ printf '%s' "Proceed on original base_sha" | wc -c
28
PASS (≤30).
```

Example (bad):
```
Label is 28 chars, within ≤30 ceiling.   # no tool output cited
```

## 3. Pre-emit adversarial critique (mandatory)

Before emitting verdict/artifact, run this loop ONCE:

1. Adopt the next gate's role mentally (skeptic for architect; reviewer for build; tester for skeptic-code).
2. Re-read your own output as that role.
3. List 3 items that would be Blocking from that perspective.
4. Fix at least the 2 most-actionable. Document the 3rd as a known limitation in your Notes section.

Emit only after this loop. Skip = doctrine refusal.

## Returns

No structured return — this skill is doctrinal, applied inline by the agent. Compliance reflected in the artifact body.

## Friction-audit checks

`pipeline_friction_audit` tool verifies post-run:
- Preflight statement present in spawn return logs (orchestrator captures first line).
- Pre-emit verification: tool-output citations appear in gate verdicts for countable claims.
- Pre-emit critique: verdict body contains `## Pre-emit critique` section (3 would-block items + fixes).
