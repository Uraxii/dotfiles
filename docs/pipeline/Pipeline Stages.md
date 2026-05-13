# Pipeline Stages

Each stage is a subagent defined in `.claude/agents/<name>.md`. The orchestrator picks which stages to include for a given run from the inclusion rules below, then spawns them in dependency order.

## Role catalog

| Role | Model | What it does | Owns artifact |
|------|-------|--------------|---------------|
| `orchestrator` | opus | Root agent. Triages, intakes, spawns, routes verdicts, aggregates two-axis review, opens + merges PRs. | `pipeline.md`, `plan.ref`, `pr-report.md` |
| `researcher` | opus | Domain facts before plan/design. APIs, feasibility, external systems. | `research.md` |
| `content-designer` | opus | Pre-plan ideation. Feature pitches, content drafts, decision options. | `ideation.md` |
| `plan` | opus | Brief → numbered tasks + scope + optional shard partition. | Canonical plan at `~/.pipeline/plans/<slug>/<id>.md` + `plan.ref` |
| `architect` | opus | System design + ADR emission on irreversible decisions. | `design.md` + ADRs at `docs/adr/<N>-<topic>.md` |
| `ui-ux-designer` | sonnet | UI structure, interaction, visual direction. Writes the handoff for UI scope. | `frontend-handoff.md` |
| `build` | sonnet | Implementation in a worktree shard. TDD when test runner supports it; eco-fallback otherwise. | `build-evidence-r<N>-s<K>.md`, `prebuild-skeptic-code-r<N>-s<K>.md`, code + tests |
| `skeptic` | opus | Gatekeeper for design/code/ops/review/test-audit. Adversarial. | `verdict-<type>-r<N>.md` |
| `reviewer` | haiku | Two-axis review: Standards + Spec. Spawned twice in parallel by orchestrator. | `verdict-review-<axis>-r<N>.md` |
| `security-auditor` | opus | Vulns, threat modeling, dep checks. Design + post-build phases. | `verdict-security-r<N>.md` |
| `tester` | sonnet | Runs tests + adversarial probe + smuggling scan. Combined-state merge test on K≥2 shards. | `verdict-test-r<N>.md` |
| `decision-elicitation` | n/a (orchestrator-owned) | Elicits human pick between N options (N ≤ 4). Sync via AskUserQuestion or async via GH issue + 10min poll. See [[Pipeline Decisions]]. | `decision-r<N>.md`, `awaiting-decision-r<N>.md` (transient) |
| `friction-reviewer` | haiku | Runs last on code-changing runs. Audits doctrine. Invokes [[Pipeline Memory\|dream]] skill on memory mutation. | `friction-report-r<N>.md`, `verdict-friction-r<N>.md` |
| `progenitor` | haiku | Meta-agent. Creates / modifies / retires agent roles + skills. Cannot self-edit. | `.claude/agents/*.md`, `.claude/skills/**/SKILL.md` |

`monitor` was retired — its memory-curation duties moved to the `dream` skill. See [[Pipeline Memory]].

## Root-agent carve-out

The `orchestrator` runs as the main Claude Code thread, not as a spawned subagent. Its frontmatter omits the `tools:` field so it inherits the full harness tool surface (Bash, Edit, Write, Read, Agent, Skill, ToolSearch, ScheduleWakeup, deferred tools). All other agents are subagents and MUST declare `tools:`.

This is documented in `.claude/agents/progenitor.md` under `## Do` ("Root-agent carve-out").

## Inclusion rules

| Role | Include when |
|------|--------------|
| `build` | code change needed |
| `architect` | schema, state, or module-boundary change |
| `ui-ux-designer` | UI/UX scope in brief |
| `skeptic` | any architect / build / ops gate runs |
| `reviewer` | diff > ~50 LoC or cross-module / shared utils |
| `security-auditor` | external input, auth, crypto, network, storage, perm, native code |
| `tester` | prod code changed + tests or regression needed |
| `researcher` | unfamiliar lib or surface + no project index coverage |
| `decision-elicitation` | brief or plan declares `decision_points:` block |
| `friction-reviewer` | always last on code-changing runs |

Ops short path (no design, no test): `build → skeptic(ops) → friction-reviewer`. Add reviewer or tester if more than one rework cycle.

## Dependency graph

```
researcher ──► plan ──► architect ──► skeptic-design
                                       │
                                       ▼
ui-ux-designer ──────────────────► build (per shard)
                                       │
                                       ▼
                                  skeptic-code + reviewer×2 + security-auditor
                                       │
                                       ▼
                                     tester
                                       │
                                       ▼
                                   pr_publish (orchestrator)
                                       │
                                       ▼
                                friction-reviewer
                                       │
                                       ▼
                              dream skill (if memory mutated)
```

Build runs in worktrees; gates read the union of per-shard diffs. See [[Pipeline Shards]].

## Spawn template

Every subagent spawn uses the canonical template (in `.claude/agents/orchestrator.md` under `## Spawn Template`):

```md
## Task
[specific instruction]

## Pipeline
Run: <artifact-id>
Dir: <repo>/.pipeline/runs/<artifact-id>/

## Read
[artifact files] + project CLAUDE.md + applicable .claude/rules/<lang>.md + docs/adr/

## Write
[artifact files]

## Acceptance Criteria
[from canonical plan or brief]

## Plan Reference
ID: <artifact-id>
Path: ~/.pipeline/plans/<project-slug>/<artifact-id>.md
```

Build spawns also include a `## Shard` block — see [[Pipeline Shards]].

## Persistence (long-running roles)

`architect` and `build` are persistent across revisions via `task_id` resume. They hit a context threshold (70% architect, 80% build) and invoke the [[Pipeline Skills|handoff-doc]] skill to write a rotation summary. The orchestrator records the old + new `task_id` in `pipeline.md`.

Gates (`skeptic`, `reviewer`, `security-auditor`, `tester`) always fresh-spawn — no persistence. This is by design: independent review per revision.

## Related

- [[Pipeline Overview]]
- [[Pipeline Gates]] — how the verdict files drive routing
- [[Pipeline Artifacts]] — full file layout per stage
