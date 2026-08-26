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
| `codex-runner` | Scoped work that is isolated, file-bounded, and testably done. Set ROLE: implementer, MODE: workspace-write. Bills the ChatGPT subscription instead of the Claude limit. Give concurrent runners a worktree each. |
| `implementation-specialist` | Scoped work that must stay inside the Claude context: deep in-flight state, live orchestration, Claude-only tooling. |
| `test-automation-engineer` | Writing tests, running the suite, diagnosing failures, verifying fixes. |

## Before shipping

| Agent | Use it for |
|---|---|
| `codex-runner` | The default pre-ship challenge check. Set ROLE: skeptic, MODE: read-only (default). Different vendor's model on the same diff, does not spend the Claude budget. |
| `skeptic-gate` | Escalation when `codex-runner` (skeptic role) returns anything but PASS, when the change hits architecture or a trust boundary, or when Codex is unavailable. |

Every skeptic gate is SERIAL, whether `codex-runner` (skeptic role) or `skeptic-gate`: spawn one gate, wait for its verdict, fix, then spawn one fresh gate. Never batch or run gates in parallel; gate calls are a dependency chain, not independent tool calls.

## Never spawned directly

The `impeccable` skill spawns its own fleet from inside its own workflow:
`impeccable-finish-reviewer`, `impeccable-documenter`,
`impeccable-asset-producer`, `impeccable-manual-edit-applier`. Invoke the
skill and let it delegate.

## Codex-backed agents

`codex-runner` is the one generic forwarder for any Codex-backed role
(implementer, skeptic, diagnoser, or free-form). Caller passes ROLE, the
task prompt, working directory, MODE (default READ-ONLY, write access only
if explicitly requested), and optional timeout. It runs exactly one
foreground `codex exec` call under `timeout` (default 900s) and relays the
result verbatim. No polling, no background job, no job-id store.

Every return opens with two lines:

```
JOB: <pid or "direct"> | NONE
DELEGATION: DELEGATED | NOT_DELEGATED - <what it did instead>
```

`NOT_DELEGATED` or a missing header means Codex never ran. Keep the work, do
not rerun it, and pass the flag up verbatim: it is how forwarder drift gets
diagnosed. A `NOT_DELEGATED` skeptic verdict is not an independent vendor
check, and must not be reported as one.

Non-zero exit (including 124, timeout) is a FAILURE, reported verbatim with
the tail of output. Never retried silently.

## Anything else

`general-purpose`, or `claude` when no agent name fits.
