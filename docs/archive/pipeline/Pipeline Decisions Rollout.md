# Pipeline Decisions Rollout

Phased delivery plan for the [[Pipeline Decisions|decision-elicitation]] stage. Each phase ships a vertical slice with its own acceptance criteria. Earlier phases can land independently; later phases assume the prior ones.

## Phase 0 — POC (delivered)

**Scope**

- `decision-elicitation` skill with artifact contracts (`options-r<N>.md`, `decision-r<N>.md`, `awaiting-decision-r<N>.md`).
- Orchestrator integration: role inclusion rule, dependency-graph entry, artifact discipline updates, SQLite Ledger decision-state extension (`decision_points`, `paused_on_decision`).
- Sync delivery via `AskUserQuestion`.
- Async delivery via Slack Socket Mode listener (`.claude/pipeline/slack_listener.py`) + `ScheduleWakeup` (`delaySeconds=600`).
- Trigger: explicit `decision_points:` declaration in brief or plan only.
- Reply syntax: button click (no text parsing). Listener writes `decision-r<N>.md` directly.
- Resume sentinel `<<resume-pipeline-<artifact-id>>>`.
- Markdown options canonical; HTML companion not required.
- Doctrine docs: [[Pipeline Decisions]], [[Pipeline Stages]] update, [[Pipeline Artifacts]] update.

**Acceptance criteria**

- [ ] A brief with `decision_points:` block triggers stage injection at declared `after:` role.
- [ ] Sync mode produces a working `AskUserQuestion` prompt and writes `decision-r<N>.md` on pick.
- [ ] Async mode writes `awaiting-decision-r<N>.md`, listener posts threaded Slack message, schedules a 10-minute wake, halts cleanly.
- [ ] Resume on wake fires the poll procedure; button click → listener writes `decision-r<N>.md`; pipeline resumes.
- [ ] Async pre-check failure (no `pipeline.toml`, missing listener script, missing tokens, listener spawn fails) degrades to sync.
- [ ] Timeout (default 7d) writes `verdict: timeout` and halts.
- [ ] SQLite Ledger shows `status=paused_on_decision` during wait.

**Out of scope (deferred to later phases)**

- HTML companion artifact.
- Auto-detect from role self-flag or brief heuristics.
- Loop-limit escape hatch.
- Multi-stakeholder workflows.
- LLM free-form comment parse.
- Cross-run decision archive.
- Architect code-direction option panels.

## Phase 1 — HTML render layer

**Goal:** turn the option set into a visual artifact when taste matters (UI mockups, design comparisons).

**Scope**

- `options-r<N>.html` template: grid layout, side-by-side panels, tradeoff tables, SVG mockup slots.
- [[Pipeline Skills|frontend-design]] skill wired as required dep when the requesting role is `ui-ux-designer`.
- `xdg-open` launcher for sync mode; falls back to printing the file path when headless.
- "Copy as prompt" clipboard button on each panel (vanilla JS, no framework).
- HTML linked from async Slack message body (file upload via `files.upload` API or raw path note when on local network only).

**Acceptance criteria**

- [ ] Generated HTML renders correctly in Firefox and Chromium.
- [ ] Headless run (no DISPLAY) skips `xdg-open` and prints path.
- [ ] Copy-as-prompt button writes a parseable string to clipboard.
- [ ] Async Slack message includes link or upload of HTML file (uploaded via `files.upload`, or local-path note when offline).

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

- When [[Pipeline Gates|revision loop]] limit hits (design 3, code 3, ops 1), orchestrator emits a guidance decision via the async Slack listener instead of dying.
- Auto-generated options from the last 3 verdicts: `extend loop +2`, `restart from <stage>`, `adjust acceptance criteria`, `abort`.
- Button click routes to the matching recovery action.
- Always async (loop-limit by definition means revisions exhausted; runner may be away).

**Acceptance criteria**

- [ ] A test pipeline that hits design-loop limit posts a guidance decision in Slack.
- [ ] `extend` button re-runs the stage with +2 revision budget.
- [ ] `restart from architect` button re-spawns architect fresh.
- [ ] `abort` button halts cleanly with audit trail.

**Dependencies**

- Phase 0, Phase 2 (decision-point reuse).

## Phase 4 — Multi-stakeholder + LLM parse + audit

**Goal:** make decision issues first-class team artifacts.

**Scope**

- `--assign <slack-user-id>` flag in `decision_points:` for delegating decisions (listener allowlists clicks to the assignee).
- LLM free-form reply parse: if no button click, listener reads the most recent thread reply from the assignee, posts a confirmation message ("Interpreted as Option B. React 🛑 within 10min to cancel."), re-wakes once, proceeds unless cancelled.
- Generated PR bodies auto-link Slack decision threads via permalink in the PR body.
- [[Pipeline Gates|pipeline-friction-audit]] audit step: scan `<run-dir>/awaiting-decision-r*.md` across active runs; report orphans + post resolution emoji in the corresponding Slack thread at run-complete.

**Acceptance criteria**

- [ ] Assigning a teammate routes notifications correctly.
- [ ] Free-form reply ("go with B, the streaming one") parsed and confirmed before action.
- [ ] User can override LLM parse via 🛑 reaction within the override window.
- [ ] PR bodies link the Slack threads that drove their scope.
- [ ] pipeline-friction-audit reports orphan awaiting files per run.

**Dependencies**

- Phase 0, Phase 2.

## Phase 5 — Cross-run decision archive

**Goal:** make past decisions discoverable and reusable.

**Scope**

- Persist `decision-r<N>.md` copies to `~/.pipeline/decisions/<project-slug>/<artifact-id>-d<N>.md` at run complete.
- New intake step: parse `as decided in <artifact-id>` (or topic-keyword search) → orchestrator includes the prior `decision-r<N>.md` in the new run's brief/Read set.

**Acceptance criteria**

- [ ] Decisions copied to global decision archive on run-complete.
- [ ] Intake recognizes prior-decision references and pre-loads them.

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
| Free-form parse misroutes user intent | Phase 4 confirmation message + 🛑 reaction override window. |
| Slack message clutter in a chatty workspace | Thread-per-run isolates noise; one channel per project keeps cross-project chatter separate; pipeline-friction-audit surfaces orphans. |
| HTML companion bloats run dirs | Phase 1 keeps HTML optional + scoped to `<run-dir>/decisions/`. Cleaned at run-complete (Phase 4). |
| Cross-run archive drift | Phase 5 archive is immutable per artifact-id; user grooms via direct file edit. |

## Related

- [[Pipeline Decisions]] — stage contract + invocation
- [[Pipeline Skills|decision-elicitation skill]]
- [[Pipeline Stages]] — role catalog
- [[Pipeline Artifacts]] — artifact discipline
