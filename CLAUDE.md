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
│   ├── qt6ct/                    # Qt6 theming (qt6ct.conf)
│   ├── starship.toml             # Starship prompt (currently disabled)
│   ├── sway/                     # Sway WM (config, modules, themes, scripts)
│   ├── waybar/                   # Waybar (config + CSS template)
│   └── wofi/                     # Wofi launcher (config only, CSS is runtime)
├── .claude/                      # Claude Code project settings
├── home.nix                      # Nix home-manager config
```

## Stow Ignore

`.stow-local-ignore` controls what stow skips (regex). Currently ignores git files, README/LICENSE, `scripts`, `.claude/settings.local.json`. Overrides stow defaults — must re-add defaults manually.

# Theming System

Changing `set $theme <name>` in `sway/prefs` + sway reload switches sway, GTK, Qt, Waybar, and Wofi together.

## Architecture

`sway/prefs` → defines `$theme`, `$font_family`
`sway/config` → includes `themes/$theme/*`, runs `set-theme.sh`
`set-theme.sh` → copies/generates runtime configs from theme data

Non-sway files (CSS, INI) live under `themes/<name>/data/` to avoid sway's include glob parsing them.

## Templates

Configurable values MUST use template system. `.tmpl` extension, `set-theme.sh` does `sed` substitution.

Two placeholder syntaxes (to avoid Go template conflicts in oh-my-posh TOML):
- `{{PLACEHOLDER}}` — CSS templates (waybar, wofi)
- `##PLACEHOLDER##` — TOML templates (oh-my-posh)

| Variable | Defined in | Placeholder | Used by |
|----------|-----------|-------------|---------|
| `$font_family` | `sway/prefs` | `{{FONT}}` | `waybar/style.css.tmpl`, `themes/*/data/wofi.css` |
| `$theme` | `sway/prefs` | N/A | `sway/config` include path + `set-theme.sh` arg |
| OMP colors | `themes/*/data/omp-colors` | `##PRIMARY##`, `##PATH_BG##`, etc. | `omp/uraxii_atomic.omp.toml.tmpl` |

Adding new variable: define in `sway/prefs` → pass to `set-theme.sh` in `sway/config` → receive as positional arg → add `sed` substitution → use placeholder in templates.

## Theme Directory Structure

```
themes/<name>/
├── colors              # Sway color vars
├── window              # Wallpaper, borders (sway syntax)
├── images/             # Wallpapers
└── data/               # Non-sway configs (NOT included by sway)
    ├── gtk-colors.css      # GTK @define-color overrides
    ├── qt-colors.colors    # Qt6ct INI color scheme
    ├── waybar-colors.css   # Waybar @define-color block
    ├── wofi.css            # Wofi CSS with {{FONT}} placeholder
    ├── omp-colors          # Shell vars for oh-my-posh ##PLACEHOLDER## substitution
    └── icon-theme          # Icon theme name (e.g. Papirus-Dark)
```

## Runtime Files (generated, NOT tracked)

`set-theme.sh` writes to: `~/.config/gtk-{3,4}.0/colors.css`, `~/.config/waybar/{colors,style}.css`, `~/.config/wofi/style.css`, `~/.config/qt6ct/colors/theme.colors`, `~/.config/omp/uraxii_atomic.omp.toml`
