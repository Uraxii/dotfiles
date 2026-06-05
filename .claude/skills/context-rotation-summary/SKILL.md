---
name: context-rotation-summary
description: Local context-rotation summary template. References context-digest and existing artifacts by path, never duplicates brief/design/build-contract content. Used by persistent Claude Code roles at context threshold (architect 70%, all other persistent roles 80%).
source: mattpocock/skills:skills/productivity/handoff/SKILL.md
output-style: caveman:ultra
---

# context-rotation-summary

Local context-rotation summary template. Pipeline-internal. Distinct from Hermes `pipeline-handoff-doc`, which is GitHub/inline delegate handoff.

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

One-shot roles (researcher, plan) do not rotate. Friction audit is a skill, not a spawned role.

## Invocation

Claude: `Skill(skill: "context-rotation-summary", args: "role=<agent>, run-dir=<path>, next-focus=<text>")`

OC: use the local context-rotation tool/skill equivalent with `{role, run_dir, next_focus}` args.

Script: `python3 .claude/skills/context-rotation-summary/handoff-doc.py --role <role> --run-dir <path> --next-focus <text>`

## Args

| Arg | Type | Required | Description |
|-----|------|----------|-------------|
| `--role` | str | yes | Role name (e.g. `architect`, `build`) |
| `--run-dir` | path | yes | Pipeline run directory |
| `--next-focus` | str | yes | What the next session should do first |

## Returns

Writes `<run-dir>/context-rotation-<role>-<YYYYMMDDTHHMMSSz>.md`; prints absolute path to stdout. Summary must cite `context-digest.md` and artifact paths; no copied full brief/design/build-contract.

## Exit codes

- 0: success
- 1: run-dir not found

## See also

`pipeline-verdict-parse`.
