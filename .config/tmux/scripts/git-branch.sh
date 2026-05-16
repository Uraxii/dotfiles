#!/usr/bin/env bash
# Git branch pill emitter for tmux status bar — icon-fill structure.
#
# Outputs:
#   <cap-L> <icon header: branch glyph> <body: branch name> <cap-R>
#
# Icon header uses @thm_success bg; body uses @thm_bg2 (gray). Empty stdout
# when not in a repo so the surrounding tmux format string collapses cleanly.
#
# Glyphs emitted via printf \xHH so this script stays ASCII on disk.

set -eu

path=${1:-$PWD}
cd "$path" 2>/dev/null || exit 0
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0

branch=$(git branch --show-current 2>/dev/null || true)
if [ -z "$branch" ]; then
    branch=$(git rev-parse --short HEAD 2>/dev/null || true)
fi
[ -z "$branch" ] && exit 0

# Glyphs (UTF-8 byte sequences):
#   CAP_L = U+E0B6 powerline left  rounded cap = \xee\x82\xb6
#   CAP_R = U+E0B4 powerline right rounded cap = \xee\x82\xb4
#   GIT   = U+F126 fa-code-fork                = \xef\x84\xa6
CAP_L='\xee\x82\xb6'
CAP_R='\xee\x82\xb4'
GIT='\xef\x84\xa6'

get() { tmux show -gv "$1" 2>/dev/null || true; }
thm_bg=$(get @thm_bg);     : "${thm_bg:=#1e1e2e}"
thm_bg2=$(get @thm_bg2);   : "${thm_bg2:=#313244}"
thm_fg=$(get @thm_fg);     : "${thm_fg:=#cdd6f4}"
color=$(get @thm_success); : "${color:=#a6e3a1}"

printf '#[fg=%s,bg=default]' "$color"
printf %b "$CAP_L"
printf '#[bg=%s,fg=%s] ' "$color" "$thm_bg"
printf %b "$GIT"
printf ' #[bg=%s,fg=%s] %s #[fg=%s,bg=default]' \
    "$thm_bg2" "$thm_fg" "$branch" "$thm_bg2"
printf %b "$CAP_R"
printf ' '
