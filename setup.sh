#!/usr/bin/env bash
# setup.sh — stow into ~/.config (see .stowrc), symlink $HOME breakers.
set -eu
cd "$(dirname "$(readlink -f "$0")")"

stow .

# Tools that hardcode $HOME paths get a symlink shim.
# If $HOME/.foo already exists as a real dir/file, ln -sfT errors loudly —
# remove or merge it manually then re-run.
for n in .claude .hermes .zshrc .xonshrc .zprofile; do
    ln -sfT "$HOME/.config/$n" "$HOME/$n"
done
