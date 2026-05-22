#!/usr/bin/env bash
# migrate-runtime-dirs.sh — one-time migration of $HOME/.{claude,hermes}
# runtime dirs into ~/.config/.{claude,hermes}, then symlink back.
#
# Prerequisite: stop both daemons FIRST.
#   - exit all claude-code sessions
#   - stop hermes (pkill hermes / systemctl --user stop hermes — whatever applies)
#   - verify no SQLite WAL files actively being written:
#       lsof ~/.hermes/state.db ~/.hermes/kanban.db 2>/dev/null
#
# Behavior:
#   - rsync $HOME/<name>/ → ~/.config/<name>/ with --ignore-existing
#     (tracked files at the stowed side win; runtime gets added underneath)
#   - rename $HOME/<name> → $HOME/<name>.pre-migrate.<epoch> (backup, not deleted)
#   - symlink $HOME/<name> → ~/.config/<name>
#
# Idempotent: skips dirs that are already symlinks.
# Safety: never deletes; backups remain until you remove them manually.

set -eu

CONFIG="$HOME/.config"
NAMES=(".claude" ".hermes")

# Refuse to run if any claude-code or hermes process visible.
if pgrep -af "claude-code|claude_code|hermes-agent" >/dev/null 2>&1; then
    echo "ERROR: claude-code or hermes process detected. Stop them first:" >&2
    pgrep -af "claude-code|claude_code|hermes-agent" >&2
    exit 3
fi

for name in "${NAMES[@]}"; do
    home_dir="$HOME/$name"
    stow_dir="$CONFIG/$name"

    if [ ! -d "$home_dir" ] && [ ! -L "$home_dir" ]; then
        echo "skip $name (no $home_dir)"
        continue
    fi

    if [ -L "$home_dir" ]; then
        target=$(readlink "$home_dir")
        if [ "$target" = "$stow_dir" ]; then
            echo "skip $name (already symlinked to $stow_dir)"
        else
            echo "WARN: $home_dir is symlink to $target, not $stow_dir — skipping" >&2
        fi
        continue
    fi

    if [ ! -d "$stow_dir" ]; then
        echo "WARN: $stow_dir does not exist — run ./setup.sh first; skipping $name" >&2
        continue
    fi

    echo "merging $home_dir/ -> $stow_dir/ (--ignore-existing: stowed wins)"
    rsync -a --ignore-existing "$home_dir/" "$stow_dir/"

    backup="$home_dir.pre-migrate.$(date +%s)"
    mv "$home_dir" "$backup"
    echo "backed up $home_dir -> $backup"

    ln -sn "$stow_dir" "$home_dir"
    echo "linked $home_dir -> $stow_dir"
done

echo
echo "Done. Verify, then clean up backups:"
for name in "${NAMES[@]}"; do
    ls -d "$HOME/$name".pre-migrate.* 2>/dev/null || true
done
echo "  rm -rf ~/.claude.pre-migrate.* ~/.hermes.pre-migrate.*"
