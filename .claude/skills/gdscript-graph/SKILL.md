---
name: gdscript-graph
description: GDScript codebase knowledge graph — find callers, trace inheritance, search structure. Use when the user asks about GDScript code relationships (who calls X, what inherits from Y, where is Z used), wants to explore Godot project structure, or asks broad "how does X work" questions that span multiple .gd files. Trigger: /gdgraph
---

<what-to-do>

When the user types `/gdgraph` or asks a GDScript structural question (callers, inheritance, dependencies, "how is X wired"), use the `graphify-gdscript-build` and `graphify-gdscript-query` CLI tools to answer it from the knowledge graph.

First-run: if `graphify-out/gdscript-graph.pkl` doesn't exist or is stale, build it:

```bash
graphify-gdscript-build --dir src/ --output graphify-out/gdscript-graph.pkl
```

For queries, always use `--json` and pipe to a Processing block for readable output:

```bash
graphify-gdscript-query --json <command> <args...>
```

Never grep source files for structural questions that the graph can answer. The graph is faster (milliseconds vs scanning 576 files) and captures relationships grep can't see (inherited methods, call graphs, signal wiring).

</what-to-do>

<supporting-info>

## Install

```bash
uv pip install "graphifyy @ git+https://github.com/Uraxii/graphify.git@v1" --no-deps
uv pip install networkx tree-sitter \
  "tree-sitter-gdscript @ git+https://github.com/PrestonKnopp/tree-sitter-gdscript.git"
```

## Build

```bash
graphify-gdscript-build --dir src/ --output graphify-out/gdscript-graph.pkl
```

Output: pickled NetworkX DiGraph. Build takes ~2 seconds on bhwf (576 .gd files).

## Query commands

All output is JSON. Add `--json` for explicit JSON mode.

| Command | Args | Description |
|---------|------|-------------|
| `stats` | — | Node/edge counts, edge type breakdown |
| `node` | `<name-or-id>` | All incoming/outgoing edges for a node |
| `callers` | `<func-name>` | Who calls this function? (INFERRED call-graph edges) |
| `callees` | `<func-name>` | What does this function call? |
| `inherits` | `<class-name>` | Full inheritance chain upward |
| `children` | `<class-name>` | What classes inherit FROM this class? |
| `god-nodes` | `[N]` | Top-N highest-degree nodes (default 10) |
| `search` | `<term>` | Substring search on node labels (ordered by degree) |
| `path` | `<src> <dst>` | Shortest path through any edge between two nodes |
| `depends` | `<name-or-id>` | Preload/load targets (outgoing depends_on) |
| `dependents` | `<name-or-id>` | What depends on this? (incoming depends_on) |
| `signals` | `<class-name>` | List signal declarations of a class |
| `methods` | `<class-name>` | List methods of a class |
| `classes` | — | All class_name classes with inherit + method counts |
| `orphans` | — | Nodes with zero edges |

Custom graph path: `--graph /path/to/graph.pkl`

## Edge types captured

| Relation | Confidence | Source |
|----------|-----------|--------|
| `class_name` | EXTRACTED | `class_name Foo` at file scope |
| `inherits` | EXTRACTED | `extends Bar` |
| `method` | EXTRACTED | `func name()` inside a class |
| `calls` | INFERRED | Cross-function calls within a file (call-graph pass) |
| `signal` | EXTRACTED | `signal name` |
| `contains` | EXTRACTED | Inner `class` / `enum` bodies |
| `depends_on` | EXTRACTED | `preload("res://...")` / `load("res://...")` |

## Worked examples

```
User: "Who calls play_ability_sfx?"
/gdgraph query callers play_ability_sfx
→ 5 callers in player_entity.gd: _on_ability_windup_started, _on_ability_active_started, ...

User: "What inherits from Component?"
/gdgraph query children Component  
→ 16 classes: MovementComp, HealthComp, StatusComp, ...

User: "Find everything related to movement"
/gdgraph query search movement
→ 51 matches: movement_system.gd, MovementComp, test_player_movement, ...
```

## Scale

Verified on bhwf (Godot 4.6, 576 .gd files): 6,393 nodes, 8,504 edges, 0 parser errors.

</supporting-info>
