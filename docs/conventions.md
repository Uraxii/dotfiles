# Docs

Human-facing per-component docs live in `docs/`. Repo-only — the dir is in `.stow-local-ignore`, never symlinked into `$HOME`.

## Doc inventory

| Component | Doc file |
|-----------|----------|
| sway, waybar, wofi, swaylock, networkmanager-dmenu | `docs/desktop.md` |
| zsh, starship, ghostty | `docs/shell.md` |
| nvim, systemd/user | `docs/tooling.md` |
| theming pipeline | `docs/theming.md` |
| agent & skill stack (lives in `~/dotai`, not here) | `docs/agents.md` |
| this file's own contract | `docs/conventions.md` |

## Doc template

Every component section in `docs/*.md` MUST use these sub-headings (in this order):

1. **Purpose** — one paragraph, what it is and why it's here.
2. **Key files** — bullet list of repo paths the component owns.
3. **Keybindings & UX** — omit if N/A.
4. **Theming integration** — omit if N/A.
5. **External dependencies** — packages required outside this repo.

## Update rule

When a component is added, removed, or materially changed (new module, new keybind, new dependency, new theming hook), update its `docs/*.md` file AND the README inventory table in the same change. Stale docs are worse than missing docs.

## No duplication

- Theming pipeline lives in `docs/theming.md`. It is the home for that content — nothing here duplicates it.
- Neovim internals live in `.config/nvim/CLAUDE.md` and `.config/nvim/README.md`. `docs/tooling.md` links — never copies.
