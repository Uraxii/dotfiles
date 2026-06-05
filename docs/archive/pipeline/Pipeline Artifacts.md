# Pipeline Artifacts

A pipeline run produces a directory of files under `<repo>/.pipeline/runs/<artifact-id>/`. Runtime state lives in the SQLite Ledger. Files in the run dir are artifacts, manifests, or pointers; they must not duplicate ledger state.

## Naming

- Run + plan identifier: `<slug>-<hex6>` from `artifact-slug`. Three kebab-cased words plus a 6-char hex suffix. Example: `zazzy-riding-popcorn-a3f29b`.
- Project slug for the plan dir: the absolute project path with `/` replaced by `-`. Example: `/home/nikki/dotfiles` → `-home-nikki-dotfiles`.
- Verdicts are versioned: `verdict-<type>-r<N>.md`. `N` increments per revision loop. The orchestrator picks the max-N file when routing.
- Build evidence is versioned + sharded: `build-evidence-r<N>-s<K>.md`.

## Run directory layout

```
<repo>/.pipeline/runs/<artifact-id>/
├── pipeline.md                              # compact manifest/pointers; not runtime source of truth
├── brief.md                                 # AGENT-BRIEF template (intake)
├── context-digest.md                        # common compact handoff input for every spawn
├── plan.ref                                 # canonical plan pointer (if plan exists)
├── research.md                              # researcher output
├── ideation.md                              # content-designer output
├── design.md                                # architect decisions/rationale/ADR refs
├── build-contract.md                        # implementation handoff: interfaces, AC map, file/module map
├── frontend-handoff.md                      # ui-ux-designer OR build fallback
├── options-r<N>.md                          # decision-point options (per d<N>; owned by options_source role)
├── options-r<N>.html                        # optional visual companion (Phase 1+)
├── awaiting-decision-r<N>.md                # transient async state; removed on resume (orchestrator-owned)
├── decision-r<N>.md                         # decision verdict + pick (orchestrator-owned)
├── test-paths.txt                           # build-emitted manifest (overrides default test-path globs)
├── build-evidence-r<N>-s<K>.md              # per shard, per revision; includes prebuild skeptic section
├── verdict-design-r<N>.md
├── verdict-code-r<N>.md
├── verdict-ops-r<N>.md
├── verdict-review-standards-r<N>.md         # reviewer standards-axis
├── verdict-review-spec-r<N>.md              # reviewer spec-axis
├── verdict-review-r<N>.md                   # orchestrator aggregate
├── verdict-security-r<N>.md
├── verdict-test-r<N>.md
├── verdict-test-audit-r<N>.md               # skeptic test-audit gate (when included)
├── friction-findings-r<N>.md                # deterministic non-gating friction audit
├── pr-report.md                             # orchestrator after pr_publish
└── worktrees/
    ├── s1/                                  # shard 1 git worktree
    ├── s2/                                  # ...
    └── s<K>/
```

Worktrees are cleaned up after merge. The artifact files remain.

## Run manifest (`pipeline.md`)

Orchestrator-only. Capped at ~40 lines. Manifest/pointers only. The SQLite Ledger is canonical for runtime state: phase, task ids, shard status, gate status, decision state, continuation tokens, and timestamps. `pipeline.md` exists for human orientation and path lookup; never mirror full ledger rows into it.

```yaml
---
run_id: <artifact-id>
ledger_id: <sqlite-row-id-or-uuid>
plan_ref: <artifact-id|none>
brief: <one-line>
roles_included: [..]
roles_skipped: {role: reason}
parallel: true|false                                  # true when K>=2
base_ref: <branch-name>
base_sha: <sha-at-intake>
github_delivery: pr|branches-only
artifacts:
  context_digest: context-digest.md
  brief: brief.md
  plan: plan.ref
  design: design.md
  build_contract: build-contract.md
  ledger_query: query-ledger --run <artifact-id>
---

## Stages
- See Ledger: `query-ledger --run <artifact-id> --view stages`

## Summary
Status: see Ledger
PRs: see Ledger
```

Shard/build/gate/decision status belongs in the SQLite Ledger. `pipeline.md` may point to latest artifacts but must not duplicate ledger state.

## Verdict schema (all gate roles)

YAML frontmatter on every `verdict-<type>-r<N>.md`:

```yaml
---
verdict: Approved | Blocked | Conditional
role: <skeptic|reviewer|tester|security-auditor>
review_type: <design|code|ops|review|security|test|test-audit>
loops: <N>
revision: r<N>
prod_diff_sha: <40-hex>      # required on skeptic code + test-audit; enables pin validation
axis: standards | spec       # required on reviewer per-axis verdicts
---
```

Verdicts are emitted through `record-verdict`, which validates schema, writes ledger rows, and writes the markdown artifact atomically. `findings:` is canonical. Body prose is optional; when present it should be compressed.

## Brief schema (`brief.md`)

Set by the [[Pipeline Skills|agent-brief-format]] skill. Durability over precision: no file paths, no line numbers (they go stale before the agent runs).

```markdown
## Brief

**Category:** bug | enhancement | refactor | ops
**Summary:** one-line description

**Current behavior:**
…

**Desired behavior:**
…

**Key interfaces:**
- `TypeName` — what changes + why
- `functionName()` return type — current vs desired

**Acceptance criteria:**
- [ ] Specific testable criterion 1
- [ ] …

**Out of scope:**
- …
```

## Build evidence

`build-evidence-r<N>-s<K>.md` must contain:

- `revision`, `timestamp`, `shard_id`
- exact commands run
- exit code per command
- pass/fail summary
- key failure logs (if any)
- TDD section: red-green sequence OR the literal line `TDD: skipped, reason: <eco-detail>`
- optional `commit_sha` (pipeline-internal audit anchor; the PR commit is opaque post-squash)
- prebuild skeptic section: change-risk scan, failure-mode assertions, targeted test scaffold, precheck result. Use a separate `prebuild-skeptic-code-r<N>-s<K>.md` only when an actual separate precheck run must happen before implementation.

Missing evidence file for a declared shard = `skeptic-code` gate Blocks with the specific shard cited.

## Where else state lives

- **Canonical plans**: `~/.pipeline/plans/<project-slug>/<artifact-id>.md`

## Related

- [[Pipeline Overview]]
- [[Pipeline Gates]] — how verdicts route revisions
- [[Pipeline Shards]] — per-shard artifact discipline
