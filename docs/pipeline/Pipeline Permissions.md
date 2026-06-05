# Pipeline Permissions

Claude Code's permission engine controls which tool invocations require user prompts. The pipeline's `.claude/settings.json` allow-list is portable and broad enough that agents don't prompt for routine pipeline operations; the deny-list blocks destructive ops + the project-doctrine surface.

## File hierarchy

| File | Tracked | Scope |
|------|---------|-------|
| `.claude/settings.json` | git | Project-wide, committed. Portable rules. |
| `.claude/settings.local.json` | `.claude/*local*` ignore | Per-machine, gitignored. WebFetch domains, plugin cache reads, ad-hoc one-shots. |

`~/.claude/settings.json` is a stow-managed symlink to `~/dotfiles/.claude/settings.json`.

## Precedence

Confirmed via Claude Code docs: **rules evaluate in order — deny first, then ask, then allow. First match in any category wins.**

Practical consequence: `Bash(git push --force:*)` in `deny` correctly overrides `Bash(git push:*)` in `allow`. Deny wins on overlap.

## Allow-list categories

Patterns in committed `settings.json`. ~70 allows; portable (no absolute paths, `~` + unrooted globs only).

### Pipeline directories

```
Read|Write|Edit(~/.pipeline/**)        # plans, runs
Read|Write|Edit(.pipeline/**)          # project mirror
```

The single `~/.pipeline/**` glob covers `plans/` and `runs/` — no separate entries needed.

### Project doctrine reads

```
Read(CLAUDE.md)
Read(.claude/**)                       # agents, skills, templates, hooks
Read(docs/adr/**)
Read(CONTRIBUTING.md)
```

Every agent's `## Inputs` block reads at least project CLAUDE.md + applicable `.claude/rules/<lang>.md` + `docs/adr/`. No prompt fires.

### Architect ADR writes

```
Write(docs/adr/**)
Edit(docs/adr/**)
```

Restricted to architect's domain. Other roles read ADRs but don't write.

### Progenitor scope (agent + skill + template edits)

```
Edit|Write(.claude/agents/**)
Edit|Write(.claude/skills/**)
Edit|Write(.claude/templates/**)
```

### Git

```
Bash(git rev-parse:*)
Bash(git worktree:*)
Bash(git diff:*)
Bash(git log:*)
Bash(git fetch:*)
Bash(git push:*)
Bash(git update-ref:*)
Bash(git reset --soft:*)             # PR squash uses this
Bash(git add:*)
Bash(git commit:*)
Bash(git checkout:*)
Bash(git status)
Bash(git branch:*)
Bash(git remote:*)
Bash(git merge:*)                    # tester combined-state step
Bash(git show:*)
```

`git stash:*` was removed — no doctrinal pipeline use case. Re-add only when a role spec requires it.

### GitHub CLI

```
Bash(gh pr create:*)
Bash(gh pr merge:*)
Bash(gh pr view:*)
Bash(gh pr list:*)
Bash(gh auth status)
Bash(gh api:*)
```

### Skill-internal shell commands

```
Bash(printf:*)                       # prod-diff-sha
Bash(sha1sum:*)                      # prod-diff-sha
Bash(mktemp:*)                       # context-rotation-summary
Bash(mkdir:*) Bash(mkdir -p:*)       # progenitor + intake
Bash(command -v:*)                   # GitHub preconditions
Bash(wc:*)
Bash(test -f:*) Bash(test -d:*) Bash(test ! -f:*)
Bash(jq:*)                           # verification
Bash(python3 ~/.config/opencode/tools/artifact-slug.py*)
```

Shell-builtin caveat: `test -f` form is covered; `[ -f ]` and `[[ -f ]]` are POSIX builtins inside compound commands — not permission-checkable. Skill bodies should use `test -f`.

### Build ecosystem stubs

```
Bash(npm test:*)
Bash(pnpm test:*)
Bash(yarn test:*)
Bash(bun test:*)
Bash(pytest:*)
Bash(python -m pytest:*)
Bash(python3 -m pytest:*)
Bash(cargo test:*)
Bash(go test:*)
Bash(dotnet test:*)
```

Project-specific test runners go in `settings.local.json`.

## Deny rules

```
Write(CLAUDE.md)
Edit(CLAUDE.md)
Bash(git reset --hard:*)
Bash(git push --force:*)
Bash(git push -f:*)
Bash(git clean:*)
Bash(rm -rf:*)
```

- `Write|Edit(CLAUDE.md)` enforces the no-direct-write rule. The user owns CLAUDE.md edits.
- Destructive git ops require explicit user confirmation (no agent grant possible).
- `rm -rf` is denied to agents.

## Portability rules

All entries follow these constraints:

- Use `~` for the home directory. Never literal `/home/<user>/`.
- Use unrooted globs for project-relative paths (`.pipeline/**`, `.claude/**`, `docs/adr/**`).
- No machine-specific values (hostnames, usernames, branch names).
- Bash patterns use `:*` suffix or glob; no inline absolute file paths.

Verification:

```bash
# Should be zero matches (no absolute paths):
grep -rnE '"[A-Za-z]+\([A-Za-z]*/(home|Users|root|tmp|var|opt|mnt|media)/' .claude/settings.json

# Should be non-zero (portable patterns present):
grep -rnE '"~/' .claude/settings.json | wc -l
grep -rnE '"\.(pipeline|claude)/' .claude/settings.json | wc -l
```

## What permissions can't enforce

- **Skill names**. The engine matches tool invocations (`Bash`, `Read`, `Skill`, `Agent`, etc.), not skill-name arguments. Skill-name-level deny rules cannot be enforced by the permission engine alone — defense rests on doctrine + audit.
- **Shell-builtin variants** as noted above (`[`, `[[`).
- **`~` expansion semantics**. If a Bash invocation reaches the matcher with `~` already expanded to `/home/<user>/`, patterns using `~` won't match. Plan documented this as a pre-deploy verification item.

## Anti-patterns observed in audit

Past `settings.local.json` accumulated stale entries:

- `Bash(git -C /home/nikki/dotfiles diff --stat HEAD)` — hard-coded user path
- `Bash(python3 -m scripts /home/nikki/.claude/agents/architect.md)` — one-shot
- `Bash(mkdir -p /home/nikki/dotfiles/.pipeline/runs/<specific-run-id>)` — stale per-run entry

These were pruned during the skills-adoption batch. New one-shots accumulate over time — periodic prune (via `/fewer-permission-prompts` skill or manual edit) keeps the file lean.

## Related

- [[Pipeline Overview]]
- [[Pipeline Skills]] — explicit Skill-tool invocation pattern
