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

## First-time setup (per machine)

Three one-time manual steps for tools that don't honor XDG:

```bash
# 1. zsh: redirect to $ZDOTDIR (zsh always reads ~/.zshenv, can't be relocated)
cat > ~/.zshenv <<'EOF'
export ZDOTDIR="${XDG_CONFIG_HOME:-$HOME/.config}/zsh"
EOF

# 2. claude-code: hardcodes ~/.claude
ln -s ~/.config/.claude ~/.claude

# 3. hermes: hardcodes ~/.hermes
ln -s ~/.config/.hermes ~/.hermes
```

If `~/.claude/` or `~/.hermes/` already exists as a real directory (e.g. you ran claude/hermes before installing dotfiles), merge first then symlink:
```bash
rsync -a --ignore-existing ~/.claude/ ~/.config/.claude/ && mv ~/.claude ~/.claude.bak && ln -s ~/.config/.claude ~/.claude
# same pattern for ~/.hermes
```

`docs/`, `README*`, `LICENSE*`, runtime opencode/pipeline state, and a few editor noise patterns are filtered by `.stow-local-ignore` and never linked.

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
| opencode | AI agent stack (legacy) | [docs/tooling.md](docs/tooling.md) |
| Claude Code | AI agent stack — `.claude/` agents + skills (omerxx-mirrored) | [docs/tooling.md](docs/tooling.md) |
| Hermes Agent | AI agent stack — `.hermes/` profiles + skills (omerxx-mirrored) | [docs/tooling.md](docs/tooling.md) |
| systemd/user | Per-user services | [docs/tooling.md](docs/tooling.md) |
| theming pipeline | Cross-component re-skin | [docs/theming.md](docs/theming.md) |

For the theming architecture, agent rules, and the `docs/` contract itself, see [CLAUDE.md](CLAUDE.md).

## Useful packages

Not required, but pair well with this setup:

- `gitui` — terminal Git UI, fast.
- `ncspot` — terminal Spotify client.
- `yazi` — terminal file manager with image previews.
- `zoxide` — `cd` replacement that learns frequent paths (already wired in `.zshrc`).
- `tealdeer` (`tldr`) — fast `tldr` client for command examples.
