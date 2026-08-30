# Conventions

## Docs

Human-facing per-component docs live in `docs/`. Repo-only — the dir is in `.stow-local-ignore`, never symlinked into `$HOME`.

### Doc inventory

| Component | Doc file |
|-----------|----------|
| sway, waybar, wofi, swaylock, networkmanager-dmenu | `docs/desktop.md` |
| zsh, starship, ghostty | `docs/shell.md` |
| nvim, systemd/user | `docs/tooling.md` |
| theming pipeline | `docs/theming.md` |
| this file's own contract | `docs/conventions.md` |

### Doc template

Every component section in `docs/*.md` MUST use these sub-headings (in this order):

1. **Purpose** — one paragraph, what it is and why it's here.
2. **Key files** — bullet list of repo paths the component owns.
3. **Keybindings & UX** — omit if N/A.
4. **Theming integration** — omit if N/A.
5. **External dependencies** — packages required outside this repo.

### Update rule

When a component is added, removed, or materially changed (new module, new keybind, new dependency, new theming hook), update its `docs/*.md` file AND the README inventory table in the same change. Stale docs are worse than missing docs.

### No duplication

- Theming pipeline lives in `docs/theming.md`. It is the home for that content — nothing here duplicates it.
- Neovim install and dependency notes live in `.config/nvim/README.md`, which is upstream kickstart. `docs/tooling.md` records only what this repo changed, and links for the rest.

## Path standard

A pre-commit hook enforces both rules.

- Never commit an expanded home path or a username. Use `$HOME` in shell
  scripts and JSON, `~` in markdown.
- Keep machine-specific and identity-bearing values (tailnet hosts, emails)
  out of tracked files. They belong in `scripts/commit-linter/identity.local`,
  which the repo's blanket `*.local` gitignore rule already covers.

## Commit gate

- The pre-commit hook is a thin wrapper in `.git/hooks`. Its logic is tracked
  at `scripts/commit-linter/lint_staged.py`.
- The hook runs an identity-leak lint with auto-fix, then a fail-closed
  TruffleHog scan of the staged content. The `trufflehog` binary is required
  at `~/.local/bin`.
- If the hook stops firing, check `git config core.hooksPath`. `bd init`
  hijacked it once.
- The emergency bypass is `git commit --no-verify`. Never use it on a secret
  finding.

Full pass list and setup:
[scripts/commit-linter/README.md](../scripts/commit-linter/README.md).

## Spikes

- `spikes/<name>/` are local, untracked scratch and prototype workspaces.
- `spikes/` is gitignored wholesale. Nothing under it is committed.
- Use a spike for repo-adjacent scratch work instead of `/tmp`.

## NerdFont glyphs

Tooling strips high-codepoint UTF-8 on write, so never paste a raw glyph. Use
`~/dotfiles/scripts/nerd-glyph` instead:

- `nerd-glyph emit U+F126` prints the bytes, for command substitution or pipes.
- `nerd-glyph sub FILE __TOK__=F126 __TOK2__=E0B6` replaces ASCII tokens in
  FILE with glyph bytes.
- `nerd-glyph check U+F126 [FONT]` verifies that the codepoint exists in the
  font.

In configs, write tokens (`__GIT__`, `__CAP_L__`) and then run
`nerd-glyph sub`. In shell scripts, emit the bytes with
`printf %b '\xHH\xHH\xHH'`.
