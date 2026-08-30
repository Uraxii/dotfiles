# Tooling

Editor and user-level systemd units. Agent and skill config for AI
harnesses is not in this repo; it lives in `~/dotai`.

## nvim

### Purpose

Neovim configuration (Kickstart-derived). Has its own docs — do not
duplicate here.

### Key files

- `.config/nvim/init.lua` — requires the `lua/config/` modules in this
  order: `globals`, `options`, `keymaps`, `autocommands`, `lsp`,
  `lazy_plugin_manager`.
- `.config/nvim/lua/plugins/` — one file per plugin, each returning a
  lazy.nvim spec. Add a plugin by adding a file here, not by growing an
  existing one.
- `.config/nvim/README.md` — upstream kickstart install and dependency
  notes.

For dependencies (`node`, `fzf`, `gcc`, `go`, `unzip`) and the rest of the
kickstart guidance, see `.config/nvim/README.md`.

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
