# CLAUDE

## Instructions

- Include local file paths in repos files.
- Prevent commits containing secrets or sensative information.
- Responses < 100 ln.
- Prefer visuals and diagram for complex information.
- READMEs = human doc + instructions. No clutter with inforation for agents.
- No emmdashes, ever.
- Use Codebase Memory MCP when possible to traverse codebases.
- Output style: caveman ultra, all agents (`rules/caveman.md`).
- Writing code = delegate to subagent w/ ponytail + caveman brief. Never
  hand-write code on main thread. (Orchestration doctrine baked into
  `agents/zakia.md` + `agents/tech-lead.md`.)

## Godot

Managed by a flatpak called 'Godots'.

- GODOT_ROOT -> ~/.var/app/io.github.MakovWait.Godots/data/godot/app_userdata/Godots/versions
- Godot 4.6 = GODOT_ROOT/Godot_v4_6-stable_linux_x86_64/Godot_v4.6-stable_linux.x86_64
