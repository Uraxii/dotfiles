# ADR-0006: Resume drift menu — record-and-halt, no orchestrator-driven rebase

**Status**: Accepted
**Date**: 2026-05-21 (initial) / amended r2

## Context

PR-5 introduces a base_sha drift recheck on async-decision resume. When the orchestrator wakes from a `paused_on_decision` sentinel, it re-runs `git rev-parse <base_ref>` and compares to the `base_sha` captured at intake. If the SHA changed AND the changed file set intersects shard scope OR touches a doctrine-drift halt-anywhere path, the orchestrator surfaces an `AskUserQuestion` menu with three options:

1. Rebase shard onto new base
2. Abort run + halt
3. Proceed against original base_sha

The semantics of option (1) is the open question: does the orchestrator execute `git rebase <new-base>` inside the shard worktree itself, or does it record the pick, halt the run, and require the user to drive the rebase manually before resuming?

The pause window is unbounded (async decision-elicitation timeout is 7 days). During that window, `main` may move materially. The shard worktree contains uncommitted state from in-flight build revisions in some race conditions (e.g., resume fires mid-build-handoff). Auto-rebase risks mid-pipeline merge conflicts that the orchestrator cannot resolve without escalating back to the user — defeating the point of automation.

This decision is **hard to reverse** because:

- The contract of what the menu's "Rebase" label promises is user-facing and operator-mental-model durable. Flipping later from "we record, you rebase" to "we run rebase" (or vice versa) re-trains every operator.
- Failure-recovery semantics differ materially: auto-rebase failure leaves the worktree in a conflicted half-rebased state; record-and-halt leaves the worktree in a known-clean state at the original `base_sha` until the user acts.
- Pipeline-internal state surface differs: auto-rebase must update `base_sha`, possibly invalidate cached gate verdicts, and re-validate `prod_diff_sha` pins on test-only revisions. Record-and-halt also incurs this cascade — but at user-initiated resume time, not in the middle of a running pipeline (see §Consequences "Pin-cascade on rebase-resume").

## Decision

**Record-and-halt.** When the user picks "Rebase shard onto new base":

1. Orchestrator writes the pick into `decision-r<N>.md` (or a sibling `resume-drift-r<N>.md` artifact when no formal decision-elicitation was in flight; N = max revision counter in run dir + 1).
2. Orchestrator sets the sentinel-bracketed `paused_on_drift` block in `pipeline.md` frontmatter (`# BEGIN paused_on_drift` ... `# END paused_on_drift`) with `drift_detected_at`, `stored_base_sha`, `new_base_sha`, `intersecting_paths`, and `drift_resolution_status: rebase_pending`.
3. Orchestrator emits a halt report citing the worktree path, the recommended manual rebase command (`git -C <worktree-path> rebase <new-base>` form, scoped to the worktree), and the resume sentinel to use after rebase completes.
4. Orchestrator does NOT run `git rebase` itself. It does NOT touch the shard worktree contents. It does NOT modify the shard branch.
5. User completes the rebase manually, then re-invokes the run with the resume sentinel. Orchestrator detects the new HEAD on resume, re-captures `base_sha` from the rebased branch's merge-base with `<base_ref>`, **invalidates all `prod_diff_sha`-pinned verdicts and re-spawns Standards-axis reviewer + security-code at the new `base_sha`** (see §Consequences "Pin-cascade on rebase-resume"), clears the `paused_on_drift` block via single sentinel-anchored Edit-delete, and continues.

This is consistent with the existing orchestrator stance: the orchestrator owns git read operations (`rev-parse`, `diff --name-only`) and git write operations that are pipeline-internal and bounded (branch creation, merge into `pipeline/<artifact-id>/test-merge`, `update-ref -d` cleanup). It does NOT own user-facing history-rewriting operations like rebase.

## Consequences

**Positive**:

- Worktree never enters a conflicted state under orchestrator control. Operator sees a clean halt + clear next step.
- Conflict resolution stays in the operator's own terminal w/ their own tooling. No orchestrator transcript pollution from `rebase --continue` cycles.
- Honors the global doctrine that destructive/history-rewriting operations require explicit operator confirmation; auto-rebase smuggles a rewrite into an automation flow.
- Failure mode is well-defined: user sees a merge conflict in their own terminal, resolves it, resumes when ready.

**Negative**:

- Slower recovery: user must context-switch into a terminal, run rebase, return to orchestrator. Auto-rebase would have been faster on the happy path (no conflicts).
- "Rebase shard onto new base" label is mildly misleading — the orchestrator does not actually run the rebase. Label kept because the operator's intent is "I want to rebase," and the menu records that intent; the halt report makes the manual step explicit.
- Operator must learn the resume sentinel pattern (already exists for decision-elicitation; this reuses it).
- **Pin-cascade on rebase-resume** (amended r2 per skeptic-design B5): the `base_sha` change invalidates `prod_diff_sha` pins. Specifically, `verdict-review-standards-r<N>.md` + `verdict-security-code-r<N>.md` (the two `prod_diff_sha`-pinned verdict types per orchestrator.md §Pin Validation) are invalidated. Orchestrator re-computes `prod_diff_sha` against the new `base_sha`; mismatch (essentially always, since rebase changes the diff range) → re-spawn that role at the new base. NOT invalidated: spec-axis review, security-design, skeptic-code, tester (these are not pinned; they re-run on revision regardless). Practical effect: nearly every rebase-resume re-spawns Standards-axis reviewer + security-code. This is the cost of the record-and-halt design; auto-rebase (Alternative A) would have incurred the same cascade in-flight rather than at resume time. The cost is paid here for the correctness benefit; silently reusing pins computed against the old `base_sha` would mean the merged code is reviewed against an out-of-date diff.

**Neutral**:

- Future PR may add an `--auto-rebase` opt-in flag at orchestrator startup (off by default) if operator demand emerges. The contract surface in this ADR is the safe default; the opt-in would be additive. The pin-cascade applies identically under auto-rebase, so deferring auto-rebase does not move the cascade.
- Sentinel-bracketed `paused_on_drift` block (`# BEGIN ... # END`) chosen for unambiguous Edit-delete on resolution; differs from `paused_on_decision:` (single-line flow map) because the drift block carries multiple diagnostic fields. Documented in design.md §B3.

## Alternatives considered

### A. Orchestrator auto-executes `git rebase <new-base>` inside the shard worktree

Faster on the happy path. Rejected because:

- Mid-run rebase conflicts have no resolver inside the orchestrator. Conflict → re-surface AskUserQuestion → user resolves in terminal anyway → orchestrator's `rebase --continue` orchestration adds zero value over the user just running rebase themselves.
- `base_sha` update cascades into cached verdict invalidation regardless of execution timing — the cascade is unavoidable under any approach that changes `base_sha`. Auto-rebase incurs it in the middle of a running pipeline (worse UX); record-and-halt incurs it at user-initiated resume (operator already context-switched for the rebase).
- Auto-rewriting branch history during an automation flow violates the global doctrine on destructive operations requiring operator confirmation. The menu pick is consent to the intent, not consent to a specific destructive operation.

### B. Auto-execute when intersection is empty; halt-only when intersection is non-empty

Hybrid: trust the orchestrator to rebase when nothing it cares about changed. Rejected because if the intersection is empty, the menu shouldn't fire at all — the entire AskUserQuestion is gated on non-empty intersection (per AC4). The hybrid collapses to "always halt-only when the menu fires."

### C. Auto-execute under a `--auto-rebase` startup flag (opt-in)

Forward-compatible escape hatch. Deferred. Shipping the menu first under record-and-halt establishes the safe default; the opt-in can be additive without re-architecting the menu contract. Not in PR-5 scope. Pin-cascade applies under any rebase mode.

### D. Record-pick + spawn a dedicated `rebase` subagent

Subagent with `git rebase` tooling, reads the worktree state, runs the rebase, escalates on conflict. Rejected as scope creep — adds a new agent, violates PR-5 "no new agents" constraint, and the subagent's conflict-resolution loop reduces to "ask user to resolve" anyway.

## References

- design.md §R3 — Resume base_sha drift recheck
- design.md §B5 (r2) — Rebase-resume pin re-validation
- orchestrator.md §Pin Validation — pinned verdict types
- orchestrator.md §Resume handler — base_sha drift recheck
- ADR-0005 (PR-4) — companion: skills emit plans, orchestrator executes bounded ops only
