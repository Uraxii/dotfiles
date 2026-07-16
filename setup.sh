#!/usr/bin/env bash
# setup.sh — deploy dotfiles via stow.
#
# Extra args are forwarded to stow, so you can use its own flags:
#   ./setup.sh                 # safe default: stops on any conflict
#   ./setup.sh -R              # restow (unstow + stow) to fix stale links
#   ./setup.sh --override='.*' # relink foreign symlinks stow doesn't own
#
# Custom deploy mode (repo -> live, repo wins):
#   ./setup.sh --force-repo    # DESTRUCTIVE: delete any plain live file that
#                              #   blocks a link, then stow. Use when the repo
#                              #   is authoritative and stale live files are in
#                              #   the way. Combine with --override='.*' to also
#                              #   force-replace foreign symlinks.
#   ./setup.sh --force-repo -n # PREVIEW: list the live files that would be
#                              #   removed and simulate the stow, touching nothing.
#   WARNING: --force-repo also overrides the SOUL.md persona-protection guard
#   below, so a locally-EDITED SOUL.md gets deleted too (repo wins). Run
#   --force-repo -n FIRST and read the victim list before running for real.
set -eu
cd "$(dirname "$(readlink -f "$0")")"

force_repo=0
dry=0
stow_args=()
for arg in "$@"; do
  case "$arg" in
    --force-repo)      force_repo=1 ;;
    -n|--no|--simulate) dry=1; stow_args+=("$arg") ;;
    *)                 stow_args+=("$arg") ;;
  esac
done

# deploy PACKAGE into a target dir. In --force-repo mode, first remove any plain
# live file (not a symlink, not a directory) that would block a link, so the
# repo version wins. Non-force mode is stock stow: it stops on conflicts.
deploy() {
  target=$1; shift            # remaining "$@": stow flags + package name
  if [ "$force_repo" -eq 1 ]; then
    while IFS= read -r rel; do
      [ -n "$rel" ] || continue
      victim="$target/$rel"
      # Only remove real files/symlinks that block a link. Never touch dirs
      # (stow folds into them) or correct links (they never appear as conflicts).
      if [ -e "$victim" ] && [ ! -d "$victim" ]; then
        if [ "$dry" -eq 1 ]; then
          printf 'force-repo: would remove %s\n' "$victim"
        else
          printf 'force-repo: removing %s\n' "$victim"
          rm -f "$victim"
        fi
      fi
    done < <(stow -n -v 3 -d "$PWD" -t "$target" "$@" 2>&1 \
             | grep '^CONFLICT when stowing' \
             | sed -E 's/.* over existing target (.+) since .*/\1/')
  fi
  if [ "$force_repo" -eq 1 ] && [ "$dry" -eq 1 ]; then
    # ponytail: preview mode removes nothing, so stow's own -n dry-run still
    # sees the same conflicts and exits nonzero. Expected here, not a real
    # failure, so don't let set -e abort the run before later targets preview.
    stow -d "$PWD" -t "$target" "$@" || true
  else
    stow -d "$PWD" -t "$target" "$@"
  fi
}

deploy "$HOME/.config" "${stow_args[@]}" .
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

deploy "$HOME/.claude" --no-folding "${stow_args[@]}" .claude
deploy "$HOME/.hermes" --no-folding "${stow_args[@]}" .hermes
mkdir -p "$HOME/.config/autostart"
deploy "$HOME/.config/autostart" --no-folding "${stow_args[@]}" autostart
