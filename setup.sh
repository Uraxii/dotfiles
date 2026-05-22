#!/usr/bin/env bash
# setup.sh — deploy dotfiles via stow.
#
# Pass 1: stow . into ~/.config (folded; one symlink per top-level dir).
# Pass 2: stow --no-folding into $HOME/.claude and $HOME/.hermes
#         (per-file symlinks; runtime state coexists alongside tracked files).
#
# See README.md for ~/.zshenv stub (one-time, per machine).
set -eu
cd "$(dirname "$(readlink -f "$0")")"
stow .
mkdir -p "$HOME/.claude" "$HOME/.hermes"
stow --no-folding -t "$HOME/.claude" .claude
stow --no-folding -t "$HOME/.hermes" .hermes
