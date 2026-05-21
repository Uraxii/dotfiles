---
name: friction-audit
description: Deterministic post-run audit of pipeline doctrine adherence. Emits findings list (non-gating, meta-only). Used by orchestrator at end of code-changing runs to capture process drift for pipeline improvement. Does NOT gate PR merge.
source: pipeline-native
output-style: caveman:ultra
disable-model-invocation: true
---

# friction-audit

Pipeline post-run doctrine audit. Pipeline-internal. **Non-gating** — output is meta-findings for pipeline improvement, not a PR-merge gate.

## Invocation

Claude: `Skill(skill: "friction-audit", args: "run-dir=<path>")`

OC: `friction-audit` custom tool with `{run_dir}` arg.

## Algorithm

```bash
python3 ~/.claude/skills/friction-audit/friction-audit.py --run-dir <path>
```

Returns JSON: `{passed: [<check-id>, ...], failed: [{check: <id>, citation: <path-or-detail>, severity: low|med|high}, ...]}`.

## Checks performed

| Check ID | What | Method |
|---|---|---|
| `agent-brief-format` | brief.md follows AGENT-BRIEF template | regex on frontmatter + required sections |
| `two-axis-review` | Both `verdict-review-standards-r<N>.md` + `verdict-review-spec-r<N>.md` exist when review ran | file existence |
| `tdd-evidence` | build-evidence-*.md shows red-green sequence OR `TDD: skipped, reason:` note | grep |
| `adr-assertion` | architect verdict frontmatter has `adr_emitted:` key | frontmatter parse |
| `task-id-continuity` | pipeline.md ledger records task_id field on persistent roles | YAML parse |
| `phase-field` | pipeline.md has `phase:` field (PR-5+ check; gracefully no-ops if absent) | YAML parse |
| `preflight-critique` | All verdict files contain `## Pre-emit critique` section per agent-preflight doctrine | grep |
| `skill-invocation` | Skills referenced in agents are actually invoked (no inline duplication regression) | grep agent files for `Skill(skill: ` patterns + cross-ref skills dir |

## Output

JSON to stdout. Caller (orchestrator) writes to `<run-dir>/friction-findings-r<N>.md`.

## Semantics

- **No verdict.** No Approved/Blocked.
- **No re-spawn.** Skill is one-shot per run.
- **No gate.** Findings inform pipeline improvement; merge proceeds regardless.
- **No judgment-required lane.** Strict binary pass/fail per check.

## Non-zero exit

Only on invocation error (missing run-dir, malformed args). Findings themselves never cause non-zero exit.

## See also

- Retired: `agents/friction-reviewer.md` (historical doctrine reference)
- Findings consumer: orchestrator (writes `friction-findings-r<N>.md`)
