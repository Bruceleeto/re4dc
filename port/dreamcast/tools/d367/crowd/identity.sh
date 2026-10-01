#!/bin/bash
# Lane crowd: knob-off identity. Builds the play recipe (cbuild.sh MODE=play and MODE=trace) from this tree with every
# CROWD_* knob at its default and from <base> (a detached worktree of this repo under /root/probe/lanes/crowd/wt-base),
# then compares the objcopy'd program images byte for byte.
#   identity.sh <base-commit>
set -euo pipefail
B=${1:?base commit}
EV=/root/probe/lanes/crowd
T=$(cd "$(dirname "$0")" && pwd)
TREE=$(cd "$T/../../../../.." && pwd)
OC=/opt/toolchains/dc/sh-elf/bin/sh-elf-objcopy
W=$EV/wt-base
if [ -d "$W" ]; then git -C "$W" checkout -q --detach "$B"; else git -C "$TREE" worktree add -q --detach "$W" "$B"; fi
echo "tree $(git -C "$TREE" rev-parse --short HEAD) dirty=$(git -C "$TREE" status --porcelain -- port/dreamcast/game | wc -l)  base $(git -C "$W" rev-parse --short HEAD)"
# __DATE__/__TIME__ (the VMU debug-slot stamp) differ between any two builds: pin them (GCC SOURCE_DATE_EPOCH).
export SOURCE_DATE_EPOCH=1759300000
r=0
for mode in play trace; do
  MODE=$mode bash "$T/cbuild.sh" ida-$mode | tail -1
  ROOT=$W MODE=$mode bash "$T/cbuild.sh" idb-$mode | tail -1
  $OC -O binary $EV/build-ida-$mode/re4dc-game.elf $EV/img-ida-$mode.bin
  $OC -O binary $EV/build-idb-$mode/re4dc-game.elf $EV/img-idb-$mode.bin
  sha256sum $EV/img-ida-$mode.bin $EV/img-idb-$mode.bin
  if cmp -s $EV/img-ida-$mode.bin $EV/img-idb-$mode.bin && cmp -s $EV/build-ida-$mode/sscrn.ovl $EV/build-idb-$mode/sscrn.ovl; then
    echo "IDENTITY $mode OK"; else echo "IDENTITY $mode DIFFERS"; r=1; fi
  rm -rf $EV/obj-ida-$mode $EV/obj-idb-$mode $EV/img-ida-$mode.bin $EV/img-idb-$mode.bin
done
exit $r
