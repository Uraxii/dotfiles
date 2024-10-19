#!/bin/bash

# Define the Taskbar associative array
declare -A Taskbars=(
    [GBAR]="gBar"
    [WAYBAR]="waybar"
)

# YOUR TASKBAR TYPE HERE!
TASKBAR=${Taskbars[WAYBAR]}
#ARGUMENTS="bar DP-2"


# Check if TASK_BAR_PROCESS is empty and exit if it is
if [ -z "$TASKBAR" ]; then
    echo "TASKBAR is empty! This will kill all processes. Exiting."
    exit 1
fi

# Kill the existing process or start the new one
pkill $TASKBAR || $TASKBAR $ARGUMENTS &
