# Agent Context Rotation Rule (all projects)

- A long-running delegate agent (tech-lead or any orchestrator) whose
  context exceeds ~250k tokens is bloated and must be rotated. Watch
  the subagent token usage reported in task notifications.
- Rotate via the `rotate-agent` skill: wrap-up order (finish in-flight
  only) -> committed handoff doc -> verify against repo -> fresh agent
  of the same type founded on the handoff + verbatim user directives.
- The main session agent enforces this; the bloated agent does not
  self-certify the rotation.
