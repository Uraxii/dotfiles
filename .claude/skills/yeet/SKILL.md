---
name: yeet
description: Stage, commit, push, and open a GitHub pull request in one flow. Use when user says "yeet", "ship it", "open a PR", "commit and PR", or invokes /yeet. Replaces the manual add → commit → push → gh pr create ritual.
---

# Yeet

End-of-task ship flow. Single PR per branch. Conventional commit format.

## Prerequisites

- `gh --version` returns ok. If missing, ask user to install and stop.
- `gh auth status` clean. If not, ask user to run `gh auth login` and stop.

## Workflow

1. **Branch.** If on `main`/`master`/default, create `git checkout -b <type>/<scope-or-summary>` using the repo's existing branch-prefix convention (check `git log --oneline -20` for examples). Otherwise stay on current branch.
2. **Stage.** Show `git status -sb` to user. Default to `git add -A`. If the working tree has pre-existing dirty files unrelated to this ship, warn and ask before staging them.
3. **Commit.** Conventional commit format: `<type>(<scope>): <subject>`. Types: `feat`, `fix`, `refactor`, `docs`, `style`, `test`, `chore`. Scope optional. Subject terse, present tense.
4. **Push.** `git push -u origin $(git branch --show-current)`. If rejected for non-fast-forward + branch already tracks remote, ask before force-push.
5. **PR.** Check existing PR for branch: `gh pr view $(git branch --show-current) --json number,url`.
   - **Exists**: update title + body in place via `gh pr edit --title ... --body-file ...`. Never flip draft↔ready.
   - **New**: open ready-for-review via `gh pr create --base <default-branch> --head $(git branch --show-current) --title ... --body-file ...`.

## Title

`<type>(<scope>): <subject>` — match the commit. Under 72 chars.

## Body

```markdown
## Summary
- 1-3 bullets on the net change

## Why
Brief prose on the motivation. If the current conversation discussed motivation,
capture it. Skip if obvious from Summary.

## Test plan
- [x] Bulleted checklist of verifications run
```

Pass body via `--body-file <tempfile>` to avoid `\n` escape issues. Temp file path: `mktemp /tmp/pr-body.XXXXXX.md`.

Backticks for paths, commands, identifiers. Fenced code blocks for transcripts.

## Anti-patterns

- No `--draft` default on new PRs. Solo repos don't need it.
- No PR template discovery unless the repo has one (most don't).
- No commits with secrets. Skip `.env`, `credentials.json`, etc.
- Never use `git commit --amend` when this skill creates a new commit; always new commit.
- Never `git push --force` to `main`/`master`.

## Co-authorship trailer

End commit message with:

```
Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
```
