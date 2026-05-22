#!/usr/bin/env bash
# Battery pill emitter for tmux status bar.
#
# Outputs a fully-styled icon-fill tmux pill:
#
#   <cap-L> <icon-header> <% body> <cap-R>
#
# Header bg tier by capacity (success >= 60, warning >= 25, urgent < 25).
# Body section uses @thm_bg2 (gray) for visual consistency w/ other pills.
# Single icon, dynamic by state:
#
#   Charging / Full   → U+F0084 nf-md-battery_charging (lightning over batt)
#   Discharging       → U+F0079 nf-md-battery
#   Capacity < 5%     → U+F008E nf-md-battery_outline (visual alert)
#   Unknown           → U+F007D nf-md-battery_40
#
# Silent (empty stdout, exit 0) if no battery present (desktop / VM).
#
# Glyphs are emitted via printf '\xHH' byte sequences so this script file
# stays ASCII on disk (Write tooling doesn't strip).

set -eu

cap_file=$(ls /sys/class/power_supply/BAT*/capacity 2>/dev/null | head -1 || true)
[ -z "$cap_file" ] && exit 0

cap=$(cat "$cap_file" 2>/dev/null || true)
[ -z "$cap" ] && exit 0

state=$(cat "${cap_file%/capacity}/status" 2>/dev/null || echo "Unknown")

# Glyph byte sequences (UTF-8).
#   CAP_L      U+E0B6   = \xee\x82\xb6   left  pill cap (powerline-extra)
#   CAP_R      U+E0B4   = \xee\x82\xb4   right pill cap
#   CHARGING   U+F0084  = \xf3\xb0\x82\x84   nf-md-battery_charging (bolt)
#   FULL       U+F0079  = \xf3\xb0\x81\xb9   nf-md-battery (full rect)
#   B90        U+F0082  = \xf3\xb0\x82\x82   nf-md-battery_90
#   B70        U+F0080  = \xf3\xb0\x82\x80   nf-md-battery_70
#   LOW        U+F12A1  = \xf3\xb1\x8a\xa1   nf-md-battery_low (modern rounded)
#
# Discharge tier (icon morphs by capacity):
#   >=85  → FULL
#   >=60  → B90
#   >=30  → B70
#   < 30  → LOW
# Charging state overrides w/ CHARGING regardless of capacity.
CAP_L='\xee\x82\xb6'
CAP_R='\xee\x82\xb4'

case "$state" in
    Charging|Full) icon='\xf3\xb0\x82\x84' ;;
    *)
        if   [ "$cap" -ge 85 ]; then icon='\xf3\xb0\x81\xb9'
        elif [ "$cap" -ge 60 ]; then icon='\xf3\xb0\x82\x82'
        elif [ "$cap" -ge 30 ]; then icon='\xf3\xb0\x82\x80'
        else                          icon='\xf3\xb1\x8a\xa1'
        fi
        ;;
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

blink_a=""; blink_b=""
[ "$cap" -le 15 ] && { blink_a=",blink"; blink_b=",noblink"; }

printf '#[fg=%s,bg=default]' "$color"
printf %b "$CAP_L"
printf '#[bg=%s,fg=%s%s] ' "$color" "$thm_bg" "$blink_a"
printf %b "$icon"
printf ' #[bg=%s,fg=%s%s] %d%% #[fg=%s,bg=default]' \
    "$thm_bg2" "$thm_fg" "$blink_b" "$cap" "$thm_bg2"
printf %b "$CAP_R"
