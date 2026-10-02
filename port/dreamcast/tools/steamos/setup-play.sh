#!/bin/bash
# RE4 Dreamcast play machine setup for SteamOS Desktop Mode (Steam Deck), user-level only
# (no sudo, no changes to the read-only system image). Idempotent: safe to run again.
#   1. gh CLI in ~/.local/bin if missing (official cli/cli release tarball), then `gh auth login` if needed
#   2. downloads a play release's *-SteamOS.tar.gz and verifies its sha256
#   3. installs Flycast and GPU Screen Recorder from Flathub (--user); OBS with --obs
#   4. adds the build's play.sh to Steam as a non-Steam game (steamos-add-to-steam) unless --no-steam
# Usage: setup-play.sh [--tag play-...] [--dir ~/Games/RE4DC] [--obs] [--no-steam]
set -euo pipefail
REPO=lamb2k/re4dc
TAG=""
DEST="$HOME/Games/RE4DC"
OBS=0
STEAM=1
while [ $# -gt 0 ]; do
  case "$1" in
    --tag) TAG=$2; shift ;;
    --dir) DEST=$2; shift ;;
    --obs) OBS=1 ;;
    --no-steam) STEAM=0 ;;
    *) echo "unknown option $1"; exit 2 ;;
  esac
  shift
done
export PATH="$HOME/.local/bin:$PATH"

# 1. gh
if ! command -v gh >/dev/null; then
  echo "== installing gh into ~/.local/bin"
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
ASSET=$(gh release view "$TAG" -R "$REPO" --json assets --jq '.assets[].name | select(endswith("-SteamOS.tar.gz"))' | head -1)
[ -n "$ASSET" ] || { echo "release $TAG has no *-SteamOS.tar.gz asset"; exit 1; }
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
chmod +x "$PKG/play.sh"
rm -f "$ASSET"   # the extracted disc is what we keep; the archive can be downloaded again

# 3. Flathub apps (user installs; no sudo)
flatpak remote-add --user --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
APPS="org.flycast.Flycast com.dec05eba.gpu_screen_recorder"
[ "$OBS" = 1 ] && APPS="$APPS com.obsproject.Studio"
# shellcheck disable=SC2086
flatpak install --user -y --noninteractive flathub $APPS

# record helper next to the build
HERE="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
if [ -f "$HERE/record.sh" ]; then install -m 755 "$HERE/record.sh" "$DEST/record.sh"; fi

# 4. Steam shortcut
if [ "$STEAM" = 1 ]; then
  if command -v steamos-add-to-steam >/dev/null; then
    steamos-add-to-steam "$PKG/play.sh" && echo "added to Steam: $PKG/play.sh"
  else
    echo "steamos-add-to-steam not found: add $PKG/play.sh by hand (Steam > Games > Add a Non-Steam Game)"
  fi
fi

echo
echo "Play:   $PKG/play.sh"
[ -f "$DEST/record.sh" ] && echo "Record: $DEST/record.sh   (Ctrl+C stops and saves to ~/Videos/RE4DC)"
