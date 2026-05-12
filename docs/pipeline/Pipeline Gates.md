# Pipeline Gates

A gate is a role that writes a verdict file. The orchestrator parses the verdict frontmatter, then either advances or re-spawns the upstream role. Gates are how the pipeline enforces quality without coupling stages to each other.

## Verdict types

| File | Written by | Reviewed thing |
|------|-----------|----------------|
| `verdict-design-r<N>.md` | `skeptic` (review_type=design) | `design.md` |
| `verdict-code-r<N>.md` | `skeptic` (review_type=code) | code + build evidence for current revision |
| `verdict-ops-r<N>.md` | `skeptic` (review_type=ops) | ops/release artifacts |
| `verdict-review-standards-r<N>.md` | `reviewer` (axis=standards) | diff vs CLAUDE.md / `.claude/rules/` / ADRs / CONTRIBUTING.md |
| `verdict-review-spec-r<N>.md` | `reviewer` (axis=spec) | diff vs brief / plan / design.md |
| `verdict-review-r<N>.md` | `orchestrator` (aggregate) | combined Standards + Spec |
| `verdict-security-r<N>.md` | `security-auditor` | design or post-build code |
| `verdict-test-r<N>.md` | `tester` | test results + adversarial probe + smuggling scan |
| `verdict-test-audit-r<N>.md` | `skeptic` (review_type=test-audit) | static audit of test design quality |
| `verdict-friction-r<N>.md` | `friction-reviewer` | doctrine adherence end-of-run |

`Approved | Blocked | Conditional` are the only values. Conditional routes identically to Blocked — the distinction exists for human readers, not for the routing engine.

## Two-axis reviewer

The orchestrator (not the reviewer itself) spawns **two reviewer subagents in a single message** so they run in parallel:

- **Standards axis** reads CLAUDE.md, `.claude/rules/<lang>.md`, `docs/adr/`, `CONTRIBUTING.md`. Reports diff violations vs documented standards. Writes `verdict-review-standards-r<N>.md`.
- **Spec axis** reads `brief.md`, canonical plan, `design.md`. Reports missing / scope-creep / wrong-impl per requirement. Writes `verdict-review-spec-r<N>.md`.

Orchestrator then aggregates into `verdict-review-r<N>.md` with `## Standards` and `## Spec` sub-sections.

**ANY axis Blocked → revision loop.** Both Approved → continue.

The split exists because code can pass one axis and fail the other:

- Code follows every standard but implements the wrong thing → Standards pass, Spec fail.
- Code does exactly what was asked but breaks conventions → Spec pass, Standards fail.

Reporting them as one mixed verdict lets one axis mask the other.

## Revision routing

Blocked or Conditional verdicts re-spawn the upstream role with the verdict findings:

| Verdict | Re-spawns |
|--------|-----------|
| `verdict-design-r<N>.md` | `architect` |
| `verdict-code-r<N>.md` | `build` |
| `verdict-ops-r<N>.md` | `build` |
| `verdict-review-r<N>.md` (ANY axis Blocked) | `build` |
| `verdict-security-r<N>.md` post-build | `build` |
| `verdict-security-r<N>.md` post-architect | `architect` |
| `verdict-test-r<N>.md` | `tester` |
| `verdict-test-audit-r<N>.md` | `build` (test-only revision; see below) |
| `verdict-friction-r<N>.md` Blocked | USER decision: fix-forward via new revision OR rollback batch |

`architect` and `build` resume the persistent session via stored `task_id`. Gates always fresh-spawn for independence.

## Loop limits

| Loop | Cap |
|------|-----|
| Design | 3 revisions |
| Code | 3 revisions |
| Ops | 1 revision |
| Test-audit retry | 1 retry per code-loop revision (max 2 test-audit verdicts per code rev) |

Hitting a limit halts the run. The orchestrator surfaces the last findings + loop history + user options. No silent loop extension.

Build revisions only re-spawn `failed` shards — passing shards keep their last commit on their `s<K>` branch.

## Test-only revision (pin mechanism)

When `skeptic-test-audit` Blocks a tester verdict, the orchestrator does NOT re-run skeptic-code, reviewer, and security-auditor. Instead:

1. Compute `prod_diff_sha` over the production-code diff (test paths excluded). See [[Pipeline Skills|prod-diff-sha skill]].
2. Pin the last-Approved `skeptic-code`, `reviewer`, `security` verdicts by storing `prod_diff_sha` in the verdict frontmatter.
3. Re-spawn `build` with `test_only: true` in the Shard block. Build's scope is restricted to test paths only; prod-path edits abort with a scope-leak block.
4. On the new build evidence, recompute `prod_diff_sha`.
5. If equal to the pinned value → pin valid; skip the pinned gates; carry the prior verdicts forward.
6. If different → pin invalidated; this counts as a new code-loop revision and the pinned gates re-fire.

The mechanism filters at the filename level only. Hunk-level prod regressions inside files listed in `test-paths.txt` are not caught — accepted hole, documented in plan §Risks.

## Friction verdict (end-of-run)

`friction-reviewer` writes `verdict-friction-r<N>.md` with:

- `verdict: Approved` — no doctrine drift; merge succeeded. Batch successful.
- `verdict: Blocked` — drift detected. Body cites specific drift findings. USER decides the rollback path (`git reset --hard <pre-batch-sha>` + reopen plan, or fix-forward via a new revision).

The friction audit checklist is in `.claude/agents/friction-reviewer.md` under `## Doctrine audit`. It scans for:

- Skill invocations fire (no inline duplication regression)
- AGENT-BRIEF template followed in `brief.md`
- Reviewer emitted both axes
- Build evidence shows red-green sequence or eco-fallback note
- Architect verdict contains `adr_emitted:` assertion
- No agent invocation of `dream-apply` (USER-only skill)
- No direct CLAUDE.md mutation
- Monitor agent file absent

## Related

- [[Pipeline Overview]]
- [[Pipeline Stages]] — role inclusion + dependency graph
- [[Pipeline Artifacts]] — full verdict schema
- [[Pipeline Skills]] — `verdict-parse` skill that the routing layer uses
