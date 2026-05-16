#!/usr/bin/env bash
# Battery pill emitter for tmux status bar.
#
# Outputs a fully-styled icon-fill tmux pill:
#
#   <cap-L> <icon-header> <% body> <cap-R>
#
# Icon header bg tier by capacity (success >= 60, warning >= 25, urgent < 25).
# Body section uses @thm_bg2 (gray) for visual consistency w/ other pills.
# Icon glyph swaps dynamically: charging vs discharging vs unknown vs critical.
# Silent (empty stdout, exit 0) if no battery present (desktop / VM).
#
# Glyphs are emitted via printf '\xHH' byte sequences so this script file
# stays ASCII-safe (Write tooling doesn't strip the bytes since they're
# encoded as backslash-hex literals, expanded only at runtime by printf).

set -eu

cap_file=$(ls /sys/class/power_supply/BAT*/capacity 2>/dev/null | head -1 || true)
[ -z "$cap_file" ] && exit 0

cap=$(cat "$cap_file" 2>/dev/null || true)
[ -z "$cap" ] && exit 0

state=$(cat "${cap_file%/capacity}/status" 2>/dev/null || echo "Unknown")

# NerdFont glyph byte sequences (UTF-8):
#   CAP_L  = U+E0B6 powerline left  rounded cap   = \xee\x82\xb6
#   CAP_R  = U+E0B4 powerline right rounded cap   = \xee\x82\xb4
#   CHARGE = U+F0E7 fa-bolt                       = \xef\x83\xa7
#   FULL   = U+F240 fa-battery-full               = \xef\x89\x80
#   TQ     = U+F241 fa-battery-three-quarters     = \xef\x89\x81
#   HALF   = U+F242 fa-battery-half               = \xef\x89\x82
#   Q      = U+F243 fa-battery-quarter            = \xef\x89\x83
#   EMPTY  = U+F244 fa-battery-empty              = \xef\x89\x84
CAP_L='\xee\x82\xb6'
CAP_R='\xee\x82\xb4'

# Pick capacity-level glyph (5-bucket).
if   [ "$cap" -ge 88 ]; then level='\xef\x89\x80'
elif [ "$cap" -ge 63 ]; then level='\xef\x89\x81'
elif [ "$cap" -ge 38 ]; then level='\xef\x89\x82'
elif [ "$cap" -ge 13 ]; then level='\xef\x89\x83'
else                          level='\xef\x89\x84'
fi

# Charging → bolt prefix before level glyph.
case "$state" in
    Charging|Full) icon="\xef\x83\xa7 $level" ;;
    *)             icon="$level" ;;
esac

# Color tier — read palette from tmux user options; fall back to mocha hex.
get() { tmux show -gv "$1" 2>/dev/null || true; }
thm_bg=$(get @thm_bg);   : "${thm_bg:=#1e1e2e}"
thm_bg2=$(get @thm_bg2); : "${thm_bg2:=#313244}"
thm_fg=$(get @thm_fg);   : "${thm_fg:=#cdd6f4}"
if   [ "$cap" -ge 60 ]; then color=$(get @thm_success); fb="#a6e3a1"
elif [ "$cap" -ge 25 ]; then color=$(get @thm_warning); fb="#f9e2af"
else                          color=$(get @thm_urgent);  fb="#f38ba8"
fi
: "${color:=$fb}"

# Emit icon-fill pill:
#   cap-L         (fg=color, bg=default)
#   icon header   (bg=color, fg=thm_bg)   <space><icon><space>
#   body section  (bg=thm_bg2, fg=thm_fg) <space><pct>%<space>
#   cap-R         (fg=thm_bg2, bg=default)
blink_a=""; blink_b=""
[ "$cap" -le 15 ] && { blink_a=",blink"; blink_b=",noblink"; }

printf '#[fg=%s,bg=default]' "$color"
printf %b "$CAP_L"
printf '#[bg=%s,fg=%s%s] ' "$color" "$thm_bg" "$blink_a"
printf %b "$icon"
printf ' #[bg=%s,fg=%s%s] %d%% #[fg=%s,bg=default]' \
    "$thm_bg2" "$thm_fg" "$blink_b" "$cap" "$thm_bg2"
printf %b "$CAP_R"
