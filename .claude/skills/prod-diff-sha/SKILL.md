---
name: prod-diff-sha
description: Compute SHA1 of production-code diff vs base_sha, excluding test paths. Used by orchestrator for test-only revision pin validation on skeptic-code/reviewer/security verdicts.
source: pipeline-native
output-style: caveman:ultra
---

# prod-diff-sha

Compute prod-code diff SHA. Pipeline-internal.

## Invocation

Claude: `Skill(skill: "prod-diff-sha", args: "base-sha=<sha>, head=<ref|HEAD>, test-paths-file=<path|none>")`

OC: `prod-diff-sha` custom tool with `{base_sha, head, test_paths_file}` args.

## Algorithm

```bash
# Build :!<glob> excludes from test-path-resolve default or test-paths.txt
EXCLUDES=""
for glob in $TEST_GLOBS; do
  EXCLUDES="$EXCLUDES :!${glob}"
done

# Diff prod-only
PROD_DIFF=$(git diff <base-sha> <head> -- $EXCLUDES)

# SHA1
prod_diff_sha=$(printf '%s' "$PROD_DIFF" | sha1sum | cut -c1-40)
```

Empty diff → returns `0000000000000000000000000000000000000000`.

## Returns

40-char hex SHA string.
