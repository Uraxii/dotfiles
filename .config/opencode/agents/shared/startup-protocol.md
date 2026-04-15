# Startup Protocol

Execute before role-specific reads. `<ROLE>` = your agent name. `<TASK>` = assigned task ID.

## Compression

Agent<->Agent: caveman:wenyan-ultra.
Agent<->User: caveman:ultra.

## Memory

1. `~/.config/opencode/memory/core-memory.md`
2. `~/.config/opencode/memory/<ROLE>-memory.md`
3. `<project>/.opencode/memory/core-memory.md`
4. `<project>/.opencode/memory/<ROLE>-memory.md`

## Inbox

5. Process global inbox: `~/.config/opencode/inbox/<ROLE>/<TASK>/unread/*.yaml` + `general/unread/*.yaml`
6. Process project inbox: `<project>/.opencode/inbox/<ROLE>/<TASK>/unread/*.yaml` + `general/unread/*.yaml`

Per msg: read → act → persist if needed → delete. Sort: critical → high → normal → low, oldest first. Schema in `shared/communication-mode.md`.

Then role-specific reads.
