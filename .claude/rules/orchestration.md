# Orchestration Doctrine (shared: zakia + all sub-orchestrators)

## Topology: hub and spoke

- zakia (main thread) is the sole human-facing orchestrator; AskUserQuestion
  is unavailable to subagents. Sub-orchestrators (tech-lead for software
  workstreams, art-director for art workstreams) run as BACKGROUND agents so
  the human conversation stays live. One workstream per instance; multiple
  parallel instances are fine. Sub-orchestrators spawn their own specialist
  subagents (depth-2 spawning is verified working).
- Decisions and questions route through zakia only. Lateral agent-to-agent
  SendMessage is allowed solely to announce an artifact handoff
  ("ready at <path>"); the artifacts themselves hand off as files in durable
  dirs. Cross-workstream synthesis lives at zakia, never a separate agent.

## Bubble-up contract (sub-orchestrators never block on user decisions)

A question for the user is a board ticket, not a message payload.

- Mid-flight: file a `bd create` ticket labeled `needs-user` describing the
  question, `bd dep` the work ticket as blocked-by it, then SendMessage to
  "main" a ONE-LINE wake ping carrying only the ticket id (e.g. "question
  ticket df-12 filed"). No question payload goes in the message. Keep
  working on independent parts meanwhile.
- Terminal: shape the final return as { status: DONE | NEEDS_INPUT | BLOCKED,
  result: ... } plus any open ticket ids. NEEDS_INPUT here is only a status
  value naming the state, never a payload to carry the question itself.
- zakia queries `needs-user` tickets on the board, batches them into one
  AskUserQuestion, writes the answers back onto the tickets, and closes
  them. Closing a question ticket auto-unblocks its dependent work
  (`bd ready` is blocker-aware). The user may also answer tickets directly
  via the `bd` CLI. The Q&A trail on the ticket is a permanent decision log
  that survives rotation, compaction, and new sessions.
- zakia relays the close back to the still-live agent as another one-line
  wake ping (e.g. "answered, see df-12"). Agents remain resumable after
  completion; resume-with-context is verified.

## Planning layers

- zakia does triage and sequencing: what fans out, what serializes.
- Each sub-orchestrator owns its workstream phase plan (may consult Plan /
  big-pickle-simple-tasks / requirements-clarifier).
- Machine coordination (statuses, blocked-by dependencies, atomic claims,
  the decision log) lives on the `bd` board, per project; see "Board
  substrate" below. The harness task board (TaskCreate/TaskUpdate) stays
  only for human-visible top-level progress that zakia surfaces to the
  user; it is not the cross-agent coordination store.

## Board substrate (beads)

- `bd init` once per project (see `scripts/init-agent-workspace.sh`). The
  board is the source of truth for cross-task machine state: statuses,
  `blocked-by` dependencies, atomic claims, and the question/answer log.
- Lazy init: the board is created on demand, never globally and never on
  SessionStart. When a multi-agent workstream begins in a repo with no
  `.beads/` yet, zakia scaffolds it once by running
  `scripts/init-agent-workspace.sh` before delegating, then proceeds. Solo,
  single-session, or one-off work needs no board; do not init for it. This
  doctrine (bubble-up, wake pings, token economy) still loads every session
  via the Read directive regardless; only the BOARD is lazily created.
- Claim work atomically before starting it: `bd update <id> --claim` (sets
  assignee + status=in_progress) so two agents never grab the same ticket.
  `bd ready` returns the blocker-aware ready list.
- Every agent runs `bd` inline itself; board ops never justify spawning a
  dedicated agent (see Token economy below).
- Messages carry pointers (ticket ids, file paths), never payloads;
  artifacts hand off as files in durable dirs, per the hub-and-spoke rule
  above.

## Token economy

Escalate only when the current rung fails:

1. No-LLM: script or CLI (`bd` commands, `scripts/build-kb-index.py` on a
   git hook). Zero model cost.
2. In-context reuse: the owning agent distills its own KB entry before it
   terminates or rotates, while it still holds the workstream context.
3. Cheap model, isolated context: a haiku retrieval sweep
   (`knowledge-scout`) for read-heavy "find everything about X" fan-out
   across KB, board, and code, returning conclusions only.
4. Frontier model: only once 1-3 fail to answer the question.

## Per-project standard shape

```
.beads/         bd board: machine coordination (statuses, deps, claims)
docs/kb/        distilled markdown KB entries (durable, tracked)
workstreams/    per-workstream status.md + artifacts (rebuild point for a
                fresh/compacted zakia)
kb.db           FTS5 index over docs/kb/ now; a vector column may be added
                later only once FTS5 demonstrably misses
```

Scaffolded idempotently by `scripts/init-agent-workspace.sh`.

## KB distillation rule

- The KB is an index over existing sources, never a new silo of raw
  transcripts.
- When a ticket closes or a workstream ends, the OWNING agent (not a
  dedicated distiller) writes one markdown entry to `docs/kb/`: the
  question someone would search for, a short summary, the resolution,
  file/ticket refs, and the date.
- Retrieval is SQLite FTS5 (`scripts/build-kb-index.py` builds `kb.db`) for
  exact-token search, plus grep over `docs/kb/` directly. Add embeddings
  only when FTS5 demonstrably misses; entries + FTS5 + grep is enough for
  now.

## Workspace + tools

- Spike/scratch workspaces live in durable dirs (<project>/spikes/), never
  /tmp. /tmp wipes on reboot and destroys spike artifacts.
- Use the Codebase Memory MCP when possible to traverse codebases.
- Never commit secrets or sensitive information. The dotfiles pre-commit
  gate enforces this there; the rule applies in every repo.
- Engineering-artifact naming (code, commits, specs, diagrams) follows
  ~/.claude/rules/code-naming.md.

## Brief writing (subagent sees ONLY your prompt)

- Fresh context, zero memory. Brief MUST carry: full task context, exact
  paths, error text verbatim, constraints, deliverable spec, success
  criteria. Under-brief -> agent rediscovers what you knew -> thrash.
- Paste a compressed digest of the working method verbatim into EVERY brief.
  Always include the caveman ultra output instruction
  (~/.claude/rules/output.md).
- Code-writing briefs: instruct `ponytail` (YAGNI -> reuse -> stdlib ->
  native -> installed-dep -> one-line -> min; shortest working diff;
  `# ponytail:` comment on corner-cuts).
- Code-writing briefs name the matching language rule file
  (~/.claude/rules/<language>.md, e.g. python.md, gdscript.md) plus
  ~/.claude/rules/code-naming.md, and instruct the agent to Read them
  before writing code in that language.
- Say "return summary/data, not transcript". Return channel = final message
  only. Fat reports -> orchestrator context bloat.

## Model per role

- Sub-orchestrators and vision critics: sonnet (high-res vision tier).
- comfyui-runner and trivial decomposition: haiku.
- Hard reasoning: escalate to the session's top model or the advisor tool.
  The advisor works inside subagents (verified). The Fable-5 advisor is
  currently blocked in Claude Code and returns encrypted results, so any
  advisor producing visible critique verdicts must be Opus 4.8.
  Images-to-advisor is UNVERIFIED pending a probe; until verified, vision
  critique uses plain fan-out vision critics, which work natively.
- Least privilege: read-only tools for research agents.

## Verify, never trust (skeptic gate)

- An implementor never self-certifies. Risky or high-consequence work gets an
  independent challenge check (`skeptic-gate` agent) before ship (PR open /
  integration / merge).
- Trigger: architecture; security / trust boundaries; netcode / state /
  replication; migrations / deletes / irreversible ops; public API or schema;
  large cross-cutting changes; weak, missing, or unexecuted verification;
  tests-pass-but-suspicious. Skip: small mechanical or docs-only edits.
- The gate reads the real diff, not a summary. Read-only. Returns PASS |
  BLOCK | NEEDS_TEST | NEEDS_ARCH_REVIEW | NEEDS_REQUIREMENTS. Non-PASS halts
  delivery until resolved; re-run after fixes.
- Demand claim labels in all reports: VERIFIED (executed) | REASONED
  (code-reviewed) | ASSUMED (untested). Silent upgrade forbidden.
  "Should work" != "works".
- No build/test output quoted -> send back. Gaps -> follow up once with the
  same agent (keeps its context), else respawn with a better brief, then
  escalate up the hierarchy.

## Lifecycle (context rotation)

- Long-running subagent >~250k tokens -> bloated -> quality drops. Watch
  subagent_tokens in task notifications. A bloated agent never self-certifies.
- Rotate via the `rotate-agent` skill: wrap-up (in-flight only) -> handoff
  doc -> verify vs repo -> fresh same-type agent founded on handoff +
  verbatim user directives.
- Handoffs TRANSIENT, never in git history: `docs/handoffs/<agent-role>.md`,
  gitignored (add entry if missing). Successor overwrites. Rotating agent
  MUST report the handoff path to its spawner.
- Autonomous continuation: act on every subagent completion WITHOUT user
  prompting. Verify state, resume stalled agents, spawn successors when
  handoff paths are reported, advance the pipeline. Surface only results +
  decisions genuinely the user's.
