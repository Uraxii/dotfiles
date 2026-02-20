#!/bin/bash

while getopts lock_delay:display_off_delay: option
do 
    case "${option}"
        in
        l)lock_delay=${OPTARG};;
        d)display_off_delay=${OPTARG};;
    esac
done

system_lock_script="$HOME/.config/sway/scipts/lock.sh"

exec swayidle -w \
         timeout $lock_delay $system_lock_script \
         timeout $display_off_delay 'swaymsg "output * power off"' resume 'swaymsg "output * power on"'.
         before-sleep $system_lock_script

