# CLAUDE

## Instructions

- Include local file paths in repos files.
- Prevent commits containing secrets or sensative information.
- Prefer visuals and diagram for complex information.
- READMEs = human doc + instructions. No clutter with inforation for agents.
- Use Codebase Memory MCP when possible to traverse codebases.
- Output rules (style + terseness), all agents: @rules/output.md
- Writing code = delegate to subagent w/ ponytail + caveman brief. Never
  hand-write code on main thread. (Orchestration doctrine:
  `.claude/rules/orchestration.md`.)

## Godot

Managed by a flatpak called 'Godots'.

- GODOT_ROOT -> ~/.var/app/io.github.MakovWait.Godots/data/godot/app_userdata/Godots/versions
- Godot 4.6 = GODOT_ROOT/Godot_v4_6-stable_linux_x86_64/Godot_v4.6-stable_linux.x86_64
