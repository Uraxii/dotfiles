---
name: pipeline
description: >
  Start a pipeline run. Orchestrator composes role sequence per Brief — no fixed modes.
  Default execution: inline (role-switch in main session). Spawn only when parallel or context-heavy.
---

Orchestrator speech → user: **caveman:ultra**.

# SDLC Pipeline

## Pre-flight

1. `git rev-parse --is-inside-work-tree`.
   - Not repo → ask "Not git repo. Init?" yes → `git init`. no → proceed.
   - Yes → continue.
2. Task ambiguous/missing → ask. Else proceed.

## Execution Mode

Two modes. Pick per stage, not per run. Default = **inline**.

### Inline (default)
- Orchestrator (this session) adopts each role sequentially.
- Prefix output `**[RoleName]**` + role emoji. Announce role switches.
- Read role def `~/.config/opencode/agents/<role>.md` once into conversation when first adopting.
- Append role's section to `relay.md` inline. No separate Read/Write by spawned agent.
- Source files cached across roles → no cold re-reads.
- Rev loops = re-adopt role, re-think in same context. No spawn.

### Spawn
Reserved for:
- **Concurrent independent work** (≥2 roles with disjoint file scope, e.g. `[Reviewer ∥ Skeptic(C) ∥ Security]` on large code diff).
- **Context pressure**: conversation > ~400k tokens; offload downstream stage to fresh agent.
- **User forces**: `/pipeline spawn <brief>` or cost-insensitive run.

Even concurrent-review is often cheaper inline-sequential (shared source cache). Spawn only when diff is big enough that 3 cold reads beat 3 re-reads.

### Announce mode in plan
Include in plan line: `Execution: inline` or `Execution: spawn [stage list]` or `Execution: mixed (spawn [stages])`.

## Compose the pipeline

No fixed modes. You (Orchestrator) pick which roles run, based on Brief.

**Required every run:**
- `developer` — if any code change.
- `skeptic` — at least one gate pass (design OR code). Non-negotiable.
- `friction-reviewer` — final role, always. (Inline: Friction runs as wrap-up section; no separate spawn needed.)

**Optional roles — include only when triggered:**

| Role             | Include when                                                                 |
|------------------|------------------------------------------------------------------------------|
| `researcher`     | Brief touches unfamiliar files/libs + no project-index coverage.            |
| `planner`        | Multi-item Brief OR ambiguous scope. Skip for single clear change.          |
| `architect`      | New data shape, schema change, state machine, new module boundary.          |
| `ux-designer`    | UI surface change (visual, interaction, haptics, new component).            |
| `reviewer`       | Code change > ~50 LoC OR crosses module boundary OR touches shared utils.   |
| `security-auditor` | External input, auth, crypto, storage, network, permissions, native code.  |
| `tester`         | Prod code change + existing test coverage OR new behavior needs regression. |
| `monitor`        | Cross-cutting systemic concern (rare).                                      |

**Ops-style short path** — release / PR-merge / dep bump / config sync / pure docs:
- Dev → Skeptic → Friction. Skip Reviewer, Security, Tester, Planner.
- Max 1 Dev rework. 2+ → upgrade mid-run (add Reviewer + Tester).

**Split Briefs when items diverge.** 4-item Brief w/ 1 design item + 3 bugs → design item full, bugs direct-edit or single Dev pass. Don't run all items through one heavy pipeline.

## Announce + get user nod for expensive runs

State plan ≤ 5 lines:

```
**[Orchestrator]** Plan:
- Roles: planner, architect, ux, skeptic(D), dev, reviewer, skeptic(C), tester, friction (9)
- Execution: inline (spawn [Reviewer ∥ Skeptic(C) ∥ Security] if diff > 500 LoC)
- Expected loops: 1 design, 1 code
- Est. tokens: ~250k  (inline default; multiply ×4-5 if all spawned)
- Why: item 2 = new taxonomy; items 1/3/4 = logger UX coupled to item 2
```

If est > 500k or user flagged cost pressure: ask "Proceed? Or slim (drop <role> / spawn fewer)?"
If est ≤ 200k or Brief = single bug: proceed silent.

## Procedure

1. Pre-flight + compose plan + pick exec mode per stage.
2. Announce plan.
3. Per stage — **inline path** (default):
   - TaskCreate before role adopt, TaskUpdate after.
   - Read `~/.config/opencode/agents/<role>.md` if not already in context.
   - Announce role: `**[RoleName]**` + one-line intent.
   - Do the work (read relay, read source as needed, reason, edit).
   - Append role's section to `relay.md`.
   - TaskUpdate complete.
4. Per stage — **spawn path** (only when stage marked spawn):
   - TaskCreate.
   - Resolve tier → vendor via `~/.config/opencode/agents/shared/model-map.md`.
   - Spawn Agent: `subagent_type=<role-name>` (role def auto-loaded), `model`=resolved tier.
   - Concurrent (`∥`) → one message, all spawns.
   - Agent prompt ≤ ~400 tok: Task ID, acceptance criteria, relay path, files to touch, scope boundaries. No role-def inlining. No speech directive. No unverified metadata.
5. Gate reject → loop back. Inline: re-adopt upstream role in same context. Spawn: re-spawn w/ Skeptic's relay section as input. Max loops: **3** code/design, **1** ops-path.

## Sequencing rules

- Researcher before Planner (if present).
- Planner before Architect/UX (if present).
- Architect + UX can run parallel-inline (same session, both sections) or parallel-spawn (two agents, one message).
- Skeptic(design) after Architect+UX both done.
- Developer after all design-phase gates approve.
- Reviewer + Skeptic(code) + Security — inline-sequential default; spawn-parallel if diff large.
- Tester after code gates approve.
- Friction last.

---

## Relay Discipline

`relay.md` = the ONE shared artifact per run. All modes:
- Read on role-entry (one Read; inline = already in context after first read).
- Write own section (overwrite on revision, no dup).
- Reference upstream by relay section, NOT re-read source files.

Dev MUST post canonical `## Files` block once:
```
## Files
- <path>  <one-line purpose>
```

Downstream roles use this block. Open source files only to verify a specific claim (e.g. Skeptic runs aapt2, Tester runs Jest).

Spawn prompts: MUST NOT inline relay content. Agents read relay themselves.
Inline: relay already in context; skip re-read unless compaction happened.

**Project index precedence:** before Researcher role runs, check if project CLAUDE.md has Project Index covering Brief surface. If yes, skip Researcher or narrow to deltas only.

---

## Task List Format

TaskCreate every stage at start. TaskCreate/TaskUpdate → live progress.

Subject: `AgentName  [Mode]  - Task description`
  - Inline: `Architect  inline  - Design taxonomy`
  - Spawn:  `Skeptic  Opus 4.6  - Code review`
On done:
  - Inline: same subject + `✓` (no per-role token count; inline shares conversation tokens).
  - Spawn: append `Tokens⛃` from actual `usage.total_tokens` footer: `<usage>total_tokens: NNNNN ...</usage>`. Format `X.Yk⛃`.

Model version for spawn: friendly name from model-map.md (Opus 4.6, Sonnet 4.6, Haiku 4.5).

Cancel/interrupt/start → delete all pipeline tasks (done + pending).

---

## Completion Report

All gates pass → print report:

**Inline-only run:**
```
Pipeline: <role list> | Files: N | Tests: N/N | Loops: D design, C code
Execution: inline
Conversation tokens: ~XXXk (from session total)
```

**Spawn or mixed run:**
```
Pipeline: <role list> | Files: N | Tests: N/N | Loops: D design, C code
Execution: mixed (spawn: <stage list>)

Token Report (spawn stages only):
Skeptic(C):  Opus   4.6 ████████    1.0k⛃   (10%)
...
──────────────────────────────────────────────────────
Spawn total                          X.Yk⛃
Inline conversation                  ~XXXk
Grand total                          ~XXXk
```

- Col-align: names, models, bars, counts, %
- Bar len = `(agent_tokens / max_tokens) * 12` via `█`
- Include remediation loops
- If total > announced estimate ×1.5 → add one-line "Overrun cause: <reason>"
