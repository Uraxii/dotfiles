#!/bin/bash
# battery_monitor.sh — graduated low-battery actions for Sway
# Polls battery status and takes action: notify, power-save, dim, suspend

POLL_INTERVAL=60
NOTIFIED_LEVEL="none" # none, low, warning, critical

BAT_PATH="/sys/class/power_supply/BAT0"
LOCK_SCRIPT="$HOME/.config/sway/scripts/lock_system.sh"

get_percent() { cat "$BAT_PATH/capacity"; }
get_status()  { cat "$BAT_PATH/status"; }

while true; do
    percent=$(get_percent)
    status=$(get_status)

    if [ "$status" = "Discharging" ]; then
        if [ "$percent" -le 8 ] && [ "$NOTIFIED_LEVEL" != "critical" ]; then
            NOTIFIED_LEVEL="critical"
            notify-send -u critical "Battery Critical" \
                "Battery at ${percent}%. Suspending in 60 seconds."
            sleep 60

            percent=$(get_percent)
            status=$(get_status)
            if [ "$status" = "Discharging" ] && [ "$percent" -le 8 ]; then
                "$LOCK_SCRIPT"
                systemctl suspend
            fi

        elif [ "$percent" -le 15 ] && [ "$NOTIFIED_LEVEL" != "warning" ] && [ "$NOTIFIED_LEVEL" != "critical" ]; then
            NOTIFIED_LEVEL="warning"
            notify-send -u critical "Battery Warning" \
                "Battery at ${percent}%. Plug in soon."
            brightnessctl set 30%
            powerprofilesctl set power-saver

        elif [ "$percent" -le 30 ] && [ "$NOTIFIED_LEVEL" = "none" ]; then
            NOTIFIED_LEVEL="low"
            notify-send -u normal "Battery Low" \
                "Battery at ${percent}%. Switching to power saver."
            powerprofilesctl set power-saver
        fi
    else
        if [ "$NOTIFIED_LEVEL" != "none" ]; then
            NOTIFIED_LEVEL="none"
            powerprofilesctl set balanced
        fi
    fi

    sleep "$POLL_INTERVAL"
done
