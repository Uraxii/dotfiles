#!/usr/bin/env bash
# setup.sh — deploy dotfiles via stow into ~/.config (see .stowrc).
# See README.md for one-time per-machine setup (~/.zshenv, ~/.claude, ~/.hermes).
set -eu
cd "$(dirname "$(readlink -f "$0")")"
stow .
