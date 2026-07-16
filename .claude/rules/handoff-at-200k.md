# Handoff At ~200k Rule (main session, all projects)

- When the main session's context reaches ~200k tokens (context/usage
  warnings, statusline, or clear long-session signals), stop starting
  new work at the next natural stopping point.
- Ask the user (AskUserQuestion if available): "Context ~200k. Write a
  handoff doc and close this session?" Do not just keep going.
- If yes: invoke the `handoff` skill, then report the generated
  `/tmp/handoff-*.md` path as the FIRST line of the final message so it
  is easy to paste into a fresh session. Then wrap up; no new work.
- If no: continue, but re-offer roughly every additional ~50k tokens.
- Never silently rely on auto-compact instead of offering a handoff;
  compaction loses directives.
- Scope: main-thread sessions only. Subagents follow the orchestrator's
  context rotation policy (~250k -> rotate via `rotate-agent`) and
  report to their spawner, not the user.
