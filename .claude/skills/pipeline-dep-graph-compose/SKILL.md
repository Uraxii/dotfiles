---
name: pipeline-dep-graph-compose
description: Compose ordered role execution graph for a pipeline run. Emits ordered_roles array + decision inject points as JSON. K-agnostic.
source: pipeline-native
output-style: caveman:ultra
disable-model-invocation: true
---

# pipeline-dep-graph-compose

Compose role execution order (topological sort over dependency edges) for a pipeline run.
Returns ordered role list + decision inject points as JSON to stdout.

## Invocation

```
Claude:  Skill(skill: "pipeline-dep-graph-compose", args: "payload-json=<json-blob>")
OC:      pipeline-dep-graph-compose --payload <json-blob>
Script:  python3 ~/.claude/skills/pipeline-dep-graph-compose/dep-graph-compose.py --payload <json>
         python3 ~/.claude/skills/pipeline-dep-graph-compose/dep-graph-compose.py --payload-file <path>
```

## Input schema

```json
{
  "brief_path": "<abs>",
  "plan_path": "<abs|null>",
  "roles_declared": ["architect", "build", "skeptic-design"],
  "roles_skipped": {"researcher": "scope known"},
  "decision_points": {"d1": {"after": "architect", "delivery": "sync"}},
  "design_handoff": "required|n/a",
  "ui_scope": false,
  "ops_scope": false,
  "code_change": true,
  "K": 1
}
```

Required keys: `brief_path`, `roles_declared`, `roles_skipped`, `decision_points`,
`design_handoff`, `ui_scope`, `ops_scope`, `code_change`, `K`.

`K` must be a positive integer. Cap (K≤8) is orchestrator-side policy — not enforced here.

## Output schema

```json
{
  "ordered_roles": [
    {
      "role": "architect",
      "depends_on_roles": [],
      "loop_cap": 3,
      "revision_loop_kind": "design|code|ops|none",
      "spawn_when": "phase-2-step-1",
      "persistent": true,
      "verdict_file_glob": "verdict-design-r*.md"
    }
  ],
  "decision_inject_points": [
    {"after_role": "architect", "decision_id": "d1", "delivery": "sync"}
  ],
  "K": 1,
  "warnings": []
}
```

## Exit codes

- `0` — valid input; JSON to stdout.
- `2` — malformed payload, missing required keys, K<1.
- `1` — unhandled crash (stderr trace).

## Notes

- Roles not in internal meta table → treated as leaf node (no deps, loop_cap 1, no verdict glob).
  Warnings array populated.
- `--payload-file <path>` escape hatch for long payloads.
- Stdlib only: `argparse`, `json`, `sys`, `pathlib`.
