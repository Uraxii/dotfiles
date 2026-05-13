# Pipeline Decisions Rollout

Phased delivery plan for the [[Pipeline Decisions|decision-elicitation]] stage. Each phase ships a vertical slice with its own acceptance criteria. Earlier phases can land independently; later phases assume the prior ones.

## Phase 0 — POC (delivered)

**Scope**

- `decision-elicitation` skill with artifact contracts (`options-r<N>.md`, `decision-r<N>.md`, `awaiting-decision-r<N>.md`).
- Orchestrator integration: role inclusion rule, dependency-graph entry, artifact discipline updates, `pipeline.md` schema extension (`decision_points:`, `paused_on_decision:` blocks).
- Sync delivery via `AskUserQuestion`.
- Async delivery via `gh issue create` + `ScheduleWakeup` (`delaySeconds=600`).
- Trigger: explicit `decision_points:` declaration in brief or plan only.
- Reply syntax: strict `/pick A|B|C|D` (or `1`-`4`).
- Resume sentinel `<<resume-pipeline-<artifact-id>>>`.
- Markdown options canonical; HTML companion not required.
- Doctrine docs: [[Pipeline Decisions]], [[Pipeline Stages]] update, [[Pipeline Artifacts]] update.

**Acceptance criteria**

- [ ] A brief with `decision_points:` block triggers stage injection at declared `after:` role.
- [ ] Sync mode produces a working `AskUserQuestion` prompt and writes `decision-r<N>.md` on pick.
- [ ] Async mode opens a labeled issue, schedules a 10-minute wake, halts cleanly.
- [ ] Resume on wake fires the poll procedure; strict `/pick` parsed; pipeline resumes.
- [ ] Async pre-check failure (no `gh`, unauthed, non-github remote) degrades to sync.
- [ ] Timeout (default 7d) writes `verdict: timeout` and halts.
- [ ] `pipeline.md` shows `status: paused_on_decision` during wait.

**Out of scope (deferred to later phases)**

- HTML companion artifact.
- Auto-detect from role self-flag or brief heuristics.
- Loop-limit escape hatch.
- Multi-stakeholder workflows.
- LLM free-form comment parse.
- Cross-run decision memory.
- Architect code-direction option panels.

## Phase 1 — HTML render layer

**Goal:** turn the option set into a visual artifact when taste matters (UI mockups, design comparisons).

**Scope**

- `options-r<N>.html` template: grid layout, side-by-side panels, tradeoff tables, SVG mockup slots.
- [[Pipeline Skills|frontend-design]] skill wired as required dep when the requesting role is `ui-ux-designer`.
- `xdg-open` launcher for sync mode; falls back to printing the file path when headless.
- "Copy as prompt" clipboard button on each panel (vanilla JS, no framework).
- HTML linked from async issue body (preview image optional; raw HTML link works on GitHub).

**Acceptance criteria**

- [ ] Generated HTML renders correctly in Firefox and Chromium.
- [ ] Headless run (no DISPLAY) skips `xdg-open` and prints path.
- [ ] Copy-as-prompt button writes a parseable string to clipboard.
- [ ] Async issue body links to the HTML file (raw GitHub URL after PR merge, or local path note when not pushed).

**Dependencies**

- Phase 0 landed.

## Phase 2 — Auto-detect + mid-run self-flag

**Goal:** stop requiring explicit `decision_points:` for obvious branch points.

**Scope**

- Role contract extension: any role can return `decision_required: true` with an inline option set in its evidence; orchestrator parses, injects decision-elicitation stage automatically.
- Brief-intake heuristic: detect phrases like "explore options", "compare approaches", "A vs B" → orchestrator drafts a `decision_points:` entry and confirms via sync `AskUserQuestion` before running.
- Multi-decision per run support (sequential injection; one paused decision at a time).

**Acceptance criteria**

- [ ] `ui-ux-designer` can flag ambiguity and trigger a decision stage without pre-declared point.
- [ ] Brief heuristic catches at least the listed trigger phrases; user can override.
- [ ] Multi-decision runs sequence cleanly; no parallel-wait deadlock.

**Dependencies**

- Phase 0 landed.

## Phase 3 — Loop-limit escape hatch

**Goal:** turn the current "loop-limit halt" failure into a recoverable guidance request.

**Scope**

- When [[Pipeline Gates|revision loop]] limit hits (design 3, code 3, ops 1), orchestrator opens a guidance issue instead of dying.
- Auto-generated options from the last 3 verdicts: `extend loop +2`, `restart from <stage>`, `adjust acceptance criteria`, `abort`.
- Reply routes to the matching recovery action.
- Always async (loop-limit by definition means revisions exhausted; runner may be away).

**Acceptance criteria**

- [ ] A test pipeline that hits design-loop limit opens a guidance issue.
- [ ] `/pick extend` re-runs the stage with +2 revision budget.
- [ ] `/pick restart from architect` re-spawns architect fresh.
- [ ] `/pick abort` halts cleanly with audit trail.

**Dependencies**

- Phase 0, Phase 2 (issue creation reused).

## Phase 4 — Multi-stakeholder + LLM parse + audit

**Goal:** make decision issues first-class team artifacts.

**Scope**

- `--assign <user>` flag in `decision_points:` for delegating decisions.
- LLM free-form comment parse: if no strict `/pick` syntax, orchestrator reads the last author comment, posts a confirmation comment ("Interpreted as Option B (async). Reply STOP within 10min to cancel."), re-wakes once, proceeds unless STOP.
- Generated PR bodies auto-link decision issues via `Closes #<N>` or `Related: #<N>`.
- [[Pipeline Stages|friction-reviewer]] audit step: scan `gh issue list --label pipeline-<artifact-id> --state open`; close orphans at run-complete; surface stale open decisions across all active runs.

**Acceptance criteria**

- [ ] Assigning a teammate routes notifications correctly.
- [ ] Free-form comment ("go with B, the streaming one") parsed and confirmed before action.
- [ ] User can override LLM parse via `STOP` within the override window.
- [ ] PR bodies link the decision issues that drove their scope.
- [ ] friction-reviewer reports orphan issues per run.

**Dependencies**

- Phase 0, Phase 2.

## Phase 5 — Cross-run decision memory

**Goal:** make past decisions discoverable, reusable, and pattern-analyzable.

**Scope**

- Persist `decision-r<N>.md` copies to `~/.pipeline/decisions/<project-slug>/<artifact-id>-d<N>.md` at run complete.
- New intake step: parse `as decided in <artifact-id>` (or topic-keyword search) → orchestrator includes the prior `decision-r<N>.md` in the new run's brief/Read set.
- [[Pipeline Skills|dream]] skill extension: when curating memory, detect repeated picks ("you keep picking async for UI handoff") and surface as candidate memory entries via `claudemd-proposal.md`.

**Acceptance criteria**

- [ ] Decisions copied to global decision archive on run-complete.
- [ ] Intake recognizes prior-decision references and pre-loads them.
- [ ] Dream surfaces ≥1 pattern after 3+ runs with similar decision shape.

**Dependencies**

- Phase 0.

## Phase 6 — Code-direction elicitation

**Goal:** extend the stage from UI/visual decisions to implementation-approach decisions.

**Scope**

- Architect can emit option panels when its design surfaces 2+ viable approaches (lib A vs B, sync vs async, schema shape, etc.).
- Option panels include: code skeleton snippets, schema diagrams (SVG), state-machine diagrams (SVG), perf/complexity matrix.
- Architect dep graph adds optional decision-elicitation injection between draft and final `design.md`.

**Acceptance criteria**

- [ ] Architect run with ≥2 viable approaches emits options + halts for decision (when point declared or self-flagged).
- [ ] SVG diagrams render in browser; visible in async issue via image link.
- [ ] Final `design.md` pinned to chosen approach; explicit reference to `decision-r<N>.md`.

**Dependencies**

- Phase 0, Phase 1 (HTML render), Phase 2 (self-flag).

## Sequencing notes

- Phases 0 → 1 → 2 is the linear value path. Each unlocks the next's UX.
- Phases 3, 4, 5 are independent of Phase 1; can ship in any order once Phase 0 is in.
- Phase 6 is the most architecturally invasive; defer until Phases 1 + 2 prove the model.

## Risk + mitigation

| Risk | Mitigation |
|---|---|
| `ScheduleWakeup` only fires in `/loop` context | Document manual `resume <id>` fallback. Phase 0 ships both paths. |
| Free-form parse misroutes user intent | Phase 4 confirmation comment + STOP override window. |
| Issue spam in a chatty repo | Labels `pipeline-decision` + `pipeline-<artifact-id>` give clean filter; friction-reviewer closes orphans. |
| HTML companion bloats run dirs | Phase 1 keeps HTML optional + scoped to `<run-dir>/decisions/`. Cleaned at run-complete (Phase 4). |
| Cross-run memory drift | Phase 5 archive immutable; dream proposes, user merges via `claudemd-proposal.md`. |

## Related

- [[Pipeline Decisions]] — stage contract + invocation
- [[Pipeline Skills|decision-elicitation skill]]
- [[Pipeline Stages]] — role catalog
- [[Pipeline Artifacts]] — artifact discipline
