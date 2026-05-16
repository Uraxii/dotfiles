#!/usr/bin/env bash
# tmux-specific token registry. Wraps ~/dotfiles/scripts/nerd-glyph with the
# canonical TOKEN=CODEPOINT pairs used in tmux.conf. Run after every edit
# that introduces a new placeholder, or to restore bytes after tooling
# strips them. Idempotent.
#
# Usage:
#   ./glyphs.sh                 # patch ~/dotfiles/.config/tmux/tmux.conf
#   ./glyphs.sh path/to/file    # patch arbitrary file w/ same registry
#
# Adding a glyph: append to the PAIRS array below + reference __TOKEN__ in
# tmux.conf, then run this script. To add ad-hoc glyphs to one-off files,
# call nerd-glyph sub directly.

set -eu

target=${1:-$HOME/dotfiles/.config/tmux/tmux.conf}
[ -f "$target" ] || { echo "glyphs.sh: target not found: $target" >&2; exit 1; }

NERD_GLYPH=${NERD_GLYPH:-$HOME/dotfiles/scripts/nerd-glyph}
[ -x "$NERD_GLYPH" ] || { echo "glyphs.sh: nerd-glyph not executable: $NERD_GLYPH" >&2; exit 2; }

# Token=Codepoint registry. Keep aligned for diff hygiene.
PAIRS=(
    __CAP_L__=E0B6     # left  rounded pill cap (powerline-extra)
    __CAP_R__=E0B4     # right rounded pill cap (powerline-extra)
    __DIR__=F115       # folder-open-o (fa)
    __GIT__=F126       # code-fork (fa)
    __VENV__=E73C      # python alt (dev)
    __USER__=F007      # user (fa)
    __HOST__=F233      # server (fa)
    __CLOCK__=F017     # clock-o (fa)
    __SESSION__=F2D0   # window-maximize (fa) — session pill icon
)

"$NERD_GLYPH" sub "$target" "${PAIRS[@]}"
