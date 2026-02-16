#!/bin/bash
# Launch Ghidra inside the VNC display for GhidraMCP
# Usage: ghidra-vnc.sh [ghidra-project-file]

DISPLAY_NUM=99
export DISPLAY=":${DISPLAY_NUM}"

# Check VNC is running
if ! xdpyinfo -display ":${DISPLAY_NUM}" >/dev/null 2>&1; then
    echo "ERROR: VNC display :${DISPLAY_NUM} is not running"
    echo "Start it first: scripts/vnc-display.sh start"
    exit 1
fi

echo "Launching Ghidra on DISPLAY=:${DISPLAY_NUM}..."
echo "Remember to enable GhidraMCPPlugin: File > Configure > Developer > GhidraMCPPlugin"
exec /home/tim/tools/ghidra/ghidraRun "$@"
