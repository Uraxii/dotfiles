#!/bin/bash

# Usage: ./toggle_process.sh <process_name>

# $1 is an argument. Pass the proccess you want to toggle when runnong.

if [ -z "$1" ]; then
    echo "Usage: $0 <process_name>"
    exit 1
fi

PROCESS_NAME=$1

pkill $PROCESS_NAME || $PROCESS_NAME
