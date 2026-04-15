# Dotfiles

GNU Stow-managed dotfiles. Flat/single-package mode — repo root IS the package, target is `$HOME`.

```bash
stow -t ~ .          # create symlinks
stow -R -t ~ .       # restow after changes
stow -n -v -t ~ .    # dry run
```

## Repo Structure

```
~/dotfiles/
├── .zshrc                        # Zsh config (oh-my-posh, keybinds, aliases)
├── .swaylock/                    # Swaylock config
├── .stow-local-ignore            # Stow ignore patterns (regex)
├── .config/
│   ├── ghostty/                  # Ghostty terminal
│   ├── networkmanager-dmenu/     # Network manager dmenu
│   ├── nvim/                     # Neovim (Kickstart-based, has own CLAUDE.md)
│   ├── omp/                      # Oh My Posh prompt themes
│   ├── opencode/                 # OpenCode + Claude Code skills
│   ├── starship.toml             # Starship prompt (currently disabled)
│   ├── sway/                     # Sway WM (config, modules, themes, scripts)
│   ├── waybar/                   # Waybar (config + CSS)
│   └── wofi/                     # Wofi launcher (config + CSS)
├── .claude/                      # Claude Code project settings
├── home.nix                      # Nix home-manager config
```

## Stow Ignore

`.stow-local-ignore` controls what stow skips (regex). Currently ignores git files, README/LICENSE, `scripts`, `.claude/settings.local.json`. Overrides stow defaults — must re-add defaults manually.

