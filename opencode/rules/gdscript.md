# GDScript Rules

- Type hints: all vars, params, returns. Static typing mode on.
- `@onready` over `_ready()` assignment for node refs.
- Signal connections: prefer `connect()` in code over editor (auditable).
- No `get_node("../../..")` chains. `@export` node paths or use groups.
- `_process` / `_physics_process`: guard w/ early return if inactive.
- Resource preload: `const` + `preload()`, not runtime `load()`.
- State machines: enum + match, not boolean soup.
- `await` for async (Godot 4). No deprecated `yield`.
- Null-check before scene tree access. Freed nodes = crash.
- Signals over direct method calls for decoupled communication.
- `class_name` on reusable scripts. Skip for one-off scene scripts.
- `StringName(&"...")` for frequent lookups (input actions, anims).
- No `get_tree().get_nodes_in_group()` in `_process` — cache result.
- `@export` over `_ready()` param injection for inspector-configurable values.
- `is_instance_valid()` before accessing refs that may be freed.
