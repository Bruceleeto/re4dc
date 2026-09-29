#!/bin/bash
# Records the screen (or a window you pick) at 60 fps with GPU Screen Recorder (Flathub
# com.dec05eba.gpu_screen_recorder), hardware-encoded so Flycast keeps the CPU. Desktop Mode only.
# The first run opens the desktop's screen-share picker (choose the Flycast window or the screen);
# later runs reuse that choice. Ctrl+C (or closing the terminal) stops and saves.
# Usage: record.sh [output.mp4]
set -euo pipefail
OUT=${1:-"$HOME/Videos/RE4DC/re4dc-$(date +%Y%m%d-%H%M%S).mp4"}
mkdir -p "$(dirname "$OUT")"
echo "Recording to $OUT  (Ctrl+C to stop)"
exec flatpak run --command=gpu-screen-recorder com.dec05eba.gpu_screen_recorder \
  -w portal -restore-portal-session yes -f 60 -a default_output -o "$OUT"
