# Tooling

Editor and user-level systemd units. Agent and skill config for AI
harnesses is not in this repo; it lives in `~/dotai` (see
[agents.md](agents.md)).

## nvim

### Purpose

Neovim configuration (Kickstart-derived). Has its own docs — do not
duplicate here.

### Key files

- `.config/nvim/README.md` — install + dependency notes.
- `.config/nvim/CLAUDE.md` — agent-facing internals.

For dependencies (`node`, `fzf`, `gcc`, `go`, `unzip`) and any
nvim-specific guidance, see the linked files above.

### External dependencies

`neovim`. See `.config/nvim/README.md` for the rest.

## systemd / user

### Purpose

User-level systemd units packaged with the dotfiles.

### Key files

- `.config/systemd/user/sway-low-battery.service` — pairs with
  `.config/sway/scripts/battery_monitor.sh` to alert on low battery.

### External dependencies

`systemd` (user instance).
