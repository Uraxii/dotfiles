# Uraxii Dotfiles

GNU Stow-managed dotfiles for a Sway-based Wayland desktop. Omerxx-style XDG layout — `--target=~/.config` set in `.stowrc`.

## Quick start

Prerequisites: `git`, `stow`.

```bash
sudo pacman -S git stow         # Arch / Manjaro
git clone <this-repo> ~/dotfiles
cd ~/dotfiles
./setup.sh                      # two stow passes: repo root -> ~/.config, then autostart/
./setup.sh --force-repo -n      # preview which live files --force-repo would delete
./setup.sh --force-repo         # DESTRUCTIVE: delete blocking live files, then stow
stow -R .                       # restow after changes
stow -n -v .                    # dry run
```

`setup.sh` is not stock stow. It runs two `deploy` passes: the repo root into
`~/.config`, then `autostart/` into `~/.config/autostart` with `--no-folding`.
Extra arguments pass through to stow. `--force-repo` is the script's own mode:
it dry-runs stow, reads the conflicts, and `rm -f`s every plain live file that
blocks a link, so the repo wins. Run `--force-repo -n` first and read the list.

### Helper scripts (uv)

`setup.py` (stow + KDE-keybind TUI) and `install.py` (cross-distro package installer) run in a `uv`-managed virtualenv. `uv.lock` is committed; `.venv/` is generated.

```bash
uv sync                         # one-time: build .venv from uv.lock
uv run setup.py                 # stow / KDE-keybind TUI (needs textual)
uv run install.py               # install packages declared in deps.toml
uv run install.py -n            # dry run
uv run pytest                   # test suite
```

## First-time setup (per machine)

One-time manual step for tools that don't honor XDG:

```bash
# 1. zsh: redirect to $ZDOTDIR (zsh always reads ~/.zshenv, can't be relocated)
cat > ~/.zshenv <<'EOF'
export ZDOTDIR="${XDG_CONFIG_HOME:-$HOME/.config}/zsh"
EOF
```

With the stub in place, zsh reads `.zshrc`, `.zprofile`, and the rest from
`$ZDOTDIR` instead of `$HOME`.

AI-harness config (Claude Code agents/skills, Codex, Hermes, opencode, Copilot) is deployed separately by `~/dotai`; see that repo's setup for its own first-time steps.

## Repo layout

```
~/dotfiles/
├── .stowrc                       # --target=~/.config (omerxx model)
├── .stow-local-ignore            # Stow ignore patterns (regex)
├── setup.sh                      # IGNORED. Two stow passes, plus --force-repo mode
├── ghostty/                      # → ~/.config/ghostty/
├── networkmanager-dmenu/         # → ~/.config/networkmanager-dmenu/
├── nvim/                         # → ~/.config/nvim/   (Kickstart-based)
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

Every shell config is XDG-native (`zsh/`, `xonsh/`).

### What stow skips

`.stow-local-ignore` holds the skip patterns, as regexes. It skips repo meta
(`README`, `LICENSE`, `docs`, `deps.toml`, `install.py`, `setup.py`,
`setup.sh`, `pytest.ini`, `scripts`, `tests`, `home.nix`), VCS files, caches
(`__pycache__`, `.ruff_cache`), `.claude/` (untracked local files only),
`.pipeline`, `tmux/plugins`, and `starship.toml` with its `.tmpl` (both
managed by `set-theme.sh`).

`.stowrc` sets `--target=~/.config` and skips `.stowrc` itself plus
`DS_Store`. A stow regex replaces the built-in defaults instead of adding to
them, so re-add by hand any default you still want.

## Component inventory

| Component | Purpose | Docs |
|-----------|---------|------|
| sway | Tiling Wayland compositor | [docs/desktop.md](docs/desktop.md) |
| waybar | Top status bar | [docs/desktop.md](docs/desktop.md) |
| wofi | Launcher / dmenu replacement | [docs/desktop.md](docs/desktop.md) |
| swaylock | Screen lock | [docs/desktop.md](docs/desktop.md) |
| networkmanager-dmenu | Wofi-backed NM UI | [docs/desktop.md](docs/desktop.md) |
| zsh | Interactive shell | [docs/shell.md](docs/shell.md) |
| oh-my-posh | Prompt | [docs/shell.md](docs/shell.md) |
| ghostty | Terminal emulator | [docs/shell.md](docs/shell.md) |
| nvim | Editor (Kickstart-derived) | [docs/tooling.md](docs/tooling.md) -> [`nvim/`](nvim/) |
| systemd/user | Per-user services | [docs/tooling.md](docs/tooling.md) |
| theming pipeline | Cross-component re-skin | [docs/theming.md](docs/theming.md) |

AI-harness config (agents, skills, rules for Claude Code, Codex, Hermes, opencode, Copilot) lives in `~/dotai`, a separate stow-managed repo.

For the theming architecture and the repo conventions (docs contract, path standard, commit gate), see [docs/theming.md](docs/theming.md) and [docs/conventions.md](docs/conventions.md).

## Useful packages

Not required, but pair well with this setup:

- `gitui` — terminal Git UI, fast.
- `ncspot` — terminal Spotify client.
- `yazi` — terminal file manager with image previews.
- `zoxide` — `cd` replacement that learns frequent paths (already wired in `.zshrc`).
- `tealdeer` (`tldr`) — fast `tldr` client for command examples.
