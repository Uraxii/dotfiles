#!/usr/bin/env bash
# setup.sh — deploy dotfiles via stow.
set -eu
cd "$(dirname "$(readlink -f "$0")")"
stow -d "$PWD" .
mkdir -p "$HOME/.claude" "$HOME/.hermes"
stow --no-folding -d "$PWD" -t "$HOME/.claude" .claude
stow --no-folding -d "$PWD" -t "$HOME/.hermes" .hermes
mkdir -p "$HOME/.config/autostart"
stow --no-folding -d "$PWD" -t "$HOME/.config/autostart" autostart
