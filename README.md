# Uraxii Dotfiles

GNU Stow-managed dotfiles for a Sway-based Wayland desktop. Single-package, flat-mode layout — the repo root *is* the package, the target is `$HOME`.

## Quick start

Prerequisites: `git`, `stow`.

```bash
sudo pacman -S git stow         # Arch / Manjaro
git clone <this-repo> ~/dotfiles
cd ~/dotfiles
stow -t ~ .                     # create symlinks
stow -R -t ~ .                  # restow after changes
stow -n -v -t ~ .               # dry run (no filesystem changes)
```

`docs/`, `README*`, `LICENSE*`, runtime opencode/pipeline state, and a few editor noise patterns are filtered by `.stow-local-ignore` and never linked into `$HOME`.

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
| nvim | Editor (Kickstart-derived) | [docs/tooling.md](docs/tooling.md) -> [`.config/nvim/`](.config/nvim/) |
| opencode | AI agent stack | [docs/tooling.md](docs/tooling.md) |
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
