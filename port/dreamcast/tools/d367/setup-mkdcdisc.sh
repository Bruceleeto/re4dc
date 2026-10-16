#!/bin/bash
# setup-mkdcdisc.sh [dir]   (WSL / Linux, maintainers): build the pinned mkdcdisc that mkgdi.sh masters release discs with.
#
# mkdcdisc (gitlab.com/simulant/mkdcdisc, GPL-2.0) writes the standard GD-ROM layout (CONTRIBUTING-PORT.md section 8).
# The release image depends on its exact version (file placement, IP.BIN bootstrap and TOC1, low-density area), so it
# is pinned: v0.0.4, commit 2b98b0d9, built against Ubuntu 24.04's libisofs 1.5.6. Contributors do not need it: they
# put their program on the published release disc with tools/swap-program.py.
# Host packages: sudo apt install git meson ninja-build build-essential pkg-config libisofs-dev libpng-dev
# Output: <dir>/builddir/mkdcdisc (default dir /root/work/tools/mkdcdisc, the path mkgdi.sh looks at; MKDCDISC=<binary>
# points mkgdi.sh at another one). A no-op when <dir> already holds the pinned commit and its binary.
set -euo pipefail
DIR=${1:-/root/work/tools/mkdcdisc}
URL=https://gitlab.com/simulant/mkdcdisc.git
PIN=2b98b0d9480e364e3517355648fbc3b49fb19882
for c in git meson ninja c++ pkg-config; do
  command -v $c >/dev/null || { echo "setup-mkdcdisc: missing $c (sudo apt install git meson ninja-build build-essential pkg-config libisofs-dev libpng-dev)" >&2; exit 1; }
done
pkg-config --exists libisofs-1 || { echo "setup-mkdcdisc: missing libisofs (sudo apt install libisofs-dev)" >&2; exit 1; }
if [ ! -d "$DIR/.git" ]; then
  git clone -q "$URL" "$DIR"
fi
if [ "$(git -C "$DIR" rev-parse HEAD)" != $PIN ] || [ -n "$(git -C "$DIR" status --porcelain)" ]; then
  git -C "$DIR" fetch -q origin
  git -C "$DIR" checkout -q --detach $PIN
  [ -z "$(git -C "$DIR" status --porcelain)" ] || { echo "setup-mkdcdisc: $DIR has local changes; use a clean checkout" >&2; exit 1; }
  rm -rf "$DIR/builddir"
fi
[ -d "$DIR/builddir" ] || meson setup "$DIR/builddir" "$DIR" --buildtype=release >/dev/null
ninja -C "$DIR/builddir" mkdcdisc >/dev/null
"$DIR/builddir/mkdcdisc" --help 2>&1 | head -1
echo "setup-mkdcdisc: $DIR/builddir/mkdcdisc ($(git -C "$DIR" rev-parse --short=8 HEAD), libisofs $(pkg-config --modversion libisofs-1))"
