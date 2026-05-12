---
name: prod-diff-sha
description: Compute SHA1 of production-code diff vs base_sha, excluding test paths. Used by orchestrator for test-only revision pin validation on skeptic-code/reviewer/security verdicts.
disable-model-invocation: true
source: pipeline-native
output-style: caveman:ultra
---

# prod-diff-sha

Compute prod-code diff SHA. Pipeline-internal. Used by orchestrator gate-pin mechanism (test-only revision path).

## Invocation

```
Skill(skill: "prod-diff-sha", args: "base-sha=<sha>, head=<ref|HEAD>, test-paths-file=<path|none>")
```

## Algorithm

```bash
# Determine test-path globs
if test -f <test-paths-file>; then
  TEST_GLOBS=$(cat <test-paths-file>)
else
  TEST_GLOBS=$(Skill(skill: "test-path-resolve") default set)
fi

# Build pathspec excludes
EXCLUDES=""
for glob in $TEST_GLOBS; do
  EXCLUDES="$EXCLUDES :!${glob}"
done

# Diff prod-only
PROD_DIFF=$(git diff <base-sha> <head> -- $EXCLUDES)

# SHA1
prod_diff_sha=$(printf '%s' "$PROD_DIFF" | sha1sum | cut -c1-40)
```

`printf '%s'` strips trailing newline — apply identically at write + validate.

## Sentinel

Empty diff → sentinel SHA `0000000000000000000000000000000000000000` (cannot collide w/ non-empty sha1sum).

## Pin validation (caller)

Orchestrator stores `prod_diff_sha` in last-Approved-verdict frontmatter. On test-only revision:
1. Read pinned SHA from verdict
2. Recompute current
3. Equal → pin valid; skip gate; carry forward verdict
4. Mismatch → pin INVALIDATED; treat as new code-loop revision; re-fire pinned gates

## Don't

- No write. Read-only computation.
- No git mutation.
- No hunk-level analysis (filename-level filtering only; accepted hole).
