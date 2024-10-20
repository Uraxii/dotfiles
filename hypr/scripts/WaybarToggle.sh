#!/bin/bash

if pgrep -x "waybar" > /dev/null
then
    # Waybar is running. Let's close it.
    pkill waybar
else
    # Waybar is NOT running, Let's start it in the background.
    waybar &
fi
