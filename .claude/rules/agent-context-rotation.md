# Agent Context Rotation (all projects)

- Any long-running subagent >~250k tokens → bloated → rotate. Watch
  subagent_tokens in task notifications. Orchestrators watch own
  specialists same way.
- Rotate via `rotate-agent` skill: wrap-up (in-flight only) → handoff
  doc → verify vs repo → fresh same-type agent founded on handoff +
  verbatim user directives.
- Handoffs TRANSIENT, never in git history: `docs/handoffs/<agent-role>.md`,
  gitignored (add entry if missing). Never commit. Successor overwrites.
- Rotating agent MUST report handoff path to spawner in final message.
  Spawner points successor's founding brief at that exact path.
- Spawner enforces rotation. Bloated agent never self-certifies.
