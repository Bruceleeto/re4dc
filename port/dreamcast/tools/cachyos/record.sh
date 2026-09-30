#!/bin/bash
# Records the screen (or a window you pick) at 60 fps with GPU Screen Recorder, hardware-encoded so Flycast keeps
# the CPU: the native `gpu-screen-recorder` if installed (CachyOS / AUR package), else Flathub
# com.dec05eba.gpu_screen_recorder. Wayland: the first run opens the desktop's screen-share picker (choose the
# Flycast window or the screen); later runs reuse it. Ctrl+C (or closing the terminal) stops and saves.
# Usage: record.sh [output.mp4]
set -euo pipefail
OUT=${1:-"$HOME/Videos/RE4DC/re4dc-$(date +%Y%m%d-%H%M%S).mp4"}
mkdir -p "$(dirname "$OUT")"
OPTS=(-w portal -restore-portal-session yes -f 60 -a default_output -o "$OUT")
[ -n "${WAYLAND_DISPLAY:-}" ] || OPTS=(-w screen -f 60 -a default_output -o "$OUT")   # X11 session
echo "Recording to $OUT  (Ctrl+C to stop)"
if command -v gpu-screen-recorder >/dev/null 2>&1; then
  exec gpu-screen-recorder "${OPTS[@]}"
fi
exec flatpak run --command=gpu-screen-recorder com.dec05eba.gpu_screen_recorder "${OPTS[@]}"
