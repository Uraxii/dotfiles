#!/usr/bin/env bash
# battery_monitor.sh — graceful low-battery handling for Sway sessions

POLL_INTERVAL="${POLL_INTERVAL:-30}"
LOW_THRESHOLD="${LOW_THRESHOLD:-20}"
WARN_THRESHOLD="${WARN_THRESHOLD:-10}"
CRITICAL_THRESHOLD="${CRITICAL_THRESHOLD:-5}"
CRITICAL_GRACE_SECONDS="${CRITICAL_GRACE_SECONDS:-30}"

LOCK_SCRIPT="$HOME/.config/sway/scripts/lock_system.sh"
NOTIFIED_LEVEL="none" # none, low, warning, critical

find_battery_path() {
    for p in /sys/class/power_supply/BAT*; do
        [ -d "$p" ] || continue
        [ -f "$p/type" ] || continue
        if grep -qx "Battery" "$p/type"; then
            printf '%s\n' "$p"
            return 0
        fi
    done
    return 1
}

BAT_PATH="$(find_battery_path || true)"
if [ -z "$BAT_PATH" ]; then
    exit 0
fi

get_percent() {
    cat "$BAT_PATH/capacity" 2>/dev/null
}

get_status() {
    cat "$BAT_PATH/status" 2>/dev/null
}

notify() {
    urgency="$1"
    title="$2"
    body="$3"
    if command -v notify-send >/dev/null 2>&1; then
        notify-send -u "$urgency" "$title" "$body"
    fi
}

set_profile() {
    profile="$1"
    if command -v powerprofilesctl >/dev/null 2>&1; then
        powerprofilesctl set "$profile" >/dev/null 2>&1 || true
    fi
}

set_dimmed_brightness() {
    if command -v brightnessctl >/dev/null 2>&1; then
        brightnessctl set 30% >/dev/null 2>&1 || true
    fi
}

while true; do
    percent="$(get_percent)"
    status="$(get_status)"

    if [ -z "$percent" ] || [ -z "$status" ]; then
        sleep "$POLL_INTERVAL"
        continue
    fi

    if [ "$status" = "Discharging" ]; then
        if [ "$percent" -le "$CRITICAL_THRESHOLD" ] && [ "$NOTIFIED_LEVEL" != "critical" ]; then
            NOTIFIED_LEVEL="critical"
            notify critical "Battery Critical" "Battery ${percent}%. Suspending in ${CRITICAL_GRACE_SECONDS}s."
            sleep "$CRITICAL_GRACE_SECONDS"

            percent="$(get_percent)"
            status="$(get_status)"
            if [ "$status" = "Discharging" ] && [ "$percent" -le "$CRITICAL_THRESHOLD" ]; then
                [ -x "$LOCK_SCRIPT" ] && "$LOCK_SCRIPT"
                systemctl suspend
            fi

        elif [ "$percent" -le "$WARN_THRESHOLD" ] && [ "$NOTIFIED_LEVEL" != "warning" ] && [ "$NOTIFIED_LEVEL" != "critical" ]; then
            NOTIFIED_LEVEL="warning"
            notify critical "Battery Warning" "Battery ${percent}%. Plug in soon."
            set_dimmed_brightness
            set_profile power-saver

        elif [ "$percent" -le "$LOW_THRESHOLD" ] && [ "$NOTIFIED_LEVEL" = "none" ]; then
            NOTIFIED_LEVEL="low"
            notify normal "Battery Low" "Battery ${percent}%. Power-saver enabled."
            set_profile power-saver
        fi
    else
        if [ "$NOTIFIED_LEVEL" != "none" ]; then
            NOTIFIED_LEVEL="none"
            set_profile balanced
        fi
    fi

    sleep "$POLL_INTERVAL"
done
