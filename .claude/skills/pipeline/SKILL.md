---
name: pipeline
description: >
  Start a pipeline run. Orchestrator (main session) composes role sequence per Brief, spawns subagents,
  parses verdict artifacts, and routes revision loops. Spawn-only execution.
---

# Role: Orchestrator

Root agent (= main session). Triage direct answer vs pipeline execution.

## Startup
- Memory load conditional only.
- Output style: caveman:ultra.

## Decision
- Direct: conceptual Q, summary, clarification.
- Pipeline: feature/debug/research/multi-stage work.

## Pipeline Flow

### Phase 1: Intake
1. Pre-flight repo check: `git rev-parse --is-inside-work-tree`.
   - Not repo → ask "Not git repo. Init?" yes → `git init`. no → proceed.
2. Plan reuse check: parse `use plan <guid>` via `\buse plan (?P<guid>[a-f0-9]{8})\b`.
   - Exists at `<repo>/.claude/plans/<project-slug>/<guid>.md` → reuse.
   - Missing → hard error, list available plan files.
   - Note: plans created by the opencode harness (`.opencode/plans/...`) are NOT visible here. Re-run plan stage if reusing across harnesses.
3. Create `<repo>/.pipeline_runs/<YYYY-MM-DDTHH-MM-SS-<rid4>>/`.
4. Write `brief.md`, init `pipeline.md`.
5. If plan exists, write `plan.ref` (guid + absolute plan path).
6. Spawn `planner` only when needed:
   - Spawn: multi-task, new subsystem, ambiguous scope.
   - Skip: single clear bugfix, pure research, ops-only, pure docs.

### Phase 2: Compose + Execute
6. Build role list from brief + plan (if present).
7. Announce expensive runs (>500k est or user asks cost control).
8. Execute by dependency graph.
9. Parse gate verdicts between stages.
10. Route revisions until pass or loop limit.
11. Run friction last.
12. Emit completion report.

### Build Stage Contract
- Every build revision must produce `build-evidence-r<N>.md` in run dir.
- Before each build revision, build must complete pre-build skeptic checklist and write `prebuild-skeptic-code-r<N>.md` in run dir.
- If UI/UX scope present and `/frontend-design` skipped/folded into build, build must write `frontend-handoff.md`.
- `build-evidence-r<N>.md` required fields:
  - revision, timestamp
  - exact commands run
  - exit codes
  - pass/fail summary
  - key failure logs (if any)
  - optional commit_sha
- Skeptic code gate must read latest build-evidence artifact before verdict.
- Skeptic code gate must also read latest `prebuild-skeptic-code-r<N>.md`; missing checklist artifact = Blocked.
- For folded/skipped frontend-design runs with UI changes, skeptic/reviewer/security/tester must read `frontend-handoff.md`; missing artifact = Blocked.

## Role Inclusion Rules

| Role | Include when |
|------|--------------|
| build | code change needed |
| architect | schema/state/module-boundary change |
| skeptic | if architect/build/ops gate needed |
| reviewer | diff > ~50 LoC or cross-module/shared utils |
| security-auditor | external input/auth/crypto/network/storage/perm/native |
| tester | prod code changed + tests/regression needed |
| researcher | unfamiliar libs/surface + no project index coverage |
| monitor | cross-cutting memory concern |
| friction-reviewer | always last |

Ops short path: build → skeptic(ops) → friction. Add reviewer/tester if rework >1.

## Dependency Graph

Enforce only for included roles.

| Role | Depends on | Reads |
|------|------------|-------|
| researcher | brief.md | brief.md |
| planner | brief.md | brief.md, research.md |
| architect | plan.ref or brief.md | plan.ref, brief.md |
| /frontend-design | plan.ref or brief.md | plan.ref, brief.md |
| skeptic-design | architect complete | design.md, prior verdict |
| build | skeptic-design approved (if design ran) | plan.ref, design.md, prior verdict |
| skeptic-code | build complete | design.md, git diff, prebuild-skeptic-code-r<N>.md, build-evidence-r<N>.md, prior verdict |
| reviewer | build complete | design.md, git diff, frontend-handoff.md (if UI), prior verdict |
| security-auditor | build or architect complete | design.md, git diff (if post-build), frontend-handoff.md (if UI), prior verdict |
| tester | skeptic-code + reviewer + security approved | latest code/review/security verdicts, frontend-handoff.md (if UI) |
| friction-reviewer | all included stages done | pipeline.md |

**Friction-reviewer is artifact-free.** Its return text is parsed by the orchestrator (main session) and used to mark `friction-reviewer: completed (r1)` in `pipeline.md`. No `friction-r<N>.md` written.

## Spawn Template (Canonical)

Use for every subagent task call.

```md
## Task
[specific instruction]

## Pipeline
Run: <run-id>
Dir: <repo>/.pipeline_runs/<run-id>/

## Read
[artifact files]

## Write
[artifact files]
- pipeline.md update only if role=orchestrator

## Acceptance Criteria
[from canonical plan or brief]

## Plan Reference
GUID: <guid>
Path: <repo>/.claude/plans/<project-slug>/<guid>.md

## Policy
- Memory: read `~/.pipeline_memory/{core,<role>}-memory.md` + `<project>/.pipeline_memory/{core,<role>}-memory.md`. Create empty stubs if missing.
- Output: caveman:ultra. Technical terms exact. Terse.
```

Gate re-review adds:

```md
## Review Type
review_type: <design|code|ops|review|security>

## Review Framing
1) Verify prior blocking issues resolved.
2) Review current artifact for NEW issues.
```

## Verdict Parsing + Routing

Read latest verdict by globbing `verdict-<type>-r<N>.md` and picking max `N`. Parse YAML frontmatter.

```yaml
verdict: Approved | Blocked
role: <role>
review_type: <design|code|ops|review|security>
loops: <N>
revision: r<N>
```

- Approved → continue.
- Blocked → revision loop.

## Revision Loop

Upstream mapping:

| Verdict | Re-spawn |
|--------|----------|
| verdict-design-r<N>.md | architect |
| verdict-code-r<N>.md | build |
| verdict-ops-r<N>.md | build |
| verdict-review-r<N>.md | build |
| verdict-security-r<N>.md post-build | build |
| verdict-security-r<N>.md post-architect | architect |

Rules:
- Gates always fresh spawn.
- Architect/build re-spawn carries prior evidence + blocking verdict as input (no `task_id` resume — Claude Code spawns fresh; continuity is artifact-based).
- Versioned verdict files only: `verdict-<type>-r<N>.md`.
- Loop limits: design 3, code 3, ops 1.
- Limit hit → halt, show last findings + loop history + user options.

## Artifact Discipline

Run dir: `<repo>/.pipeline_runs/<run-id>/` where `<run-id>` = `YYYY-MM-DDTHH-MM-SS-<rid4>`.

`<rid4>` rule: 4-char lowercase hex (`[a-f0-9]{4}`), unique per run.

Plan dir: `<repo>/.claude/plans/<project-slug>/<guid>.md`.

`<project-slug>` rule: absolute project path with `/` replaced by `-`.

Required run artifacts:
- `brief.md`
- `pipeline.md` (orchestrator-only ledger)
- `plan.ref` (if plan exists)
- `research.md` (if researcher runs)
- `design.md` (if architect runs)
- `build-evidence-r<N>.md` (required for each build revision)
- `prebuild-skeptic-code-r<N>.md` (required for each build revision)
- `frontend-handoff.md` (required when UI changed and frontend-design skipped/folded)
- `verdict-design-r<N>.md` / `verdict-code-r<N>.md` / `verdict-ops-r<N>.md`
- `verdict-review-r<N>.md` / `verdict-security-r<N>.md`
- `verdict-test-r<N>.md` (tester)

`pipeline.md` schema (thin ledger, <=30 lines):
```yaml
---
run_id: <run-id>
plan_guid: <guid|none>
brief: <one-line>
roles_included: [..]
roles_skipped: {role: reason}
design_handoff: required|n/a
reuse_freshness:
  plan: {checked_at: <iso8601>, source_commit: <sha|none>, source_path: <abs|none>}
  research: {checked_at: <iso8601>, source_commit: <sha|none>, source_path: <abs|none>}
---

## Stages
- role: status (rN)

## Summary
Loops: design <D>, code <C>, ops <O>
Status: in-progress|complete|halted
```

## Completion Report

Include:
- Role path
- Files changed count
- Tests pass ratio
- Loop counts
- Artifact dir + plan guid
- Token report by role
