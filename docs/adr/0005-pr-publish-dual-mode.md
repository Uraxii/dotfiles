# ADR-0005: pr-publish skill dual-mode (plan-only default, --apply opt-in)

**Status**: Accepted
**Date**: 2026-05-21
**Run**: vivid-juggling-rivest-840dcd
**PR**: PR-4 orchestrator skill decomposition

## Context

PR-4 extracts `pr_publish` orchestrator responsibility into a standalone skill (`pr-publish`). The skill must produce a per-shard publication plan (branch names, push commands, `gh pr create` args, merge-order topology respecting `depends_on`). The orchestrator currently executes git/gh subprocesses inline (every command visible in orchestrator transcript — full audit trail).

Two responsibility-split options exist:

1. **Plan-only**: skill emits JSON describing what should happen; orchestrator executes via Bash. Subprocess error handling, retry idempotency, and audit logging all stay in the orchestrator's hands.
2. **`--apply`**: skill executes subprocesses internally and emits JSONL action-result log. Orchestrator becomes a thin invocation site; skill owns the subprocess surface.

Plan-only matches current orchestrator audit pattern. `--apply` reduces orchestrator Bash glue and improves replayability of the publication step in isolation.

This decision is **hard to reverse** because:
- Subprocess error handling is allocated to whichever side owns execution (orchestrator or skill).
- Idempotency surface (what happens on retry after partial failure) lives with the executor.
- Audit-trail location (transcript vs JSONL) cascades into operator mental models and friction-audit checks.
- Test surface for the skill differs materially: plan-only is a pure function; `--apply` requires subprocess mocking.

Reversing later means re-routing all three concerns and re-training operator expectations.

## Decision

Ship the skill in **dual-mode**:

- **Default**: plan-only. Skill emits a JSON publication plan (locked schema in design.md R5). No subprocess side effects beyond the read-only `gh` availability probe.
- **`--apply` flag**: opt-in. Skill executes `git push`, `gh pr create`, `gh pr merge` subprocesses; emits JSONL action-result log to stdout; final summary line always emitted.

**PR-4 orchestrator wiring uses plan-only.** `--apply` is implemented in the script and exercised by smoke tests, but is **not invoked by the orchestrator** in this PR. Orchestrator continues to execute git/gh via Bash using the `commands` field of the plan-only JSON (preserves current audit trail).

`--apply` is a forward-compatible knob. Future PRs (PR-6+) may flip the orchestrator to `--apply` after subprocess error handling and idempotency surface inside the skill mature.

## Consequences

**Positive**:
- Audit trail unchanged for PR-4 (orchestrator transcript still shows every git/gh invocation).
- Skill is replayable in isolation today via plan-only mode (deterministic JSON output given pipeline.md input).
- Forward-compatible: future PR can opt into `--apply` without re-architecting the skill or the orchestrator.
- Test surface clear: plan-only is a pure function (easy to test); `--apply` smoke test mocks subprocess behavior.

**Negative**:
- Skill ships with two code paths from day one; `--apply` is dead code in PR-4 orchestrator wiring. YAGNI risk: if `--apply` is never adopted, the second code path is maintenance overhead.
- Two output schemas (JSON plan vs JSONL action log) increase contract surface; consumers must branch on mode.
- Smoke test must exercise both modes (more test cases per skill).

**Neutral**:
- Subprocess error handling lives in the orchestrator's Bash for PR-4. When `--apply` is adopted, error handling moves to the skill — operators must learn the new error-surface location.

## Alternatives considered

### A. Plan-only, no --apply

Simpler skill (one code path). Forces orchestrator to retain all subprocess Bash forever. Rejected because the long-term goal of orchestrator-as-conductor argues for eventual `--apply` adoption, and shipping the flag latently is cheap (one extra code path) while back-fitting it later is a contract change.

### B. --apply only, drop plan-only

Smaller contract surface. Forces orchestrator to give up audit-trail authority in PR-4. Rejected because the audit pattern (every command in orchestrator transcript) is operator-facing doctrine; changing it within a refactor PR muddles the diff and risks operator surprise. Friction-audit's `skill-invocation` check would not catch a regression here.

### C. Plan-only with optional --execute callback

Skill emits plan + accepts a follow-up `--execute <plan-file>` invocation. Two-step protocol. Rejected as more complex than dual-mode (state passed through a file on disk; orchestrator must manage the intermediate artifact). Dual-mode collapses the two steps into one optional flag.

### D. Plan-only with shared library for subprocess execution

Skill emits plan; a separate `pr-publish-execute` skill consumes the plan and runs subprocesses. Splits the contract across two skills. Rejected because the skill surface area doubles and the protocol between them becomes another design point. Dual-mode keeps one skill name.

## References

- design.md (PR-4) §R2 — decision rationale
- design.md (PR-4) §R5 — locked output schema for plan-only mode
- brief.md (PR-4) §Open questions Q2
- plan.md (PR-4) §Scope risks R2
