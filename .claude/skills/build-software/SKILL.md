---
name: build-software
description: Phased feature-build pipeline. Builds software as reviewable skeleton - data structures, then typed interface stubs + failing acceptance tests, then TODO-sited change points - commit + push each phase to remote branch for review before any impl written. Then impl via outside-in TDD behind invariant pass, dual-layer tests (CI regression + headless behavioral), independent challenge check. Use when user says "build-software", "build this in phases", "phased build", wants feature built in reviewable increments, or wants to steer design before logic written.
---

# build-software

Drive pipeline in main thread. Understand req → break into phases → build each as reviewable
increment user signs off before next. No finished-feature dump. Skeleton first, push each
phase, add logic only after design confirmed.

Self-contained. Own Designer/Builder/skeptic personas (bundled). Operates only on invoked
project.

## Core Responsibilities

- Analyze req, determine complexity
- Break work into sequenced phases
- Maintain full context across phases
- Build data/interface/TODO skeleton before impl
- Pass quality gates before delivery

## Roles (personas this skill defines)

| Persona | File | Phases | Use for | Exec |
|---|---|---|---|---|
| **Designer** | `designer.md` | 0-3 | req, data structures, interface contracts, TODO siting (read-only) | inline so user sees reasoning; subagent only for big read-only research |
| **Builder** | `builder.md` | 4-6 | impl, dual-layer tests, invariants, behavioral runs, deviation log | inline for small work; subagent for heavy impl |
| **skeptic** | `skeptic.md` | 4 & 6 | independent challenge check (Builder never certifies own work) | **fresh general-purpose subagent** - separate spawn + clean context = independence |

**Load a persona file only when entering its phase - don't read all upfront.**

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
Run whole pipeline in that worktree. No push.

**Phase 1 - Data structures.** Designer: types/records/schemas only, no logic.

**Phase 2 - Interfaces + failing acceptance tests.** Designer: signatures + contracts (types,
pre/postconditions, docstrings), bodies raise not-impl. Builder: a **few behavioral
acceptance tests** (outside-in, via public interface, critical-path) - the outer TDD loop =
executable spec user reviews this gate. Stays RED till phase 6. NOT shape/contract tests (no
"struct has N fields") - test behavior, not structure.

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

**Phase 6 - Real impl.** Builder: impl against confirmed skeleton + invariants via `tdd`
skill (inner loop - vertical, one test→one impl→refactor; NO horizontal slicing), driving
phase-2 acceptance tests **green** (CI regression). Run headless/UAT iface (`verify` / `run`).
Spawn skeptic = final challenge check.

## Per-phase ritual (phases 1,2,3,5,6)

1. Do phase work (Designer or Builder).
2. **Quality gate** on small diff: run `/code-review` then `/simplify`
   (correctness/readability/dead-code/over-eng). Honor project rules - discover + obey any
   `CLAUDE.md`, `AGENTS.md`, rule files, `.editorconfig`, linter/formatter config in built
   project.
3. Commit (`build(<phase>): …`) + **push branch** (`git push -u origin <branch>`).
4. **STOP.** Show diff + branch compare URL, state what to check, wait. Resume on go.

## Testing - two layers (never either/or)

1. **CI/CD regression (required):** outside-in TDD. Outer loop = few behavioral acceptance
   tests @ phase 2 (RED). Inner loop = `tdd` skill @ phase 6 (vertical unit tests). All green
   @ phase 6, CI-runnable. Proves nothing broke. Follow project test conventions.
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
- State persona switches + why
- Summarize each phase output
- Present diff + what to review every gate
- Ambiguity → ask, don't assume

## End of pipeline

Default: **stop at pushed branch** after phase-6 gate - user opens PR when ready.
`build-software --pr` → `yeet` opens **draft** PR after phase 6 for remote review. One branch,
accumulating commits. Keep each phase diff tiny. After PR/merge, clean up:
`git worktree remove ../<repo>-build-<slug>`.
