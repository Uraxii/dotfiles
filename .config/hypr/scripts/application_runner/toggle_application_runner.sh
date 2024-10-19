#!/bin/bash

selection=tofi

# Define the Taskbar associative array
declare -A apps=(
    [rofi]="rofi"
    [tofi]="tofi-drun"
)

declare -A arguments=(
    [rofi]="-show drun -modi drun,filebrowser,run,window"
    [tofi]="--drun-launch=true"
)


# Check if TASK_BAR_PROCESS is empty and exit if it is
if [ -z $selection ]; then
    echo "Selection is empty! This will kill all processes. Exiting."
    exit 1
fi

app_to_run=${apps[$selection]}
app_arguments=${arguments[$selection]}

echo "app to run=${app_to_run}, app argument=${app_arguments}"

# Kill the existing process or start the new one
pkill $app_to_run || $app_to_run $app_arguments &
