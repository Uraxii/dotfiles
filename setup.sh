#!/usr/bin/env bash
# setup.sh — deploy dotfiles via stow + link breakers + auto-merge runtime.
#
# Stow target is ~/.config (see .stowrc). Tools that hardcode $HOME paths
# (zsh, claude-code, hermes, xonsh) get a symlink from $HOME/<name> →
# ~/.config/<name> so they find their config.
#
# If a breaker path at $HOME exists as a real directory (e.g. ~/.hermes/
# with live runtime state), setup.sh rsyncs its contents into the stowed
# tree (--ignore-existing: tracked files win), backs the original up to
# <path>.pre-migrate.<epoch>, then replaces it with the symlink.
#
# Daemon-safety guard: refuses to merge if claude-code or hermes processes
# are detected. Override with --force (dangerous if SQLite WAL is hot).
#
# Idempotent. Safe to re-run after edits.
#
# Usage:
#   ./setup.sh            # stow + link + auto-merge runtime
#   ./setup.sh restow     # stow -R + relink + auto-merge
#   ./setup.sh unstow     # remove breaker symlinks + stow -D
#   ./setup.sh dry        # preview, no changes
#   ./setup.sh --force …  # bypass daemon-detection guard

set -eu

cd "$(dirname "$(readlink -f "$0")")"

FORCE=0
if [ "${1:-}" = "--force" ]; then
    FORCE=1
    shift
fi

CMD=${1:-stow}
CONFIG="$HOME/.config"

# Breakers: stow puts these at ~/.config/<name>; tool expects $HOME/<name>.
# name=kind (dir|file). swaylock NOT here — it reads XDG natively.
BREAKERS=(
    ".claude=dir"
    ".hermes=dir"
    ".zshrc=file"
    ".xonshrc=file"
    ".zprofile=file"
)

# Processes that, if running, make runtime-dir merges unsafe.
DAEMON_PATTERNS="claude-code|claude_code|hermes-agent|hermes_agent"

check_daemons_stopped() {
    [ "$FORCE" -eq 1 ] && return 0
    if pgrep -af "$DAEMON_PATTERNS" >/dev/null 2>&1; then
        echo "ERROR: live daemon detected — runtime-dir merge unsafe:" >&2
        pgrep -af "$DAEMON_PATTERNS" >&2
        echo "" >&2
        echo "Options:" >&2
        echo "  1. Stop the daemon(s) and re-run ./setup.sh" >&2
        echo "  2. ./setup.sh --force (DANGEROUS: corrupts active SQLite WALs)" >&2
        return 1
    fi
    return 0
}

merge_real_dir() {
    # $1 = name (e.g. .hermes), $2 = src (~/.config/.hermes), $3 = dst (~/.hermes)
    local name=$1 src=$2 dst=$3
    echo "merging $dst/ -> $src/ (--ignore-existing: tracked files win)"
    rsync -a --ignore-existing "$dst/" "$src/"
    local backup="$dst.pre-migrate.$(date +%s)"
    mv "$dst" "$backup"
    echo "  backed up $dst -> $backup"
    ln -sn "$src" "$dst"
    echo "  linked $dst -> $src"
}

merge_real_file() {
    # $1 = name, $2 = src, $3 = dst
    local name=$1 src=$2 dst=$3
    local backup="$dst.pre-migrate.$(date +%s)"
    mv "$dst" "$backup"
    echo "  backed up $dst -> $backup"
    # Tracked file at src already has its content; user-edited copy in backup.
    ln -sf "$src" "$dst"
    echo "  linked $dst -> $src"
    echo "  NOTE: user edits preserved in $backup — diff vs $src if you customized."
}

link_breakers() {
    mkdir -p "$CONFIG"
    local merge_needed=0
    # First pass: detect any merges needed → run daemon check once.
    for entry in "${BREAKERS[@]}"; do
        name=${entry%=*}
        dst="$HOME/$name"
        src="$CONFIG/$name"
        [ -e "$src" ] || continue
        if [ -e "$dst" ] && [ ! -L "$dst" ]; then
            merge_needed=1
            break
        fi
    done
    if [ "$merge_needed" -eq 1 ]; then
        check_daemons_stopped || return 1
    fi

    for entry in "${BREAKERS[@]}"; do
        name=${entry%=*}
        kind=${entry#*=}
        src="$CONFIG/$name"
        dst="$HOME/$name"

        if [ ! -e "$src" ]; then
            echo "skip $name (not stowed yet at $src)"
            continue
        fi
        if [ -L "$dst" ] && [ "$(readlink "$dst")" = "$src" ]; then
            continue  # already correct
        fi
        if [ -L "$dst" ]; then
            target=$(readlink "$dst")
            echo "WARN: $dst is symlink to $target — leaving alone, fix manually" >&2
            continue
        fi
        if [ -e "$dst" ]; then
            # Real file/dir exists — merge.
            if [ "$kind" = "dir" ] && [ -d "$dst" ]; then
                merge_real_dir "$name" "$src" "$dst"
            elif [ "$kind" = "file" ] && [ -f "$dst" ]; then
                merge_real_file "$name" "$src" "$dst"
            else
                echo "WARN: $dst type mismatch (expected $kind) — skipping" >&2
            fi
            continue
        fi
        ln -sfn "$src" "$dst"
        echo "linked $dst -> $src"
    done
}

unlink_breakers() {
    for entry in "${BREAKERS[@]}"; do
        name=${entry%=*}
        dst="$HOME/$name"
        src="$CONFIG/$name"
        if [ -L "$dst" ] && [ "$(readlink "$dst")" = "$src" ]; then
            rm "$dst"
            echo "removed symlink $dst"
        fi
    done
}

case "$CMD" in
    stow)
        stow .
        link_breakers
        ;;
    restow)
        stow -R .
        link_breakers
        ;;
    unstow)
        unlink_breakers
        stow -D .
        ;;
    dry)
        stow -n -v .
        echo "--- breaker plan (preview) ---"
        for entry in "${BREAKERS[@]}"; do
            name=${entry%=*}
            kind=${entry#*=}
            dst="$HOME/$name"
            src="$CONFIG/$name"
            if [ -L "$dst" ] && [ "$(readlink "$dst")" = "$src" ]; then
                echo "  ok    $dst (already symlinked)"
            elif [ -e "$dst" ] && [ ! -L "$dst" ]; then
                echo "  merge $dst ($kind, real $kind exists) -> rsync + backup + symlink"
            else
                echo "  link  $dst -> $src"
            fi
        done
        ;;
    *)
        echo "usage: $0 [--force] [stow|restow|unstow|dry]" >&2
        exit 2
        ;;
esac

# Surface backup paths if any merges happened this run.
backups=$(ls -d "$HOME"/.{claude,hermes,zshrc,xonshrc,zprofile}.pre-migrate.* 2>/dev/null || true)
if [ -n "$backups" ]; then
    echo ""
    echo "Backups present (verify, then remove):"
    echo "$backups"
fi
