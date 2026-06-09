#!/usr/bin/env bash
# setup.sh — deploy dotfiles via stow.
set -eu
cd "$(dirname "$(readlink -f "$0")")"
stow -d "$PWD" .
mkdir -p "$HOME/.claude" "$HOME/.hermes"

# SOUL.md files are static identity files tracked by dotfiles now. If a
# pre-existing live copy matches the tracked copy, remove it so stow can
# replace it with a symlink. If it differs, leave it in place so stow reports
# the conflict instead of overwriting local persona edits.
while IFS= read -r src; do
  rel="${src#"$PWD/.hermes/"}"
  dst="$HOME/.hermes/$rel"
  if [ -f "$dst" ] && cmp -s "$src" "$dst"; then
    rm "$dst"
  fi
done <<EOF
$(find "$PWD/.hermes" -path '*/SOUL.md' -type f | sort)
EOF

stow --no-folding -d "$PWD" -t "$HOME/.claude" .claude
stow --no-folding -d "$PWD" -t "$HOME/.hermes" .hermes
mkdir -p "$HOME/.config/autostart"
stow --no-folding -d "$PWD" -t "$HOME/.config/autostart" autostart
