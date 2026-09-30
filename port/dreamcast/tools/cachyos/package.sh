#!/bin/bash
# Builds <name>-CachyOS.tar.gz from a staged play disc directory (disc.bin, disc.cue, elf.sha256).
# Layout: <name>-CachyOS/{play.sh,record.sh,README.txt,disc/{disc.bin,disc.cue,elf.sha256}}; the scripts keep
# their exec bit. Prints the archive's size and sha256 (put the sha256 in the release notes next to the asset).
# Usage: package.sh <disc-dir> <name, e.g. RE4DC-r21k> <out-dir> [build description]
set -euo pipefail
DISC=$1 NAME=$2 OUT=$3 BUILD=${4:-}
HERE="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
for f in disc.bin disc.cue elf.sha256; do [ -f "$DISC/$f" ] || { echo "missing $DISC/$f"; exit 1; }; done
T=$(mktemp -d)
trap 'rm -rf "$T"' EXIT
P="$T/$NAME-CachyOS"
mkdir -p "$P/disc"
install -m 755 "$HERE/play.sh" "$HERE/record.sh" "$P/"
for f in disc.bin disc.cue elf.sha256; do ln -s "$(readlink -f "$DISC/$f")" "$P/disc/$f"; done
cat > "$P/README.txt" <<EOF
RE4 Dreamcast ${NAME#RE4DC-} - CachyOS / Arch Linux

Play: extract this archive (e.g. into ~/Games), keep play.sh next to the disc folder, run ./play.sh.
It uses a native Flycast if one is installed (paru -S flycast), else Flathub's org.flycast.Flycast
(installed for your user when Flatpak is present: sudo pacman -S flatpak). The game starts in a
window from the title (F11 toggles fullscreen). Your own Flycast settings are not changed: the play
settings are passed on the command line. RE4DC_FLYCAST=/path/to/flycast ./play.sh picks a binary.

Controls (a gamepad on port A, Flycast defaults): A action / fire, B run / cancel, Y inventory,
R2 aim, L2 knife, left stick move, START pause / options. Frame pacing: hold R2 and press START to
cycle Smooth -> Fast -> Off (Fast is the default). Remap in Flycast Settings > Controls.

Record: ./record.sh [out.mp4] (GPU Screen Recorder, 60 fps; Ctrl+C stops, saves to ~/Videos/RE4DC).
Steam (optional): Games > Add a Non-Steam Game > Browse > play.sh.

${BUILD:+Build: $BUILD. }ELF sha256 in disc/elf.sha256. No BIOS included: Flycast boots the disc with its
built-in HLE BIOS.
EOF
mkdir -p "$OUT"
A="$OUT/$NAME-CachyOS.tar.gz"
tar -C "$T" -chzf "$A" "$NAME-CachyOS"
echo "$(basename "$A") $(stat -c %s "$A") $(sha256sum "$A" | cut -d' ' -f1)"
