# Orchestration

## Orchestrators

| Agent | Use it for |
|---|---|
| `zakia` | Main thread. Triage, sequencing, cross-workstream synthesis, and every question that reaches the user. |
| `tech-lead` | One software workstream, start to finish. Delegates, never implements. |
| `art-director` | One image generation or editing workstream. Never loads image pixels into its own context. |

## Before writing code

| Agent | Use it for |
|---|---|
| `requirements-clarifier` | A vague task that needs user stories, acceptance criteria, and edge cases before anyone builds. Read-only. |
| `big-pickle-simple-tasks` | Scope that feels paralyzing, or a high-stakes operation whose step order matters. |
| `architect-designer` | Structure, pattern choice, ADRs, and the code skeleton: types, interfaces, contracts, stub bodies. Stops before implementation logic. |
| `Plan` | A step-by-step implementation plan and the critical files for it. |
| `Explore` | Broad read-only search when the answer means sweeping many files and you want the conclusion, not the dumps. |

## Writing code

| Agent | Use it for |
|---|---|
| `implementation-specialist` | Scoped, well-defined implementation work. |
| `test-automation-engineer` | Writing tests, running the suite, diagnosing failures, verifying fixes. |

## Before shipping

| Agent | Use it for |
|---|---|
| `skeptic-gate` | The pre-ship challenge check, before any PR opened/integrated. |

Every skeptic gate is SERIAL: spawn one gate, wait for its verdict, fix, then spawn one fresh gate. Never batch or run gates in parallel; gate calls are a dependency chain, not independent tool calls.

## Never spawned directly

The `impeccable` skill spawns its own fleet from inside its own workflow:
`impeccable-finish-reviewer`, `impeccable-documenter`,
`impeccable-asset-producer`, `impeccable-manual-edit-applier`. Invoke the
skill and let it delegate.

## Anything else

`general-purpose`, or `claude` when no agent name fits.
