#!/bin/bash
# Grab one settled frame from the Magewell HDMI capture (/dev/video0) into a PNG.
# Runs ON rpi4-asus-aspeed2050-dev.  Grabs several frames and keeps the last
# (-update 1) because v4l2's first dequeued buffer is often flagged corrupt.
#   grabframe.sh [outfile]     default: ~/hw-capture/frame.png
set -euo pipefail
out="${1:-$HOME/hw-capture/frame.png}"
mkdir -p "$(dirname "$out")"
# Serialise access to the single Magewell capture device: v4l2 allows only one
# opener at a time, so concurrent grabs must not overlap (else "device busy").
# All rig users run as 'tim', so a per-user lock file is a shared mutex.
exec 9>"$HOME/.video0.lock"
flock 9
ffmpeg -hide_banner -loglevel error -f v4l2 -input_format yuyv422 \
    -i /dev/video0 -frames:v 6 -update 1 -y "$out"
printf '%s (%s bytes)\n' "$out" "$(stat -c %s "$out")"
