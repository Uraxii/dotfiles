# Uraxii Dotfiles

GNU Stow-managed dotfiles for a Sway-based Wayland desktop. Omerxx-style XDG layout — `--target=~/.config` set in `.stowrc`.

## Quick start

Prerequisites: `git`, `stow`.

```bash
sudo pacman -S git stow         # Arch / Manjaro
git clone <this-repo> ~/dotfiles
cd ~/dotfiles
./setup.sh                      # runs `stow .`
stow -R .                       # restow after changes
stow -n -v .                    # dry run
```

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

`docs/`, `README*`, `LICENSE*`, and a few editor noise patterns are filtered by `.stow-local-ignore` and never linked.

AI-harness config (Claude Code agents/skills, Codex, Hermes, opencode, Copilot) is deployed separately by `~/dotai`; see that repo's setup for its own first-time steps.

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
| Claude Code | `.claude/` hooks, themes, statusline.sh only — agents/skills/rules live in `~/dotai` | [docs/tooling.md](docs/tooling.md) |
| systemd/user | Per-user services | [docs/tooling.md](docs/tooling.md) |
| theming pipeline | Cross-component re-skin | [docs/theming.md](docs/theming.md) |

AI-harness config (agents, skills, rules for Claude Code, Codex, Hermes, opencode, Copilot) lives in `~/dotai`, a separate stow-managed repo.

For the theming architecture, agent rules, and the `docs/` contract itself, see [docs/theming.md](docs/theming.md), [docs/agents.md](docs/agents.md), and [docs/conventions.md](docs/conventions.md).

## Useful packages

Not required, but pair well with this setup:

- `gitui` — terminal Git UI, fast.
- `ncspot` — terminal Spotify client.
- `yazi` — terminal file manager with image previews.
- `zoxide` — `cd` replacement that learns frequent paths (already wired in `.zshrc`).
- `tealdeer` (`tldr`) — fast `tldr` client for command examples.
