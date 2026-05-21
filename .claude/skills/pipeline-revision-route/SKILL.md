---
name: pipeline-revision-route
description: Map a verdict file to its next pipeline action (respawn/approved/halt). Keys on (review_type, role) tuple. Drift-guards against orchestrator.md Revision Loop table on every invocation.
source: pipeline-native
output-style: caveman:ultra
disable-model-invocation: true
---

# pipeline-revision-route

Route a gate verdict to the next pipeline action. Emits JSON to stdout.
Validates internal ROUTING_TABLE against orchestrator.md Revision Loop table
on every invocation (drift guard — exits 2 on mismatch).

## Invocation

```
Claude:  Skill(skill: "pipeline-revision-route", args: "verdict-path=<abs-path>")
OC:      pipeline-revision-route --verdict-path <abs-path>
Script:  python3 ~/.claude/skills/pipeline-revision-route/revision-route.py --verdict-path <abs-path>
         # Testing override:
         python3 ... --verdict-path <path> --orch-path <alt-orchestrator.md>
```

## Input

Verdict markdown file with YAML frontmatter containing:
- `verdict`: `Approved` | `Conditional` | `Blocked`
- `role`: issuing role (e.g. `architect`, `skeptic-code`, `tester`)
- `review_type`: `design` | `code` | `ops` | `review` | `test-audit`
- `revision`: `r<N>`
- `loops`: current loop count (integer)

## Output schema

```json
{
  "action": "approved" | "respawn" | "halt",
  "target_role": "architect" | "build" | "tester" | null,
  "revision_n": 2,
  "reason": "verdict=Blocked, (design, architect) → respawn architect r2",
  "loop_cap_hit": false,
  "verdict_summary": {
    "review_type": "design",
    "role": "architect",
    "verdict": "Blocked",
    "current_loops": 1,
    "loop_cap": 3
  }
}
```

## Routing table

| `(review_type, role)` | verdict | action | target |
|----------------------|---------|--------|--------|
| (design, architect) | Blocked | respawn | architect (cap 3) |
| (design, architect) | Approved/Conditional | approved | — |
| (code, skeptic-code) | Blocked | respawn | build (cap 3) |
| (ops, skeptic-ops) | Blocked | respawn | build (cap 1) |
| (review, reviewer) | Blocked | respawn | build (cap 3) |
| (code, security-auditor) | Blocked | respawn | build (cap 3) |
| (design, security-auditor) | Blocked | respawn | architect (cap 3) |
| (test-audit, tester) | Blocked | respawn | tester (cap 3) |
| any | cap hit | halt | null |

## Exit codes

- `0` — valid verdict; JSON to stdout.
- `2` — verdict file missing/unreadable; malformed frontmatter; verdict value not in enum;
  `(review_type, role)` not in ROUTING_TABLE; orchestrator.md table drift detected.
- `1` — unhandled crash.

## Drift guard (C3/C5)

`_assert_table_sync()` runs on every invocation. Reads orchestrator.md from
`Path(__file__).resolve().parents[2] / "agents" / "orchestrator.md"` (symlink-stable).
Mismatch → `sys.stderr.write(msg); sys.exit(2)` — not `sys.exit(msg)` (exit-1 trap).

## Notes

- K never appears in input or logic — skill operates per-verdict.
- `Conditional` treated as approved; orchestrator verifies `## Conditions` section.
- Stdlib only: `argparse`, `json`, `re`, `sys`, `pathlib`.
