---
name: memory-write
description: DEPRECATED. Pipeline no longer writes memory files. Agents do not invoke this skill.
disable-model-invocation: true
source: pipeline-native
output-style: caveman:ultra
---

# memory-write (DEPRECATED 2026-05-13)

Pipeline no longer maintains per-role memory files. Agents do not invoke this skill.

Lessons that warrant durable persistence are surfaced in verdict Notes / friction-report. User decides how to capture them (project doctrine, agent spec edits, code comments, ADRs).

Skill file retained for rollback only. Do not invoke from any agent.
