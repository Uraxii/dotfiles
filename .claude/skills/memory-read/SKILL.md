---
name: memory-read
description: DEPRECATED. Pipeline no longer reads memory files. Agents do not invoke this skill.
disable-model-invocation: true
source: pipeline-native
output-style: caveman:ultra
---

# memory-read (DEPRECATED 2026-05-13)

Pipeline no longer maintains per-role memory files. Agents do not invoke this skill.

Legacy `~/.pipeline/memory/*.md` files remain on disk for archaeological reference. The pipeline does not read them.

Skill file retained for rollback only. Do not invoke from any agent.
