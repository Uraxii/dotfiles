#!/usr/bin/env bash
# bootstrap.sh: one command to set up a new Linux or Termux machine.
#
#   ./bootstrap.sh                      # full setup
#   ./bootstrap.sh --profile server     # no desktop, fonts, or GUI apps
#   ./bootstrap.sh --dry-run            # print the commands, change nothing
#
# This is shell only because Python is not available yet. It installs mise
# if it is missing, then runs the Python task mise/tasks/setup, which does
# the rest: Python and the user tools, the system packages, then stow.
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"

# Termux: mise support on Android is limited. Use the pkg Python instead;
# the setup task installs the user tools with pkg on this platform.
if [ -n "${TERMUX_VERSION:-}" ]; then
  command -v python >/dev/null || pkg install -y python
  exec python mise/tasks/setup "$@"
fi

export PATH="$HOME/.local/bin:$PATH"
if ! command -v mise >/dev/null; then
  if [ -e /etc/NIXOS ]; then
    # Generic Linux binaries do not run on NixOS; use the nixpkgs build.
    nix --extra-experimental-features 'nix-command flakes' profile install nixpkgs#mise
  else
    # installs ~/.local/bin/mise. Ubuntu desktop has wget but not curl.
    if command -v curl >/dev/null; then
      curl -fsSL https://mise.run | sh
    else
      wget -qO- https://mise.run | sh
    fi
  fi
fi

# The repo's mise/config.toml is a project config here, so mise finds the
# tasks before stow links anything. Trust it once, explicitly.
mise trust mise/config.toml
exec mise run setup "$@"
