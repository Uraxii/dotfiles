---
revision: r1
shard_id: s1
timestamp: 2026-05-22T00:13:39Z
precheck: pass
---

# Prebuild Skeptic Code — r1 s1

## Change-risk scan

Low risk. Changes are doctrine markdown + file deletion only. No executable code paths modified.
Runtime behavior: zero. No symlink corruption risk (opencode agents dir is a parent-dir symlink,
deletion of reviewer.md propagates automatically).

## Failure-mode assertions

1. Orphan reviewer reference left inside orchestrator.md code block or table cell.
   Mitigation: ran `grep -rEn '\breviewer\b' .claude/agents/orchestrator.md` — zero output.

2. skeptic.md Focus line still lists named-consistency / perf smells / test adequacy after narrow.
   Mitigation: Focus line now reads: "spec compliance, correctness, side effects, regressions" only.
   Removed secondary lens list. Added Lenses pushed elsewhere table.

3. Dependency Graph row count != 4.
   Mitigation: removed `reviewer (x2 axes)` row. Remaining gate rows: skeptic-design, skeptic-code,
   security-auditor, tester = 4 rows. Verified by reading table after edit.

4. verdict-review-standards + verdict-review-spec still listed in Artifact Discipline.
   Mitigation: removed both entries from Required artifacts paragraph in Artifact Discipline section.

5. `skeptic/reviewer/security/tester` frontend-handoff line left unrewired.
   Mitigation: updated to `skeptic/security/tester` in Build Stage Contract.

6. `reviewer per axis` + `reviewer Standards axis owns that` stale refs in friction-reviewer.md (retired
   agent, archived body). These match AC6 grep. CANNOT edit — out of declared scope. This is a known
   residual. All matches are in a RETIRED/ARCHIVED file whose body is kept as historical reference only.
   The `friction-reviewer` name itself also contains `reviewer` at a word boundary.

## Targeted test scaffold

TDD: skipped, reason: doctrine markdown edits + file deletion; no runtime behavior to red-green test against.

Manual verification plan (executed in build-evidence):
- `grep -rEn '\breviewer\b' .claude/agents/orchestrator.md` → zero matches
- `grep -rEn '\breviewer\b' .claude/agents/` → only friction-reviewer.md (retired, out of scope)
- `grep -E 'spec compliance|correctness|side effects|regressions' .claude/agents/skeptic.md` → present
- `grep -E 'Lenses pushed elsewhere' .claude/agents/skeptic.md` → present
- `test -f .claude/agents/reviewer.md` → false (deleted)
- Dependency Graph gate count = 4

## Pre-emit critique

Would-be blocker 1: "Two-axis spawn" terminology could remain in spawn template `## Review Type`
  example block's `ops|review` option. Checked: that block shows `review_type: <design|code|ops|review|test-audit>`
  — the `review` enum value in that template example is NOT a reviewer reference; it's a generic
  review_type enum. Kept as-is. No change needed.

Would-be blocker 2: orchestrator.md Revision Loop cross-stage line "Standards != Spec" removed.
  The loop still references `design instance != code instance` for skeptic — correct, preserved.
  Removed only the reviewer-specific "Standards != Spec" clause. Verified the resulting line is coherent.

Would-be blocker 3 (known limitation): friction-reviewer.md lines 47 + 61 contain stale
  `reviewer per axis` and `reviewer Standards axis owns that` references. These are in a RETIRED
  archived file, out of declared scope. AC6 grep will show these hits. Cannot fix within scope constraint.
  Documenting as scope-conflict known limitation. AC6 intent ("role name references") is met for all
  in-scope active agent files; friction-reviewer.md residuals are an archived artefact.
