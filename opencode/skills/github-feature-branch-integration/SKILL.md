---
name: github-feature-branch-integration
description: Project-local GitHub feature/integration branch workflow for coordinating worker PRs, issue comments, and final main-target PRs. Keep this skill in the working repo because branch topology, review gates, and status conventions are project-specific.
---

# GitHub feature-branch integration

Use when coordinating multi-issue milestone work where worker PRs target a feature/integration branch and one final PR targets `main`.

## Scope

This is a project-local skill. Do not copy its rules into global agent policy unless a user explicitly asks. Each repo may define different branch names, review-bot behavior, project statuses, issue-link rules, and verification gates.

## Flow

1. Read project instructions first: `AGENTS.md`, repo docs, active issue/PR bodies, and any current handoff.
2. Verify live GitHub state before acting:
   - issue status and labels
   - existing branch/PR topology
   - Project status when a Project is used
   - latest PR checks/reviews/comments
3. Create or continue one feature/integration branch from current `main`.
4. Keep worker PRs as draft PRs targeting the feature branch, not `main`, unless this repo says otherwise.
5. Split worker lanes by low-collision boundaries. Identify shared seams before delegation: service/router/config/test runner/scene entrypoints/resources.
6. Require worker GitHub communication:
   - issue kickoff comment before coding: scope, branch, files, verification plan
   - material progress/blocker comments on issue
   - narrow draft PR linked to the issue
   - PR body with issue link, files changed, verification command/output, risks/blockers
   - PR status comment when opened and when material status changes
   - final/block comment on issue with PR link and verification result
7. Integrate worker branches into the feature branch in dependency order.
8. Resolve conflicts by preserving all completed slice behavior. Do not silently drop enum/resource/config additions.
9. Run project-native gates after each conflict-heavy merge and again at final head.
10. Push the feature branch only after gates pass.
11. Open exactly one final non-draft PR from feature branch to `main` with verification evidence and exact closing references for issues intended to close.
12. Post signed status to parent/child issues and final PR.

## Issue and PR linking

- Use `Closes #NN`, `Fixes #NN`, or `Resolves #NN` only for exact child issues the PR satisfies when it reaches default branch.
- Use `Refs #NN` / `Related to #NN` for context links that must not close or satisfy an issue.
- Do not add closing keywords for parent epics unless all epic acceptance is truly complete.
- After PR creation/update, verify Development links when the repo depends on them.

## Status/signature convention

GitHub comments often come from one shared GitHub account/token. Use body-level signatures.

Examples:

```text
— tech-lead / orchestrator
— implementation-specialist / implementer
— test-automation-engineer / tester
— architect-designer / architect
```

Do not forge another profile's signature.

## Conflict-resolution checks for resource-heavy repos

- Inspect generated/resource conflicts directly; keep all authored resources needed by merged slices.
- If enum members are added independently, append both and update serialized numeric values to match final enum order.
- For selector/router conflicts, preserve all branches and choose explicit priority order rather than dropping either side.
- After conflict edits, run targeted gates before committing the merge, then full gates after final integration.

## Role boundary

Architect/designer coordinates, verifies, documents decisions, and delegates implementation. Direct conflict edits are acceptable only as integration stewardship when preserving already-reviewed worker slices and immediately backed by gates; otherwise route implementation to the implementation specialist.

## Project customization checklist

Before using this in a new repo, edit this file to match that repo:

- feature branch naming
- worker PR base branch policy
- draft vs ready PR rules
- review-bot behavior
- required checks/tests/imports
- GitHub Project statuses
- issue closure/linking standards
- required comment signatures
