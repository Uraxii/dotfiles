---
name: handoff-doc
description: Compact persistence-rotation summary template. References existing artifacts by path, never duplicates content. Used by any persistent role at context threshold (architect 70%, all other persistent roles 80%).
source: mattpocock/skills:skills/productivity/handoff/SKILL.md
output-style: caveman:ultra
---

# handoff-doc

Persistence-rotation summary template. Pipeline-internal.

## Per-role thresholds

| Role | Threshold | task_id key |
|---|---|---|
| architect | 70% | role |
| build | 80% | (role, shard_id) |
| skeptic | 80% | (role, review_type) |
| reviewer | 80% | (role, axis) |
| security-auditor | 80% | (role, review_type) |
| tester | 80% | role |
| ui-ux-designer | 80% | role |
| content-designer | 80% | role |

One-shot roles (researcher, plan, friction-reviewer) do not rotate.

## Invocation

Claude: `Skill(skill: "handoff-doc", args: "role=<agent>, run-dir=<path>, next-focus=<text>")`

OC: `handoff-doc` custom tool with `{role, run_dir, next_focus}` args.

Script: `python3 .claude/skills/handoff-doc/handoff-doc.py --role <role> --run-dir <path> --next-focus <text>`

## Args

| Arg | Type | Required | Description |
|-----|------|----------|-------------|
| `--role` | str | yes | Role name (e.g. `architect`, `build`) |
| `--run-dir` | path | yes | Pipeline run directory |
| `--next-focus` | str | yes | What the next session should do first |

## Returns

Writes `<run-dir>/handoff-<role>-<YYYYMMDDTHHMMSSz>.md`; prints absolute path to stdout.

## Exit codes

- 0: success
- 1: run-dir not found

## See also

`verdict-parse`.
