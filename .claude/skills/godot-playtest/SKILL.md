---
name: godot-playtest
description: Drive a running Godot game through godot-mcp (freeze clock, step time, inject input, read live state JSON) to verify a change actually works, then fix what breaks. Inner dev loop, per change, minutes. Use when the user says "playtest this", "verify in-game", "does this work when played", or after any gameplay-affecting change in a Godot project. Not for full demo evaluation (use demo-video-capture + demo-video-judge).
---

# godot-playtest

Purpose: replace "tests pass, ship it" with "I played it and watched it
work". State JSON answers most questions; screenshots only for visual
questions (vision tokens are the expensive path).

## Preconditions

1. godot-mcp tools reachable: `ToolSearch` for `godot` tools. If absent,
   STOP and tell the user to run:
   - `claude mcp add --scope user godot-mcp -- npx -y @satelliteoflove/godot-mcp`
   - `npx @satelliteoflove/godot-mcp --install-addon <godot project dir>`
   - Enable Project Settings > Plugins > Godot MCP, editor open.
   Addon speaks WebSocket on 127.0.0.1:6550; Godot 4.5+; Node 20+.
2. nikki-net repo rule (project CLAUDE.md): playtest scenes are thin
   harnesses on REAL services. `Net.host()` for single player, spawn via
   `ActorService.spawn`, never `OfflineMultiplayerPeer`, never direct
   actor instancing, never mutating server state to fake a scenario.

## Loop

1. State the claim being verified as one sentence ("client capsule moves
   under host integration with X input"). No claim, no playtest.
2. Run the scene. Freeze the game clock.
3. Arrange: GDScript-execution tool for setup that a player could reach
   legitimately; inject inputs through ACTIONS (the real input path),
   not by setting positions.
4. Act: step exact time slices (or step-until-condition). Deterministic:
   same seed + same steps = same result; record the step script in the
   session notes so a failure reproduces.
5. Observe: live state JSON (positions, velocities, animation state,
   custom watches, signal timeline). Assert against the claim with real
   numbers, not "looks fine".
6. Screenshot ONLY for visual claims (UI shown, VFX fired, style).
7. Fail -> fix code -> repeat from 2. Pass -> report: claim, steps,
   observed values, and any incidental oddity noticed (file it, do not
   silently fix out-of-scope).

## Multiplayer claims

One editor instance = one MCP client. For host+client claims, run the
second instance headless from CLI and observe it via logs/state dumps,
or use demo-video-capture's paired capture. Never fake the second peer.
