#!/bin/bash
# RE4 Dreamcast play build on SteamOS: runs disc/disc.cue in Flycast (Flathub org.flycast.Flycast)
# with the play settings (NTSC / USA, TV cable, framebuffer emulation, vsync, windowed; F11 toggles fullscreen). The
# settings are passed with -config (transient), so the user's own Flycast config is left untouched.
# Template for the *-SteamOS.tar.gz release packages (docs/STEAMOS_PLAY.md).
DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
APP=org.flycast.Flycast
if ! flatpak info "$APP" >/dev/null 2>&1; then
  echo "Flycast is not installed; installing it from Flathub (user install)..."
  flatpak install --user -y flathub "$APP" || { echo "Install failed: install Flycast from Discover, then run this again."; read -r -t 30 _; exit 1; }
fi
exec flatpak run --filesystem="$DIR" "$APP" \
  -config config:Dreamcast.Broadcast=0 \
  -config config:Dreamcast.Cable=3 \
  -config config:Dreamcast.Region=1 \
  -config config:rend.EmulateFramebuffer=yes \
  -config config:rend.vsync=yes \
  -config window:fullscreen=no \
  "$DIR/disc/disc.cue"
