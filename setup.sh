#!/usr/bin/env bash
# setup.sh — deploy dotfiles via stow + link breakers.
#
# Stow target is ~/.config (see .stowrc). Tools that hardcode $HOME paths
# (zsh, claude-code, hermes, xonsh) get a symlink from $HOME/<name> →
# ~/.config/<name> so they find their config.
#
# Idempotent. Safe to re-run after edits.
#
# Usage:
#   ./setup.sh            # stow + link
#   ./setup.sh restow     # stow -R (restow: unstow + stow, repoint stale links)
#   ./setup.sh unstow     # stow -D + remove breaker symlinks
#   ./setup.sh dry        # stow -n -v (dry run, no changes)

set -eu

cd "$(dirname "$(readlink -f "$0")")"

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

link_breakers() {
    mkdir -p "$CONFIG"
    for entry in "${BREAKERS[@]}"; do
        name=${entry%=*}
        src="$CONFIG/$name"
        dst="$HOME/$name"
        if [ ! -e "$src" ]; then
            echo "skip $name (not stowed yet at $src)"
            continue
        fi
        if [ -L "$dst" ] && [ "$(readlink "$dst")" = "$src" ]; then
            continue  # already correct
        fi
        if [ -e "$dst" ] && [ ! -L "$dst" ]; then
            echo "WARN: $dst exists and is not a symlink — refusing to clobber" >&2
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
        echo "--- breaker symlinks (preview) ---"
        for entry in "${BREAKERS[@]}"; do
            name=${entry%=*}
            echo "  $HOME/$name -> $CONFIG/$name"
        done
        ;;
    *)
        echo "usage: $0 [stow|restow|unstow|dry]" >&2
        exit 2
        ;;
esac
