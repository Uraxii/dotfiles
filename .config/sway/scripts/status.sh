#!/bin/sh

FLASH=0

while true; do
    BAT=$(cat /sys/class/power_supply/BAT0/capacity 2>/dev/null)
    STATUS=$(cat /sys/class/power_supply/BAT0/status 2>/dev/null)

    case "$STATUS" in
        Charging) ICON="⚡"; COLOR="#ffffff" ;;
        Full)     ICON="🔋"; COLOR="#00ff00" ;;
        *)
            if [ "$BAT" -ge 80 ]; then
                ICON="🔋"; COLOR="#00ff00"
            elif [ "$BAT" -ge 20 ]; then
                ICON="🔋"; COLOR="#ffff00"
            elif [ "$BAT" -ge 10 ]; then
                ICON="🪫"; COLOR="#ff4444"
            else
                COLOR="#ff4444"
                if [ "$FLASH" -eq 0 ]; then
                    ICON="🪫"
                    FLASH=1
                else
                    ICON="  "
                    FLASH=0
                fi
            fi ;;
    esac

    echo "<span color='$COLOR'>$ICON $BAT%</span>  $(date +'%d %X')"
    sleep 1
done
