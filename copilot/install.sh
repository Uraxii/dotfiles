#!/bin/sh
# One-time per-machine symlink installer for GitHub Copilot CLI config.
# ~/.copilot/ holds live runtime state (session db, logs, config.json) so it
# cannot be stowed wholesale; only these subpaths are linked in.
# Idempotent: safe to re-run. Never clobbers or silently mislinks a path.
set -eu

COPILOT_DIR="$(cd "$(dirname "$0")" && pwd)"
TARGET_DIR="$HOME/.copilot"

mkdir -p "$TARGET_DIR"

link() {
  name="$1"
  src="$COPILOT_DIR/$name"
  dest="$TARGET_DIR/$name"

  if [ ! -e "$src" ]; then
    echo "ERROR: source missing, refusing to link: $src" >&2
    exit 1
  fi

  rel="$(realpath --relative-to="$TARGET_DIR" "$src")"

  if [ -L "$dest" ]; then
    current="$(readlink "$dest")"
    if [ "$current" = "$rel" ]; then
      echo "skip (already linked): $dest"
      return
    fi
    echo "ERROR: $dest is a symlink to '$current', expected '$rel'. Fix or remove it manually." >&2
    exit 1
  fi

  if [ -e "$dest" ]; then
    echo "ERROR: $dest exists and is not a symlink, refusing to overwrite: $dest" >&2
    exit 1
  fi

  ln -s "$rel" "$dest"
  echo "linked: $dest -> $rel"
}

link "agents"
link "skills"
link "instructions"
link "refs"
link "copilot-instructions.md"
