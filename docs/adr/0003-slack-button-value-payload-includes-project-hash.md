# ADR-0003 — Slack button value payload includes project path hash

Date: 2026-05-14
Status: Accepted
Run: clever-finding-canyon-113225
Related design: `.pipeline/runs/clever-finding-canyon-113225/design.md` §7.2, §7.4

## Context

The Slack router (`slack_router.py`) routes button clicks from Slack back to
the correct pipeline run directory. Button click payloads must identify:

1. Which run directory to write the artifact into.
2. Which question or decision within that run was answered.
3. Which option was chosen.

The prior payload format was `<run-id>|<qd-id>|<choice>`.

**Problem**: `run-id` values are human-readable artifact slugs (e.g.
`clever-finding-canyon-113225`). On a host running multiple projects, two
different projects could independently produce the same run-id. Because the
router maintains a global run-index keyed by `run-id`, a click on a button
from project A could silently write an artifact into project B's run
directory if both happened to use the same slug.

This was identified as a blocking defect (B2) during design review r1.

## Decision

Embed an 8-character hex prefix of `sha1(project_path_str)` in the button
value, making the full format:

```
<phash8>|<run-id>|<qd-id>|<choice>
```

Example (using a symbolic project path):

```
7c2a4f91|clever-finding-canyon-113225|q1|A
```

Where `phash8 = sha1("<project-path>")[:8]` (lowercase hex).

The router's run-index stores the same `project_path_hash` alongside the
`run_dir`. On click, the router compares the button's `phash8` against the
index entry. Mismatch → ephemeral toast "Stale or cross-project click" +
drop; no artifact written.

## Consequences

### Positive

- Eliminates silent cross-project artifact misrouting. Worst case on hash
  collision (birthday bound ~65k projects) is a stale-click toast, not
  corruption.
- Self-describing: operators reading logs can identify which project a button
  payload originates from.

### Negative

- Format is not reversible: every button posted in the wild carries the
  format. Changing it would break in-flight buttons.
- Slightly non-obvious to readers unfamiliar with this ADR (why is there a
  hash in the payload?). This ADR documents that.
- `phash8` birthday collision (two distinct projects share same 8-char hex
  prefix AND the same run-id simultaneously) still allows misrouting.
  Probability ≈ 1 / (65536 × 16M) — vanishing at any plausible scale.

## Alternatives considered

### Alt-A: Run-index list scan

Router could scan all run-index entries for matching `run_dir` content.
O(N) per click, locks index during scan, and still does not prevent a race
where two entries share the same key. **Rejected.**

### Alt-B: Accept silent corruption

Unacceptable; violates artifact integrity. **Rejected.**

### Alt-C: Full `sha256(project_path)` in payload

64 chars; Slack 2000-char button value limit is easily consumed by long
project paths with many concurrent decision options. 8 chars provides
sufficient discrimination at practical scale. **Rejected.**

## References

- design.md §7.2 — payload format + length budget
- design.md §7.4 — multi-project collision behavior
- `verdict-design-r1.md` blocker B2 — original defect report
