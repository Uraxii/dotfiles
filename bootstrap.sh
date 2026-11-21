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

dry=0
for arg in "$@"; do
  case "$arg" in -n|--dry-run) dry=1 ;; esac
done

# run CMD...: run it, or only print it in a dry run.
run() {
  printf '+ %s\n' "$*"
  if [ "$dry" -eq 0 ]; then "$@"; fi
}

export PATH="$HOME/.local/bin:$PATH"
nixos=0; [ -e /etc/NIXOS ] && nixos=1

if [ -n "${TERMUX_VERSION:-}" ] || [ "$nixos" -eq 1 ]; then
  # mise's prebuilt python and node do not run on Android or NixOS, so they
  # come from the system and mise skips them (SYSTEM_RUNTIMES in
  # mise/lib/dotplat/detect.py; the shell configs set the same value).
  export MISE_DISABLE_TOOLS=python,node
fi

if [ -n "${TERMUX_VERSION:-}" ]; then
  # mise.run does not support Android; Termux ships its own mise build.
  run pkg install -y mise python nodejs
elif [ "$nixos" -eq 1 ]; then
  # Generic Linux binaries do not run on NixOS; use the nixpkgs builds.
  command -v mise >/dev/null && command -v python >/dev/null && command -v node >/dev/null ||
    run nix --extra-experimental-features 'nix-command flakes' profile install \
      nixpkgs#mise nixpkgs#python3 nixpkgs#nodejs
elif ! command -v mise >/dev/null; then
  # installs ~/.local/bin/mise. Ubuntu desktop has wget but not curl.
  if command -v curl >/dev/null; then
    run sh -c 'curl -fsSL https://mise.run | sh'
  else
    run sh -c 'wget -qO- https://mise.run | sh'
  fi
fi

if [ "$dry" -eq 1 ]; then
  # A dry run changes nothing: no mise install, no trust, no Python download.
  # The setup task needs only the Python standard library, so run it with
  # any Python that is already here.
  printf '+ mise trust mise/config.toml\n+ mise run setup %s\n' "$*"
  py=$(command -v python3 || command -v python || true)
  if [ -n "$py" ]; then
    exec "$py" mise/tasks/setup "$@"
  fi
  echo "dry run: no python on this machine, so the setup steps cannot be listed"
  exit 0
fi

# The repo's mise/config.toml is a project config here, so mise finds the
# tasks before stow links anything. Trust it once, explicitly.
mise trust mise/config.toml
exec mise run setup "$@"
