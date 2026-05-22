#!/bin/sh
# Power menu via swaynag (no rofi dep). Wired to custom/logo on-click.
#
# Buttons: Lock, Logout, Reboot, Shutdown, Suspend, Cancel.
#
# Lock uses ~/.config/sway/scripts/lock_system.sh if present; falls back
# to swaylock.

LOCK="$HOME/.config/sway/scripts/lock_system.sh"
[ -x "$LOCK" ] || LOCK="swaylock -f"

exec swaynag \
    -t warning \
    -m "Power" \
    --button "Lock"     "$LOCK" \
    --button "Logout"   "swaymsg exit" \
    --button "Suspend"  "systemctl suspend" \
    --button "Reboot"   "systemctl reboot" \
    --button "Shutdown" "systemctl poweroff"
