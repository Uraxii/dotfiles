#!/bin/bash

VM_PATH="/home/nicole-brandon/vmware/Windows 11 x64/Windows 11 x64.vmx"

vmrun -vp "thisissecure" start "$VM_PATH"
sleep 10

# Optional: If you want to ensure it's in fullscreen
# (This may require additional commands depending on your setup)
