# Pipeline Artifacts

A pipeline run produces a directory of files under `<repo>/.pipeline/runs/<artifact-id>/`. Each agent owns specific files; the orchestrator owns only the ledger + a couple of cross-cutting reports.

## Naming

- Run + plan identifier: `<slug>-<hex6>` from `artifact-slug`. Three kebab-cased words plus a 6-char hex suffix. Example: `zazzy-riding-popcorn-a3f29b`.
- Project slug for the plan dir: the absolute project path with `/` replaced by `-`. Example: `/home/nikki/dotfiles` → `-home-nikki-dotfiles`.
- Verdicts are versioned: `verdict-<type>-r<N>.md`. `N` increments per revision loop. The orchestrator picks the max-N file when routing.
- Build evidence is versioned + sharded: `build-evidence-r<N>-s<K>.md`.

## Run directory layout

```
<repo>/.pipeline/runs/<artifact-id>/
├── pipeline.md                              # orchestrator ledger
├── brief.md                                 # AGENT-BRIEF template (intake)
├── plan.ref                                 # canonical plan pointer (if plan exists)
├── research.md                              # researcher output
├── ideation.md                              # content-designer output
├── design.md                                # architect output
├── frontend-handoff.md                      # ui-ux-designer OR build fallback
├── options-r<N>.md                          # decision-point options (per d<N>; owned by options_source role)
├── options-r<N>.html                        # optional visual companion (Phase 1+)
├── awaiting-decision-r<N>.md                # transient async state; removed on resume (orchestrator-owned)
├── decision-r<N>.md                         # decision verdict + pick (orchestrator-owned)
├── test-paths.txt                           # build-emitted manifest (overrides default test-path globs)
├── prebuild-skeptic-code-r<N>-s<K>.md       # per shard, per revision
├── build-evidence-r<N>-s<K>.md              # per shard, per revision
├── verdict-design-r<N>.md
├── verdict-code-r<N>.md
├── verdict-ops-r<N>.md
├── verdict-review-standards-r<N>.md         # reviewer standards-axis
├── verdict-review-spec-r<N>.md              # reviewer spec-axis
├── verdict-review-r<N>.md                   # orchestrator aggregate
├── verdict-security-r<N>.md
├── verdict-test-r<N>.md
├── verdict-test-audit-r<N>.md               # skeptic test-audit gate (when included)
├── verdict-friction-r<N>.md                 # friction-reviewer Approved/Blocked
├── friction-report-r<N>.md
├── pr-report.md                             # orchestrator after pr_publish
└── worktrees/
    ├── s1/                                  # shard 1 git worktree
    ├── s2/                                  # ...
    └── s<K>/
```

Worktrees are cleaned up after merge. The artifact files remain.

## Ledger schema (`pipeline.md`)

Orchestrator-only. Capped at ~40 lines. YAML frontmatter + a couple of markdown sections:

```yaml
---
run_id: <artifact-id>
plan_id: <artifact-id|none>
brief: <one-line>
roles_included: [..]
roles_skipped: {role: reason}
parallel: true|false                                  # true when K>=2
base_ref: <branch-name>
base_sha: <sha-at-intake>
github_delivery: pr|branches-only
shards:
  s1: {status: pending|running|passed|failed|skipped_due_to_dep, branch: <ref>, worktree: <path>, evidence: <file>, depends_on: [..]}
pr_urls:
  s1: <url>
merge_shas:
  s1: <sha|null>
decision_points:                                      # if brief/plan declared any
  d1: {after: <role>, options_source: <role>, delivery: sync|async, timeout_days: 7, status: pending|active|resolved|timeout|cancelled}
paused_on_decision:                                   # present only while waiting on async decision
  decision_id: d<N>
  delivery_mode: async
  slack_channel: <channel-id>
  opened_at: <iso8601>
  timeout_at: <iso8601>
  next_wake_at: <iso8601>
---

## Stages
- role: status (rN)
- decision-elicitation: d<N> (sync|async) → chosen|timeout|cancelled
- pr_publish: <pending|complete>

## Summary
Loops: design <D>, code <C>, ops <O>
Status: in-progress|paused_on_decision|complete|halted
PRs: <count> opened
```

The `shards:` map is the canonical build status — build does not write a row in `## Stages`.

## Verdict schema (all gate roles)

YAML frontmatter on every `verdict-<type>-r<N>.md`:

```yaml
---
verdict: Approved | Blocked | Conditional
role: <skeptic|reviewer|tester|security-auditor|friction-reviewer>
review_type: <design|code|ops|review|security|test|test-audit|friction>
loops: <N>
revision: r<N>
prod_diff_sha: <40-hex>      # required on skeptic code + test-audit; enables pin validation
axis: standards | spec       # required on reviewer per-axis verdicts
---
```

Body sections vary by role (typically Blocking / Conditions / Suggestions / Nits / Notes).

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

Missing evidence file for a declared shard = `skeptic-code` gate Blocks with the specific shard cited.

## Where else state lives

- **Canonical plans**: `~/.pipeline/plans/<project-slug>/<artifact-id>.md`

## Related

- [[Pipeline Overview]]
- [[Pipeline Gates]] — how verdicts route revisions
- [[Pipeline Shards]] — per-shard artifact discipline
