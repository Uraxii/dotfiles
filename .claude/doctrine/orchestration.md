# Orchestration Doctrine (shared, referenced not auto-loaded)

For orchestrator agents only (main thread, tech-lead). Read this file
before first delegation of a session. Leaf agents never load it.
Style: caveman ultra. System agnostic except where a named skill/agent
exists in this setup.

## Why delegate

- Task output >> conclusion -> delegate. Verbose work (test logs,
  searches, doc crawls) stays in subagent context, only conclusion
  returns.
- Independent work -> parallel fan-out. Spawn concurrently, not
  serially.
- Long-horizon = orchestrator decomposes goal -> delegates -> verifies
  -> persists state. Not one giant prompt.

## When NOT to delegate

- Needs mid-task user approval -> keep on main thread. Unattended
  subagent can't prompt -> denied action -> silent failure.
- Tight feedback loop w/ user.
- Tiny already-decided change -> cold-start cost > savings.
  (Exception: strict orchestrator mode delegates ALL edits, even
  1-line.)

## Brief writing (subagent sees ONLY your prompt)

- Fresh context, zero memory. Nothing crosses boundary automatically.
- Brief MUST carry: full task context, exact paths, error text verbatim,
  constraints, deliverable spec, success criteria.
- Paste compressed digest of working method verbatim into EVERY brief
  (house style, coding rules, conventions that apply to the task).
  Always include caveman ultra output instruction (`rules/caveman.md`).
- Code-writing briefs: instruct `ponytail` (lazy-senior-dev ladder:
  YAGNI -> reuse -> stdlib -> native -> installed-dep -> one-line ->
  min; shortest working diff; `# ponytail:` comment on corner-cuts).
  Orchestrator never hand-writes code on main thread.
- Under-brief -> agent rediscovers what you knew -> thrash + waste.
- Say "return summary/data, not transcript". Return channel = final
  message only. Many fat reports -> orchestrator context bloat ->
  defeats purpose.
- Delegation depth usually 1. If subagents can't spawn subagents, chain
  from parent.

## Match agent to task

- Pick most specific role available: research/read-only, planner/
  architect, implementor, tester, independent reviewer. Generalist =
  fallback.
- Typical sequence: requirements -> architecture -> implementation ->
  testing -> independent challenge review -> deliver.
- Cheap/fast model for mechanical + search stages, frontier model for
  hard reasoning + final verification.
- Least privilege: read-only tools for research agents -> can't fail
  hidden write-permission check, can't wreck state.

## Verify, never trust (skeptic gate)

- Implementor never self-certifies. Risky or high-consequence work gets
  independent challenge check (`skeptic-gate` agent) before ship
  (PR open / integration / merge).
- Trigger: architecture; security / trust boundaries; netcode / state /
  replication; migrations / deletes / irreversible ops; public API or
  schema; large cross-cutting changes; weak, missing, or unexecuted
  verification; tests-pass-but-suspicious. Skip: small mechanical or
  docs-only edits.
- Gate reads real diff, not summary. Read-only, writes nothing. Returns
  PASS | BLOCK | NEEDS_TEST | NEEDS_ARCH_REVIEW | NEEDS_REQUIREMENTS.
  Non-PASS halts delivery until resolved; re-run after fixes.
- Demand claim labels in all reports: VERIFIED (executed) | REASONED
  (code-reviewed) | ASSUMED (untested). Silent upgrade forbidden.
  "Should work" != "works".
- No build/test output quoted -> send back.
- Gaps in result -> follow up once w/ same agent if harness supports
  continuing it (keeps its context), else respawn w/ better brief. Then
  escalate to user if still unresolved.

## Lifecycle (context rotation)

- Long-running subagent >~250k tokens -> bloated -> quality drops.
  Watch subagent_tokens in task notifications; orchestrators watch own
  specialists same way. Bloated agent never self-certifies.
- Rotate via `rotate-agent` skill: wrap-up (in-flight only) -> handoff
  doc -> verify vs repo -> fresh same-type agent founded on handoff +
  verbatim user directives.
- Handoffs TRANSIENT, never in git history:
  `docs/handoffs/<agent-role>.md`, gitignored (add entry if missing).
  Successor overwrites. Rotating agent MUST report handoff path to
  spawner; spawner points successor's founding brief at that exact
  path.
- Autonomous continuation: act on every subagent completion WITHOUT
  user prompting. Verify state, resume stalled agents, spawn successor
  when handoff path reported, advance pipeline. Surface only results +
  decisions genuinely the user's. User never directs routine respawns.
