# Uraxii Dotfiles

GNU Stow-managed dotfiles for a Sway-based Wayland desktop. Omerxx-style XDG layout — `--target=~/.config` set in `.stowrc`.

## Quick start

Prerequisites: `git`, `stow`.

```bash
sudo pacman -S git stow         # Arch / Manjaro
git clone <this-repo> ~/dotfiles
cd ~/dotfiles
./setup.sh                      # stow: repo root -> ~/.config
./setup.sh --force-repo -n      # preview which live files --force-repo would delete
./setup.sh --force-repo         # DESTRUCTIVE: delete blocking live files, then stow
stow -R .                       # restow after changes
stow -n -v .                    # dry run
```

`setup.sh` is not stock stow. It runs one `deploy` pass: the repo root into
`~/.config`. Extra arguments pass through to stow. `--force-repo` is the
script's own mode: it dry-runs stow, reads the conflicts, and `rm -f`s every
plain live file that blocks a link, so the repo wins. Run `--force-repo -n`
first and read the list.

### Packages (mise)

[mise](https://mise.jdx.dev) installs the packages. `mise/` stows to
`~/.config/mise/`. It has two parts:

- `mise/config.toml` `[tools]`: user CLI tools (neovim, ripgrep, starship,
  node, python, the AI CLIs, ...). No root. Same on every platform.
- `mise run system`: system packages (sway stack, compilers, native libs,
  GUI apps). The rules are different for each platform.

`system` is a switchboard. It detects the platform, exports it in
`DOTFILES_PLATFORM`, and runs that platform's rules from
`mise/lib/dotplat/platforms/<platform>.py`. Platforms: `arch`, `nixos`,
`ubuntu`, `fedora`, `bazzite`, `termux`, `windows`. The tasks are Python
file tasks in `mise/tasks/`, so the same task runs on Linux and Windows.

```bash
mise run platform                     # print the detected platform
mise run system --dry-run             # print the commands, change nothing
mise run system --profile server      # core only: no desktop, fonts, GUI apps
DOTFILES_PLATFORM=fedora mise run system --dry-run   # test another platform's rules
mise run setup                        # mise install + system + ./setup.sh
```

If mise does not pass `--dry-run` through, use `DOTFILES_DRY_RUN=1` and
`DOTFILES_PROFILE=server`. `DOTFILES_SHELL` sets the login shell
(default `fish`, `none` to skip).

New Linux machine:

```bash
# 1. install git, stow, and mise (https://mise.jdx.dev/installing-mise.html)
git clone <this-repo> ~/dotfiles && cd ~/dotfiles
./setup.sh                            # links mise/ to ~/.config/mise/
mise run setup                        # python, then tools, then system packages
```

You do not need a system Python. Each task declares
`#MISE tools={python="3.13"}`, so `mise run` installs Python before the
task starts. For `pypi:` tools, `mise install` installs Python and uv first.

Termux: mise support on Android is limited, so do not use mise there.
Install Python with `pkg`, then run the task file directly. It installs
the user tools with `pkg`:

```bash
pkg install -y python
python ~/.config/mise/tasks/system
```

New Windows machine (PowerShell). There is no stow on Windows, so mise
reads the repo directly through `MISE_CONFIG_DIR`:

```powershell
winget install jdx.mise Git.Git
git clone <this-repo> $HOME\dotfiles
[Environment]::SetEnvironmentVariable("MISE_CONFIG_DIR", "$HOME\dotfiles\mise", "User")
# open a new terminal, then:
mise run setup
# put the tools on PATH in every shell: add this line to $PROFILE
mise activate pwsh | Out-String | Invoke-Expression
```

To add a platform: add its id to `PLATFORMS` (and `ALIASES`) in
`mise/lib/dotplat/detect.py`, then add `platforms/<id>.py` with a
`steps()` function.

### Helper scripts (uv)

`setup.py` (stow + KDE-keybind TUI) runs in a `uv`-managed virtualenv.
`uv.lock` is committed; `.venv/` is generated.

`install.py` with `deps.toml` is the old package installer. mise replaces
it. It stays until the mise tasks are tested on each machine.

```bash
uv sync                         # one-time: build .venv from uv.lock
uv run setup.py                 # stow / KDE-keybind TUI (needs textual)
uv run install.py -n            # old installer, dry run
uv run pytest                   # test suite
```

## First-time setup (per machine)

One-time manual step for tools that don't honor XDG:

```bash
# 1. zsh: redirect to $ZDOTDIR (zsh always reads ~/.zshenv, can't be relocated)
cat > ~/.zshenv <<'EOF'
export ZDOTDIR="${XDG_CONFIG_HOME:-$HOME/.config}/zsh"
EOF

# 2. bash: bootstrap stub (bash always reads ~/.bashrc, can't be relocated)
cat > ~/.bashrc <<'EOF'
[ -r "${XDG_CONFIG_HOME:-$HOME/.config}/bash/bashrc" ] && . "${XDG_CONFIG_HOME:-$HOME/.config}/bash/bashrc"
EOF
```

With the stub in place, zsh reads `.zshrc`, `.zprofile`, and the rest from
`$ZDOTDIR` instead of `$HOME`; bash reads `bash/bashrc` the same way.

AI-harness config (Claude Code agents/skills, Codex, Hermes, opencode, Copilot) is deployed separately by `~/dotai`; see that repo's setup for its own first-time steps.

## Repo layout

```
~/dotfiles/
├── .stowrc                       # --target=~/.config (omerxx model)
├── .stow-local-ignore            # Stow ignore patterns (regex)
├── setup.sh                      # IGNORED. Two stow passes, plus --force-repo mode
├── bash/bashrc                   # → ~/.config/bash/bashrc   (loaded via ~/.bashrc stub)
├── ghostty/                      # → ~/.config/ghostty/
├── mise/                         # → ~/.config/mise/   (tools + per-platform system tasks)
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
