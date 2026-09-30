#!/bin/bash
# RE4 Dreamcast play build on CachyOS (or any Arch-based desktop): runs disc/disc.cue in Flycast with the play
# settings (NTSC / USA, TV cable, framebuffer emulation, vsync, windowed; F11 toggles fullscreen). The settings are
# passed with -config (transient), so the user's own Flycast config is left untouched.
# Flycast, in this order: $RE4DC_FLYCAST (a path), a native `flycast` on PATH (AUR / chaotic-aur package), the
# Flathub build org.flycast.Flycast (installed for the user if Flatpak is present). No sudo.
# Template for the *-CachyOS.tar.gz release packages (docs/CACHYOS_PLAY.md).
set -u
DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
CUE="$DIR/disc/disc.cue"
[ -f "$CUE" ] || { echo "missing $CUE (keep play.sh next to the disc folder)"; exit 1; }
ARGS=(-config config:Dreamcast.Broadcast=0
      -config config:Dreamcast.Cable=3
      -config config:Dreamcast.Region=1
      -config config:rend.EmulateFramebuffer=yes
      -config config:rend.vsync=yes
      -config window:fullscreen=no)
if [ -n "${RE4DC_FLYCAST:-}" ]; then
  exec "$RE4DC_FLYCAST" "${ARGS[@]}" "$CUE"
fi
if command -v flycast >/dev/null 2>&1; then
  exec flycast "${ARGS[@]}" "$CUE"
fi
if command -v flatpak >/dev/null 2>&1; then
  APP=org.flycast.Flycast
  if ! flatpak info "$APP" >/dev/null 2>&1; then
    echo "Flycast is not installed; installing it from Flathub (user install)..."
    flatpak remote-add --user --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo &&
      flatpak install --user -y flathub "$APP" ||
      { echo "Install failed. Install Flycast yourself (see below), then run this again."; exit 1; }
  fi
  exec flatpak run --filesystem="$DIR" "$APP" "${ARGS[@]}" "$CUE"
fi
cat <<'EOF'
Flycast was not found. Install it one of these ways, then run play.sh again:
  paru -S flycast            (AUR; or yay -S flycast, or flycast-git from chaotic-aur)
  sudo pacman -S flatpak     (then play.sh installs Flathub's org.flycast.Flycast for your user)
EOF
exit 1
