# Dotfiles

## Dos
- Recommend safety commits/branches for large changes.

GNU Stow-managed dotfiles. Omerxx-style XDG layout — repo root contents land in `~/.config/` (target set via `.stowrc`).

```bash
./setup.sh                  # two stow passes, stops on any conflict
./setup.sh --force-repo -n  # preview which live files --force-repo would delete
./setup.sh --force-repo     # DESTRUCTIVE: delete blocking live files, then stow
```

`setup.sh` is not stock stow. It runs two `deploy` passes: the repo root into `~/.config`, then `autostart/` into `~/.config/autostart` with `--no-folding`. Extra arguments pass through to stow. `--force-repo` is the script's own mode. It dry-runs stow, reads the conflicts, and `rm -f`s every plain live file that blocks a link, so the repo wins. Run `--force-repo -n` first and read the list. All shell configs are XDG-native (`zsh/`, `xonsh/`).

## Repo Structure

```
~/dotfiles/
├── .stowrc                       # --target=~/.config (omerxx model)
├── .stow-local-ignore            # Stow ignore patterns (regex)
├── setup.sh                      # IGNORED. Two stow passes, plus --force-repo mode
├── ghostty/                      # → ~/.config/ghostty/
├── networkmanager-dmenu/         # → ~/.config/networkmanager-dmenu/
├── nvim/                         # → ~/.config/nvim/   (Kickstart-based, has own CLAUDE.md)
├── omp/                          # → ~/.config/omp/    (inactive, kept for reference)
├── qt6ct/                        # → ~/.config/qt6ct/
├── sway/                         # → ~/.config/sway/
├── swaylock/                     # → ~/.config/swaylock/   (XDG-native)
├── systemd/                      # → ~/.config/systemd/
├── tmux/                         # → ~/.config/tmux/
├── waybar/                       # → ~/.config/waybar/
├── wofi/                         # → ~/.config/wofi/
├── xonsh/rc.xsh                  # → ~/.config/xonsh/rc.xsh   (xonsh native XDG path)
├── zsh/.zshrc                    # → ~/.config/zsh/.zshrc     (loaded via $ZDOTDIR; see ~/.zshenv stub)
├── zsh/.zprofile                 # → ~/.config/zsh/.zprofile
├── starship.toml                 # IGNORED — managed at runtime by set-theme.sh
├── starship.toml.tmpl            # IGNORED — template, set-theme.sh substitutes ##PALETTE##
├── home.nix                      # IGNORED (repo meta)
```

**zsh + ZDOTDIR**: zsh hardcodes `~/.zshenv` as the one always-loaded file. Create a one-line stub on each machine:
```sh
# ~/.zshenv
export ZDOTDIR="${XDG_CONFIG_HOME:-$HOME/.config}/zsh"
```
After that, zsh loads `.zshrc`, `.zprofile`, etc from `$ZDOTDIR` instead of `$HOME`.

## Stow Ignore

`.stow-local-ignore` controls what stow skips (regex). Ignores: repo meta (`README`, `LICENSE`, `docs`, `CLAUDE.md`, `CONTEXT.md`, `AGENTS.md`, `deps.toml`, `install.py`, `pytest.ini`, `scripts`, `tests`, `home.nix`), VCS files, caches (`__pycache__`, `.ruff_cache`), `.claude/` (untracked local files only), `.pipeline`, `tmux/plugins`, `starship.toml` + `.tmpl` (managed by set-theme.sh).

`.stowrc` defines `--target=~/.config` + ignores `.stowrc` itself + `DS_Store`. Stow regex overrides defaults — must re-add defaults manually.

## Agent & Skill Stack

This repo contains no agent files. Agents, skills, and the Claude Code hooks, statusline, and themes moved to the `Uraxii/dotai` repo (`~/dotai`) or to unversioned copies under `~/.claude`.

Full detail: [`docs/agents.md`](docs/agents.md).

## Path Standard (enforced by pre-commit hook)

- Never commit expanded home paths or usernames. Use `$HOME` in shell scripts/JSON, `~` in markdown.
- Machine-specific or identity-bearing config (tailnet hosts, emails) goes in `.claude/settings.local.json` (gitignored), never in tracked files.

## Commit Gate

- Local pre-commit hook: thin wrapper in `.git/hooks`, logic at `scripts/commit-linter/lint_staged.py`.
- Runs an identity-leak lint (with auto-fix) plus a fail-closed TruffleHog scan of staged content. `trufflehog` binary required at `~/.local/bin`.
- Hooks not firing: check `git config core.hooksPath` (bd init once hijacked it).
- Emergency bypass: `git commit --no-verify`. Never for secret findings.

## Spikes

- `spikes/<name>/` are local, untracked scratch/prototype workspaces.
- `spikes/` is gitignored wholesale; nothing under it is committed.
- Agents use spikes for repo-adjacent scratch work instead of `/tmp`.

# Theming System

Changing `set $theme <name>` in `sway/prefs` + sway reload switches sway, GTK, Qt, Waybar, and Wofi together. Configurable values MUST use the `.tmpl` + `sed` template system. Runtime outputs (`~/.config/waybar/*`, `~/.config/starship.toml`, etc) are generated and NOT tracked.

Full architecture, placeholder tables, theme directory layout, and howto recipes: [`docs/theming.md`](docs/theming.md).

# Docs

Component added/removed/materially changed => update its `docs/*.md` file AND the README inventory table in the same change.

Full doc contract (inventory, template, no-duplication rule): [`docs/conventions.md`](docs/conventions.md).

# NerdFont Glyphs

Tooling strips high-codepoint UTF-8 on write. Never paste raw glyphs. Use `~/dotfiles/scripts/nerd-glyph`:

- `nerd-glyph emit U+F126` — print bytes (for command substitution / pipes).
- `nerd-glyph sub FILE __TOK__=F126 __TOK2__=E0B6` — replace ASCII tokens in FILE w/ glyph bytes.
- `nerd-glyph check U+F126 [FONT]` — verify codepoint exists in font.

In configs, write tokens (`__GIT__`, `__CAP_L__`, …) then run `nerd-glyph sub`. In shell scripts emit via `printf %b '\xHH\xHH\xHH'`.
