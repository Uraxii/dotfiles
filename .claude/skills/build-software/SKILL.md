---
name: build-software
description: Phased feature-build pipeline. Builds software as reviewable skeleton - data structures, then typed interface contracts, then TODO-sited change points - commit + push each phase to remote branch for review before any impl written. Then impl AND tests together at the final phase via outside-in TDD behind invariant pass, dual-layer tests (CI regression + headless behavioral), independent challenge check. Use when user says "build-software", "build this in phases", "phased build", wants feature built in reviewable increments, or wants to steer design before logic written.
---

# build-software

Drive pipeline in main thread. Understand req → break into phases → build each as reviewable
increment user signs off before next. No finished-feature dump. Skeleton first, push each
phase, add logic only after design confirmed.

Self-contained. Own Designer/Builder/skeptic agents (bundled). Operates only on invoked
project.

## Core Responsibilities

- Analyze req, determine complexity
- Break work into sequenced phases
- Maintain full context across phases
- Build data/interface/TODO skeleton before impl
- Pass quality gates before delivery

## Roles (agents this skill defines)

| Agent | File | Phases | Use for | Exec |
|---|---|---|---|---|
| **Designer** | `designer.md` | 0-3 | req, data structures, interface contracts, TODO siting (read-only) | **spawn a Designer subagent** (`designer.md`); orchestrator relays its reasoning + artifact at the gate. Inline ONLY for trivial single-line transcription. |
| **Builder** | `builder.md` | 4-6 | impl, dual-layer tests, invariants, behavioral runs, deviation log | **spawn a Builder subagent** (`builder.md`) for impl/tests/invariants. Inline ONLY for trivial single-line edits. |
| **skeptic** | `skeptic.md` | 4 & 6 | independent challenge check (Builder never certifies own work) | **fresh general-purpose subagent** - separate spawn + clean context = independence |

**Delegation is default.** Orchestrator spawns agent subagents for phase work +
relays their reasoning/diff at the gate. "Small to type" ≠ "trivial decision" —
design judgments go to the subagent even if output is a few lines.

**Trivial carve-out.** Genuinely trivial phase → orchestrator MAY self-adopt roles
inline, but MUST announce the inline path + show each role-stage labelled
(`[Designer]`→`[reviewer]`→`[skeptic]`). Can't cleanly separate stages → not
trivial, delegate.

## Core gate rule (non-negotiable)

> Advance only if feature impl-able with **existing** structs/interfaces/TODOs **without
> going anywhere else**. Else design wrong → loop back, fix skeleton, re-gate. Bad
> struct/interface/TODO never advances.

User decides phase ready. Struct wrong → stop. Interface wrong → stop. TODOs wrong → stop.
Every gate: invite **direct file edits or prose**. Never force design change through
English-only.

## Operational Protocol

**Phase 0 - Assess & Plan.** Req clear? complete? what domain expertise? Designer clarifies
objectives/scope/edge cases (via `grill-with-docs`), writes phase-1→6 plan. Discover project
quality + test conventions. Present plan, get explicit ack before code. Then create
**dedicated worktree** (default - isolates the build; main checkout stays clean; phase-4 spike
gets its own throwaway worktree off this one):
```
git worktree add ../<repo>-build-<slug> -b build/<slug>
```
Run whole pipeline in that worktree. Nothing to push until phase 1; every code phase pushes at its gate (see per-phase ritual).

**Phase 1 - Data structures.** Designer: types/records/schemas only, no logic.

**Phase 2 - Interfaces.** Designer: signatures + contracts (types, pre/postconditions,
docstrings), bodies raise not-impl. The contract is the reviewable artifact this gate - the
user steers the shape before any logic exists. NO tests this phase; tests are written at
phase 6 once the impl shape is known.

**Phase 3 - TODO markers.** Designer: `TODO` at every call/change site, exact where logic
goes. Impl path fully mapped.

**Phase 4 - spike → deviation log → DISCARD** (throwaway; NOT pushed). Precond: phase-3
committed. Builder:
- `git worktree add ../<repo>-spike-<slug> -b spike/<slug>` (separate worktree from phase-3)
- impl change + commit **in the spike worktree**
- **run software** via headless/UAT iface (`verify` / `run`), confirm behavior
- **deviation log** - every place forced to break from structs/interfaces/TODOs (each: what
  was missing + suggested design fix)

Spawn skeptic on spike diff. Present log + verdict, apply gate rule: deviations → loop to 1-3,
fix design; clean → proceed. Discard spike: `git worktree remove --force ../<repo>-spike-<slug>`
(+ `git branch -D spike/<slug>`).

**Phase 5 - Invariants.** Builder: assertions, pre/postconditions, guard clauses from phase
4. skeptic + quality gate verify these specifically.

**Phase 6 - Real impl + tests.** Builder: write the tests now (both layers below) AND impl
against the confirmed skeleton + invariants via `tdd` skill (outside-in: behavioral
acceptance test first, then inner loop - one test→one impl→refactor; NO horizontal slicing),
driving all tests **green** (CI regression). Run headless/UAT iface (`verify` / `run`).
Spawn skeptic = final challenge check.

## Per-phase ritual (phases 1,2,3,5,6)

1. Do phase work (Designer or Builder).
2. **Quality gate** on small diff: run `/code-review` then `/simplify`
   (correctness/readability/dead-code/over-eng). Honor project rules - discover + obey any
   `CLAUDE.md`, `AGENTS.md`, rule files, `.editorconfig`, linter/formatter config in built
   project.
3. **Commit + push** the phase via the `yeet` skill. Required every code phase; never gate-stop on a local-only commit.
4. **STOP.** Give a clickable review link (commit URL + branch compare URL), state what to check, wait. Resume on go.

## Testing - two layers (never either/or)

1. **CI/CD regression (required):** all tests are written at phase 6 via outside-in TDD -
   behavioral acceptance tests first, then the `tdd` skill inner loop (vertical unit tests).
   All green @ phase 6, CI-runnable. Proves nothing broke. Follow project test conventions.
2. **Headless/UAT (additive):** Builder builds driveable headless iface - behavioral runs,
   data gathering, reporting, acceptance testing. Complements layer 1, never replaces.

## Quality Gates (pass before proceeding)

- Req clarified or user-provided
- Skeleton (structs/interfaces/TODOs) confirmed at gate
- Tests green @ phase 6
- Quality gate passed each phase diff
- skeptic PASS (or non-PASS findings resolved) phases 4 & 6

## Communication Style

- Think step-by-step, explain decisions
- State agent switches + why
- Summarize each phase output
- Present diff + what to review every gate
- Ambiguity → ask, don't assume

## End of pipeline

Default: **stop at pushed branch** after phase-6 gate - user opens PR when ready.
`build-software --pr` → `yeet` opens **draft** PR after phase 6 for remote review. One branch,
accumulating commits. Keep each phase diff tiny. After PR/merge, clean up:
`git worktree remove ../<repo>-build-<slug>`.
