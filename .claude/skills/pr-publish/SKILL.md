---
name: pr-publish
description: Generate per-shard PR publication plan from pipeline.md. Default plan-only JSON. --apply executes git/gh subprocesses. K-agnostic. Graceful branches-only degradation when gh unavailable.
source: pipeline-native
output-style: caveman:ultra
disable-model-invocation: true
---

# pr-publish

Generate per-shard PR publication plan from `pipeline.md` ledger.
Default: plan-only JSON (no subprocess side effects). `--apply` opt-in executes.

## Invocation

```
Claude:  Skill(skill: "pr-publish", args: "pipeline-md=<abs-path>")
OC:      pr-publish --pipeline-md <abs-path> [--apply]
Script:  python3 ~/.claude/skills/pr-publish/pr-publish.py --pipeline-md <abs-path>
         python3 ... --pipeline-md <path> [--apply] [--artifact-id <id>] [--task-summary <str>]
```

## Input

`pipeline.md` path. Parses frontmatter for:
- `run_id`, `base_ref`, `base_sha` — required.
- `shards: { s<K>: {status, branch, worktree, depends_on: [...]} }` — required.
- `brief` — used for PR title; override with `--task-summary`.
- `github_delivery` — pr|branches-only hint.

## Output schema (plan-only)

```json
{
  "mode": "pr" | "branches-only",
  "gh_available": true | false,
  "gh_reason": null | "gh not in PATH" | "gh auth status failed" | "remote not github.com",
  "base_sha": "<sha>",
  "base_ref": "<ref>",
  "base_sha_stable": true | false,
  "shards": [
    {
      "shard_id": "s1",
      "branch": "pipeline/<id>/s1",
      "depends_on": [],
      "commands": {
        "recommit": ["git", "reset", "--soft", "<sha>"],
        "push": ["git", "push", "origin", "..."],
        "pr_create": ["gh", "pr", "create", "..."] | null,
        "pr_merge": ["gh", "pr", "merge", "..."] | null
      },
      "title": "[<id>] <summary>",
      "body_path": null
    }
  ],
  "merge_order": ["s1", "s2"],
  "warnings": []
}
```

Note: NO `merge_order_rank` per shard (C4). Rank implicit: `merge_order.index(shard_id)`.

## Output schema (--apply mode)

JSONL to stdout — one line per action, then a summary line:
```json
{"shard": "s1", "action": "push", "exit": 0, "stdout": "...", "stderr": ""}
{"shard": "s1", "action": "pr_create", "exit": 0, "stdout": "...", "stderr": ""}
{"summary": {"total_shards": 1, "pushed": 1, "pr_opened": 1, "merged": 0, "failed": []}}
```

## Merge order

Computed via Kahn's algorithm over `depends_on` edges. Independent shards first.
Cyclic depends_on → exit 2.

## Exit codes

- `0` — plan-only success OR `--apply` with all actions succeeded.
- `1` — `--apply` with ≥1 action failed (summary line still emitted).
- `2` — pipeline.md missing/malformed, depends_on cycle, K<1, missing required keys.
- `gh` missing/auth-failed → exit 0 + `mode: branches-only`. Not a hard error.

## Notes

- K inferred from `len(shards)` — no constant baked in.
- `base_sha_stable: false` + warning when `git rev-parse <base_ref>` ≠ `base_sha`. Skill
  surfaces; orchestrator decides to abort.
- Frontmatter parser: constrained YAML subset (scalar + one-level nested flow maps/seqs).
  No anchors/aliases/multi-line scalars. Pipeline.md is orchestrator-written — we control input.
- Stdlib only: `argparse`, `json`, `re`, `subprocess`, `sys`, `pathlib`, `shutil`.
