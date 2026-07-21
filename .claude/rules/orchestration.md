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

- Mid-flight: SendMessage to "main" with a NEEDS_INPUT payload (question +
  options + context), then keep working on independent parts meanwhile.
- Terminal: shape the final return as
  { status: DONE | NEEDS_INPUT | BLOCKED, questions: [...], result: ... }.
- zakia batches pending questions into one AskUserQuestion and delivers the
  answers back via SendMessage to the still-live agent. Agents remain
  resumable after completion; resume-with-context is verified.

## Planning layers

- zakia does triage and sequencing: what fans out, what serializes.
- Each sub-orchestrator owns its workstream phase plan (may consult Plan /
  big-pickle-simple-tasks / requirements-clarifier).
- The shared task board (TaskCreate/TaskUpdate) is the cross-agent source of
  truth for work state; plans live as tracked tasks.

## Workspace + tools

- Spike/scratch workspaces live in durable dirs (<project>/spikes/), never
  /tmp. /tmp wipes on reboot and destroys spike artifacts.
- Use the Codebase Memory MCP when possible to traverse codebases.
- Never commit secrets or sensitive information. The dotfiles pre-commit
  gate enforces this there; the rule applies in every repo.

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
  (~/.claude/rules/<language>.md, e.g. python.md, gdscript.md) and instruct
  the agent to Read it before writing code in that language.
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
