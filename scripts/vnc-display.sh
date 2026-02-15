#!/bin/bash
# Manage the shared VNC display for MCP servers (Ghidra, Playwright)
# Usage: vnc-display.sh start|stop|status

DISPLAY_NUM=99
VNC_GEOMETRY=1920x1080
VNC_DEPTH=24
PIDFILE="$HOME/.vnc/$(hostname -f):${DISPLAY_NUM}.pid"

case "${1:-status}" in
    start)
        if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>&1; then
            echo "VNC display :${DISPLAY_NUM} already running (PID $(cat "$PIDFILE"))"
            exit 0
        fi
        echo "Starting VNC display :${DISPLAY_NUM} (${VNC_GEOMETRY}x${VNC_DEPTH})..."
        vncserver ":${DISPLAY_NUM}" \
            -geometry "$VNC_GEOMETRY" \
            -depth "$VNC_DEPTH" \
            -localhost yes \
            -SecurityTypes VncAuth
        echo "VNC server started. Connect with: vncviewer localhost:${DISPLAY_NUM}"
        echo "Or tunnel: ssh -L 5999:localhost:5999 $(hostname)"
        ;;
    stop)
        echo "Stopping VNC display :${DISPLAY_NUM}..."
        vncserver -kill ":${DISPLAY_NUM}" 2>&1 || true
        ;;
    status)
        if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>&1; then
            echo "VNC display :${DISPLAY_NUM} is running (PID $(cat "$PIDFILE"))"
            echo "  DISPLAY=:${DISPLAY_NUM}"
            echo "  Port: $((5900 + DISPLAY_NUM))"
        else
            echo "VNC display :${DISPLAY_NUM} is not running"
        fi
        ;;
    *)
        echo "Usage: $0 {start|stop|status}"
        exit 1
        ;;
esac
