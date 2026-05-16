#!/usr/bin/env bash
# Substitute NerdFont glyph tokens in tmux.conf with literal UTF-8 bytes.
# Runs in-place. Tokens are ASCII placeholders that survive any tooling
# that strips high-codepoint chars on write (some web/editor pipelines).
#
# Usage:
#   ./scripts/glyphs.sh                 # patch ~/dotfiles/.config/tmux/tmux.conf
#   ./scripts/glyphs.sh path/to/file    # patch arbitrary file
#
# Codepoints picked from FontAwesome classic range (U+F0xx, U+F1xx) +
# Devicons for python — these have universal coverage across NerdFont
# versions. Pill caps use Powerline private-use codepoints.

set -eu

target=${1:-$HOME/dotfiles/.config/tmux/tmux.conf}
[ -f "$target" ] || { echo "glyphs.sh: target not found: $target" >&2; exit 1; }

# Token codepoint glyph map.
#   __CAP_L__  U+E0B6   left  rounded pill cap (powerline-extra)
#   __CAP_R__  U+E0B4   right rounded pill cap (powerline-extra)
#   __DIR__    U+F115   folder-open-o (fa-folder_open_o)
#   __GIT__    U+F126   code-fork (fa-code_fork)
#   __VENV__   U+E73C   python alt (dev-python_alt)
#   __USER__   U+F007   user (fa-user)
#   __CLOCK__  U+F017   clock-o (fa-clock_o)
declare -A glyphs=(
    [__CAP_L__]=$''
    [__CAP_R__]=$''
    [__DIR__]=$''
    [__GIT__]=$''
    [__VENV__]=$''
    [__USER__]=$''
    [__CLOCK__]=$''
)

tmp=$(mktemp)
cp "$target" "$tmp"
for token in "${!glyphs[@]}"; do
    glyph=${glyphs[$token]}
    sed -i "s|$token|$glyph|g" "$tmp"
done
mv "$tmp" "$target"
echo "glyphs.sh: patched $target"
