#!/bin/bash

# Actually this file is from ISO rootfs
AUTOSTART_FILE='/run/initramfs/live/autostart.sh'

echo "Checking for presense of file '$AUTOSTART_FILE' ..."
if [ ! -f "$AUTOSTART_FILE" ]; then
    echo "Can't find file '$AUTOSTART_FILE'."
    echo "Nothing to do. Entry point for autostart not found."
    exit 1
fi

exec /bin/bash "$AUTOSTART_FILE"
