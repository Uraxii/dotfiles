# Pipeline Overview

A Claude Code orchestration system that breaks software work into named stages (plan → design → build → review → test → merge), each owned by a subagent with a fixed contract. The orchestrator routes between stages based on YAML-frontmatter verdicts written to disk. Multi-stage work runs through the pipeline; one-off questions don't.

## When the pipeline runs

The orchestrator triages every user turn:

- **Direct answer** — conceptual question, summary, clarification. No pipeline.
- **Pipeline** — feature work, debugging, research, multi-stage changes.

The triage is in `.claude/agents/orchestrator.md` under `## Decision`. Triggers for pipeline mode include any prompt that implies a series of dependent decisions (plan a thing, build a thing, debug a thing).

## Entry point

The user prompts the main thread. The main thread runs as `orchestrator` (the only root agent — see [[Pipeline Stages]] for the carve-out). On pipeline mode:

1. Pre-flight: `git rev-parse --is-inside-work-tree` confirms repo context.
2. Plan-reuse check parses `use plan <slug>-<hex6>` from the prompt; loads matching plan from `~/.pipeline/plans/<project-slug>/<id>.md`.
3. Generate canonical artifact-id via the `artifact-slug` Python tool. Format: `<three-words>-<hex6>` (e.g. `zazzy-riding-popcorn-a3f29b`).
4. Create run dir `<repo>/.pipeline/runs/<artifact-id>/`. Write `brief.md` from the [[Pipeline Skills|agent-brief-format]] template. Init `pipeline.md` ledger.

After intake, the orchestrator composes the role list ([[Pipeline Stages]]) and spawns subagents in dependency order.

## What's in scope vs out

- **In**: anything that produces a code change, design artifact, research note, or test verdict tied to a tracked run.
- **Out**: ad-hoc shell tasks, single-file typo fixes (use the `caveman:cavecrew-builder` subagent), reading code (use `Explore` or `caveman:cavecrew-investigator`), general Q&A.

The pipeline is heavyweight. Don't run it for two-line patches.

## Key features

- **Worktree-isolated builds** — every build runs in `<repo>/.pipeline/runs/<id>/worktrees/s<K>/` against a snapshot of the base ref. See [[Pipeline Shards]].
- **Parallel shards** — plan can declare up to 4 disjoint-scope shards; orchestrator spawns them in parallel.
- **Gate verdicts** — every reviewer/skeptic/tester writes `verdict-<type>-r<N>.md`. Orchestrator routes on `verdict: Approved | Blocked | Conditional`. See [[Pipeline Gates]].
- **Revision loops** — Blocked verdicts re-spawn the upstream role with the new findings; loop caps prevent runaway.
- **Two-axis review** — `reviewer` runs twice in parallel: one against documented standards (CLAUDE.md, ADRs), one against the spec (brief, plan, design). Orchestrator aggregates.
- **Skill-based procedure extraction** — mechanical algorithms (verdict parsing, prod-diff SHA, worktree primitives, etc.) live in `.claude/skills/`, invoked via the `Skill` tool. See [[Pipeline Skills]].
- **Persistent revising roles** — `architect`, `build`, `skeptic`, `reviewer` (per axis), `security-auditor`, `tester`, `ui-ux-designer`, `content-designer` resume the same task_id across revisions within one loop. See [[Pipeline Stages]] § Persistence.
- **Immediate auto-merge** — gates already gated; after PR creation, the orchestrator runs `gh pr merge --squash --delete-branch` directly. No CI wait, no manual review pause.
- **Friction audit closes every run** — `friction-reviewer` runs last, audits doctrine adherence, writes `verdict-friction-r<N>.md` Approved/Blocked.

## What it doesn't do

- No environment provisioning. Pipeline assumes a working repo + a working test runner.
- No CI integration. Auto-merge bypasses GitHub Actions; gates are pipeline-internal.
- No cross-run memory. Durable lessons graduate to project doctrine (CLAUDE.md, rules, ADRs) via user edits, not automated curation.
- No retry on infrastructure failures. Network/git/gh errors surface to the user.

## Related pages

- [[Pipeline Stages]] — the role catalog + dependency graph
- [[Pipeline Artifacts]] — what gets written where during a run
- [[Pipeline Gates]] — verdict files, routing, revision loops
- [[Pipeline Shards]] — parallel worktrees + PR publishing
- [[Pipeline Skills]] — skill inventory + invocation pattern
- [[Pipeline Permissions]] — settings.json model + deny rules
