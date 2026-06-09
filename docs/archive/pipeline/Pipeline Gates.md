# Pipeline Gates

A gate emits a verdict through `record-verdict`. The tool validates schema, writes findings to the SQLite Ledger, and writes the markdown verdict artifact. The orchestrator routes from ledger/findings first; prose is optional/compressed.

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


`Approved | Blocked | Conditional` are the only values. `findings:` is canonical. Conditional routes identically to Blocked unless the orchestrator can verify all listed conditions.

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

Blocked or Conditional verdicts re-spawn the upstream role with the structured verdict findings, not full prior artifacts:

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


All revising roles resume their persistent session via stored `task_id` within a single revision loop:
- `architect`, `build` (per shard), `tester`, `ui-ux-designer`, `content-designer` — one task_id per role.
- `skeptic` — task_id keyed by `review_type` (skeptic-design and skeptic-code are distinct persistent instances).
- `reviewer` — task_id keyed by `axis` (Standards and Spec are distinct persistent instances).
- `security-auditor` — task_id keyed by `review_type` (security-design and security-code are distinct persistent instances).

Cross-stage spawns are always fresh. One-shot roles (`researcher`, `plan`) never persist. Friction audit is a deterministic skill, not a spawned gate role.

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

## Friction audit (end-of-run)

The orchestrator invokes `pipeline-friction-audit` after PR publish. It writes `friction-findings-r<N>.md` only. Findings are non-gating and feed pipeline-improvement backlog grooming.

The archived historical subagent doc lives at `docs/archive/pipeline/friction-reviewer.md`. Current friction audit scans for:

- Skill invocations fire (no inline duplication regression)
- AGENT-BRIEF template followed in `brief.md`
- Reviewer emitted both axes
- Build evidence shows red-green sequence or eco-fallback note
- Architect verdict contains `adr_emitted:` assertion
- Persistent roles honored task_id continuity across revisions
- Monitor agent file absent

## Related

- [[Pipeline Overview]]
- [[Pipeline Stages]] — role inclusion + dependency graph
- [[Pipeline Artifacts]] — full verdict schema
- [[Pipeline Skills]] — `verdict-parse` skill that the routing layer uses
