# CLAUDE

## Instructions

- Include local file paths in repos files.
- Prevent commits containing secrets or sensative information.
- Responses < 100 ln.
- Prefer visuals and diagram for complex information.
- READMEs = human doc + instructions. No clutter with inforation for agents.
- No emmdashes, ever.
- Use Codebase Memory MCP when possible to traverse codebases.
- ALL agents (main + every subagent) use caveman ultra output style (see
  `caveman` skill: drop articles/filler, abbreviate, arrows for causality).
  Technical terms, paths, code, commands stay exact. Code/commits/PRs/docs
  for humans written normal. Include this instruction in subagent briefs.

## Godot

Managed by a flatpak called 'Godots'.

- GODOT_ROOT -> ~/.var/app/io.github.MakovWait.Godots/data/godot/app_userdata/Godots/versions
- Godot 4.6 = GODOT_ROOT/Godot_v4_6-stable_linux_x86_64/Godot_v4.6-stable_linux.x86_64
