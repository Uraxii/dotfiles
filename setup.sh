#!/usr/bin/env bash
# setup.sh — deploy dotfiles via stow.
#
# Pass 1: stow . into ~/.config (folded; one symlink per top-level dir).
# Pass 2: stow --no-folding into $HOME/.claude and $HOME/.hermes
#         (per-file symlinks; runtime state coexists alongside tracked files).
#
# Subcommand:
#   (none)  fail loudly on existing-file conflicts
#   adopt   pull existing $HOME files INTO repo + symlink (review with `git diff`)
#
# See README.md for ~/.zshenv stub (one-time, per machine).
set -eu
cd "$(dirname "$(readlink -f "$0")")"

OPTS=()
case "${1:-}" in
    adopt) OPTS+=(--adopt) ;;
    "")    ;;
    *)     echo "usage: $0 [adopt]" >&2; exit 2 ;;
esac

# Explicit -d "$PWD" forces stow-dir to repo root regardless of how setup.sh is invoked.
stow "${OPTS[@]}" -d "$PWD" .
mkdir -p "$HOME/.claude" "$HOME/.hermes"
stow "${OPTS[@]}" --no-folding -d "$PWD" -t "$HOME/.claude" .claude
stow "${OPTS[@]}" --no-folding -d "$PWD" -t "$HOME/.hermes" .hermes
