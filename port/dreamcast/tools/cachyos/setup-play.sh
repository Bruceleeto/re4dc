#!/bin/bash
# RE4 Dreamcast play machine setup for CachyOS (or any Arch-based desktop), user-level only (no sudo; the system
# packages it may need are printed for the user to install). Idempotent: safe to run again.
#   1. gh CLI (a system `gh` if present, else the official cli/cli release in ~/.local/bin), `gh auth login` if needed
#   2. downloads a play release's *-CachyOS.tar.gz from the private repo and verifies its sha256
#   3. Flycast and GPU Screen Recorder: native packages if installed, else Flathub (--user) if Flatpak is present;
#      OBS with --obs
#   4. a desktop menu entry for the build's play.sh (~/.local/share/applications) unless --no-desktop
# Usage: setup-play.sh [--tag play-...] [--dir ~/Games/RE4DC] [--obs] [--no-desktop]
set -euo pipefail
REPO=lamb2k/re4dc
TAG=""
DEST="$HOME/Games/RE4DC"
OBS=0
DESKTOP=1
while [ $# -gt 0 ]; do
  case "$1" in
    --tag) TAG=$2; shift ;;
    --dir) DEST=$2; shift ;;
    --obs) OBS=1 ;;
    --no-desktop) DESKTOP=0 ;;
    *) echo "unknown option $1"; exit 2 ;;
  esac
  shift
done
export PATH="$HOME/.local/bin:$PATH"

# 1. gh
if ! command -v gh >/dev/null; then
  echo "== installing gh into ~/.local/bin (or: sudo pacman -S github-cli)"
  V=$(curl -fsSL https://api.github.com/repos/cli/cli/releases/latest | sed -n 's/.*"tag_name": *"v\([^"]*\)".*/\1/p' | head -1)
  T=$(mktemp -d)
  curl -fsSL "https://github.com/cli/cli/releases/download/v$V/gh_${V}_linux_amd64.tar.gz" | tar -xz -C "$T"
  mkdir -p "$HOME/.local/bin"
  install -m 755 "$T/gh_${V}_linux_amd64/bin/gh" "$HOME/.local/bin/gh"
  rm -rf "$T"
fi
gh auth status >/dev/null 2>&1 || gh auth login -h github.com -p https -w

# 2. release
if [ -z "$TAG" ]; then
  TAG=$(gh release list -R "$REPO" --limit 50 --json tagName,createdAt \
        --jq '[.[] | select(.tagName | startswith("play-"))] | sort_by(.createdAt) | last | .tagName')
fi
[ -n "$TAG" ] && [ "$TAG" != null ] || { echo "no play-* release found on $REPO"; exit 1; }
echo "== release $TAG"
mkdir -p "$DEST/$TAG"
cd "$DEST/$TAG"
ASSET=$(gh release view "$TAG" -R "$REPO" --json assets --jq '.assets[].name | select(endswith("-CachyOS.tar.gz"))' | head -1)
[ -n "$ASSET" ] || { echo "release $TAG has no *-CachyOS.tar.gz asset (pick a newer release with --tag)"; exit 1; }
[ -f "$ASSET" ] || gh release download "$TAG" -R "$REPO" -p "$ASSET"
WANT=$(gh release view "$TAG" -R "$REPO" --json body --jq .body | grep -F "$ASSET" | grep -o '[0-9a-f]\{64\}' | head -1 || true)
HAVE=$(sha256sum "$ASSET" | cut -d' ' -f1)
if [ -n "$WANT" ]; then
  [ "$WANT" = "$HAVE" ] || { echo "sha256 mismatch: got $HAVE, release notes say $WANT"; rm -f "$ASSET"; exit 1; }
  echo "sha256 ok"
else
  echo "warning: no sha256 for $ASSET in the release notes (got $HAVE)"
fi
tar -xzf "$ASSET"
PKG="$DEST/$TAG/${ASSET%.tar.gz}"
chmod +x "$PKG/play.sh" "$PKG/record.sh"
rm -f "$ASSET"   # the extracted disc is what we keep; the archive can be downloaded again

# 3. Flycast + recorder: native packages win; else Flathub for the user
NEED=""
command -v flycast >/dev/null || NEED="$NEED org.flycast.Flycast"
command -v gpu-screen-recorder >/dev/null || NEED="$NEED com.dec05eba.gpu_screen_recorder"
if [ "$OBS" = 1 ] && ! command -v obs >/dev/null; then NEED="$NEED com.obsproject.Studio"; fi
if [ -n "$NEED" ]; then
  if command -v flatpak >/dev/null; then
    flatpak remote-add --user --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
    # shellcheck disable=SC2086
    flatpak install --user -y --noninteractive flathub $NEED
  else
    echo "Not installed:$NEED"
    echo "Install natively (paru -S flycast gpu-screen-recorder) or install Flatpak (sudo pacman -S flatpak)"
    echo "and run this script again."
  fi
fi

# 4. menu entry
if [ "$DESKTOP" = 1 ]; then
  APPS="$HOME/.local/share/applications"
  mkdir -p "$APPS"
  cat > "$APPS/re4dc-$TAG.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=RE4 Dreamcast ($TAG)
Comment=RE4 Dreamcast play build in Flycast
Exec="$PKG/play.sh"
Path=$PKG
Terminal=false
Categories=Game;Emulator;
EOF
  echo "menu entry: $APPS/re4dc-$TAG.desktop"
fi

echo
echo "Play:   $PKG/play.sh"
echo "Record: $PKG/record.sh   (Ctrl+C stops and saves to ~/Videos/RE4DC)"
echo "Steam:  Games > Add a Non-Steam Game > Browse > $PKG/play.sh (optional)"
