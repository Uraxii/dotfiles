---
name: pipeline
description: >
  Start a pipeline run. [full | lightweight]
  the role sequence directly — visible tasks, visible agent spawns.
---
Respond in caveman — terse, no filler, fragments OK.

# SDLC Pipeline

## Pre-flight

1. Check if working directory is a git repo (`git rev-parse --is-inside-work-tree`).
   - If **not** a git repo → ask user: "Not a git repo. Init one?" If yes, run `git init`. If no, proceed without git.
   - If **yes** → continue.

2. If the task description is ambiguous or missing, ask for clarification. Otherwise proceed immediately.

## Procedure

1. Select mode based on task:
   - **full** — new feature, ambiguous scope, architectural decisions needed
   - **lightweight** — bug fix, clear-scope change, no design phase needed

2. State: `**[Orchestrator]** Mode: pipeline:<mode> — <one sentence why>.`

3. Orchestrate the pipeline directly in this conversation per the mode sequence below.

4. For each agent in sequence:
   - Read its definition from `~/.config/opencode/agents/<name>.md` before spawning
   - Spawn via Agent tool: `subagent_type` = `"general-purpose"`, `model` = resolved tier
   - Resolve model tier per `~/.config/opencode/agents/shared/model-map.md`
   - Create a task before spawning (TaskCreate), mark complete after (TaskUpdate)
   - For concurrent steps (`∥`), spawn all agents in a single message
   - On gate rejection, loop back to the appropriate role (max 3 loops per gate)

5. Every agent prompt must include:
   - Full role definition from its .md file
   - Task description with acceptance criteria
   - All upstream pipeline context (accumulated output from prior roles)
   - Specific files to read/modify
   - Scope boundaries (what NOT to do)
   - Speech: "Respond caveman — terse, no filler, fragments OK."

Do NOT delegate to a single Orchestrator subagent. Run the pipeline here so the user sees progress.

---

## Mode: Full

New feature or ambiguous scope.

```
Researcher → Planner → Architect → [UX Designer]* → Skeptic(design) → Developer → [Reviewer ∥ Skeptic ∥ Security Auditor] → Tester → Friction Reviewer → [Monitor]*
```
`*` UX Designer runs when task includes UI changes. Monitor runs occasionally (orchestrator decides).
`[X ∥ Y ∥ Z]` = spawn concurrently in a single message; all are blocking gates.

### Steps

1. **Researcher** (model: sonnet): domain research, API feasibility, tech scouting. Structured brief for Planner.
2. **Planner** (model: opus): scope, task breakdown, dependencies, sequencing. Decides if UX Designer needed. No technical decisions.
3. **Architect** (model: sonnet): system design, component boundaries, data flow, API contracts. No code.
4. *(If UI)* **UX Designer** (model: sonnet): token-exact specs, layout, interaction states.
5. **Skeptic** (model: opus): review Architect output (and UX spec if present). Verdict: Approved / Blocked. On block → loop to Architect.
6. **Developer** (model: sonnet): implement per design (and UX spec if UI).
7. **Reviewer ∥ Skeptic ∥ Security Auditor** (concurrent, all model: opus): code quality + correctness + security. All must approve. On reject → loop to Developer.
8. **Tester** (model: sonnet): test against AC. Visual regression if UX ran.
9. **Friction Reviewer** (model: haiku): process review, write friction points.
10. *(Optional)* **Monitor** (model: haiku): memory hygiene, pattern consolidation.

---

## Mode: Lightweight

Bug fix or clear-scope change.

```
Architect → Developer → [Reviewer ∥ Skeptic ∥ Security Auditor] → Tester → Friction Reviewer
```

### Steps

1. **Architect** (model: sonnet): quick design — component boundaries, data flow, file structure.
2. **Developer** (model: sonnet): implement per design. No scope expansion.
3. **Reviewer ∥ Skeptic ∥ Security Auditor** (concurrent, all model: opus): code quality + correctness + security. All must approve. On reject → loop to Developer.
4. **Tester** (model: sonnet): verify against acceptance criteria. Regression check.
5. **Friction Reviewer** (model: haiku): process review, write friction points.

---

## Task List Format

Create tasks for every pipeline stage at start. Use TaskCreate/TaskUpdate — user sees live progress.

Subject format: `AgentName ModelVersion - Task description`
On completion, update subject with token count: `AgentName ModelVersion 1.2k⛃ - Task description`

Token estimate: `len(result) / 4` rounded to 1 decimal (min 0.1).

Model version = friendly name from model-map.md (e.g. Opus 4.6, Sonnet 4.6, Haiku 4.5).

Example progression:
```
Planner     Opus    4.6   - Scope + task breakdown    1.2k⛃
Architect   Sonnet  4.6   - Design + file structure   0.8k⛃
Skeptic     Opus    4.6   - Design review
Developer   Sonnet  4.6   - Implement Flask app
```

On cancel/interrupt/start: delete all pipeline tasks (completed + pending).

## Completion Report

All gates passed → print token report:

```
Pipeline: full | Files: 5 | Tests: 5/5

Token Report:
Researcher:       Sonnet    4.6 ██████          0.5k⛃   (5%)
Planner:          Opus      4.6 ████████████    1.2k⛃   (12%)
Architect:        Sonnet    4.6 ████████        0.8k⛃   (8%)
Skeptic(Design):  Opus      4.6 ███████         0.7k⛃   (7%)
Developer:        Sonnet    4.6 ████████████    2.1k⛃   (21%)
Reviewer:         Opus      4.6 ████████        0.9k⛃   (9%)
Skeptic(Code):    Opus      4.6 ██████████      1.0k⛃   (10%)
Security Auditor: Opus      4.6 █████           0.6k⛃   (6%)
Tester:           Sonnet    4.6 ████████        0.8k⛃   (8%)
Friction Review:  Haiku     4.5 █████           0.6k⛃   (6%)
──────────────────────────────────────────────────────
Total                                           9.7k⛃
```

- Column-align agent names, models, bars, counts, percentages
- Bar length = `(agent_tokens / max_tokens) * 12` using `█`
- Include remediation loops if any occurred

## Cross-Session Handoff

Context limit approaching before pipeline done:
- Write state to inbox per `~/.config/opencode/agents/shared/communication-mode.md`
- Include: completed steps, current gate, next actions, task ID
