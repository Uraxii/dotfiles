# Orchestration

## Orchestrators

| Agent | Use it for |
|---|---|
| `tech-lead` | One software workstream, start to finish. Delegates, never implements. |

## Before writing code

| Agent | Use it for |
|---|---|
| `requirements-clarifier` | A vague task that needs user stories, acceptance criteria, and edge cases before anyone builds. Read-only. |
| `big-pickle-simple-tasks` | Scope that feels paralyzing, or a high-stakes operation whose step order matters. |
| `architect-designer` | Structure, pattern choice, ADRs, and the code skeleton: types, interfaces, contracts, stub bodies. Stops before implementation logic. |

Claude Code's built-in `Plan` agent has no Copilot equivalent; for a
step-by-step implementation plan, use the `search`/`read` tools directly
in the current thread. Claude's `Explore` maps to Copilot's built-in
`explore` agent (fast codebase exploration and research): delegate to it
for a broad read-only sweep across many files instead of doing the sweep
inline.

## Writing code

| Agent | Use it for |
|---|---|
| `implementation-specialist` | Scoped, file-bounded work: the default implementer on this platform. |
| `test-automation-engineer` | Writing tests, running the suite, diagnosing failures, verifying fixes. |

## Before shipping

| Agent | Use it for |
|---|---|
| `skeptic-gate` | The sole pre-ship challenge check on this platform. Read-only, spawn on architecture/trust-boundary changes, risky self-certified work, weak or suspicious verification, or before an expensive implementation runs. |

Every skeptic gate is SERIAL: spawn one `skeptic-gate`, wait for its verdict,
fix, then spawn one fresh gate. Never batch or run gates in parallel; gate
calls are a dependency chain, not independent tool calls.

## Anything else

Copilot CLI ships its own built-in agents, separate from this custom fleet:
`explore`, `task`, `general-purpose`, `rubber-duck`, `code-review`,
`research`, `security-review`. Two of those names collide with shipped
skills of the same name (`code-review`, `research`) but are a different
thing: a skill is instructions loaded into the current agent, a built-in
agent is a separate delegate. Prefer the custom fleet above for anything
it covers; `explore` is the one exception already called out above, use it
directly for a broad read-only sweep. Reach for the rest only when nothing
above fits: `general-purpose` for scoped work no specialist owns, `task`
for a generic delegated task, `rubber-duck` to think out loud,
`security-review` for an ad hoc security pass outside the skeptic-gate
pipeline.
