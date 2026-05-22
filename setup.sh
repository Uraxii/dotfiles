#!/usr/bin/env bash
# setup.sh — deploy dotfiles via stow.
#
# Pass 1: main packages → ~/.config (folded; one symlink per top-level dir).
# Pass 2: .claude/.hermes → $HOME (unfolded; per-file symlinks so runtime
#         state can coexist alongside tracked configs in the real dir).
#
# See README.md for ~/.zshenv stub (one-time, per machine).
set -eu
cd "$(dirname "$(readlink -f "$0")")"
stow .
stow --no-folding -t "$HOME" .claude .hermes
