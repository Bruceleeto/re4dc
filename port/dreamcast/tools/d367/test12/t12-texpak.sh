#!/bin/bash
# t12-texpak.sh (WSL): the test 12 dc/tex.pak (t11-fix.py data set t12tex), deterministic, built on ext4.
#   base   tex-t11.pak            test 11 (GC bake textures + Leon's 2x packages), sha256 1582e5c5
#   + fx12 tex-t11-ps2lib.pak     PS2 effect library pictures under the GameCube keys (FX_PS2_PACK / PAL4), 653e622b
#   + vram tex-vr12-both.pak      blackgc14vl: r101's 12 large PS2 world textures + Leon's atlas ec255e66-76812316 as VQ
#                                 (Leon VQ: user decision 2026-10-14 23:58)
#   + merchant 4 texture keys     ps2lib/cast/r102/merchant-em18/dc/tex (PS2_CAST_MERCHANT), packed instead of loose
#   + items tex-items.pak         lane items (24526dfb, ps2_items-v2): tex-t11.pak + the PS2 pickup / debris packages
#                                 (re4-assets-private/items-20261014, sha256 in SHA256SUMS)
#   + acc12 8 texture keys        lane acc12 (fdc16424): PS2 Ganado accessory pictures, ps2lib/cast/common/acc12/tex,
#                                 packed instead of loose
#   then tex_wrapsafe.py marks the uniform 16-bit packages (TEX_WRAP_SAFE=1).
# tex_merge.py refuses a key two inputs change differently. Output: $OUT (default /root/probe/lanes-20261014/t12rc/data).
set -euo pipefail
D=$(cd "$(dirname "$0")/.." && pwd)
OUT=${OUT:-/root/probe/lanes-20261014/t12rc/data}
BASE=/root/probe/lanes-20261014/t11/data/tex-t11.pak
FX=/root/probe/lanes-20261014/fx12/ps2pack/tex-t11-ps2lib.pak
VR=/root/probe/lanes-20261014/vram12/data/tex-vr12-both.pak
MER="/mnt/c/Game Dev/Emulators/re4-assets-private/ps2lib/cast/r102/merchant-em18/dc/tex"
ITM="/mnt/c/Game Dev/Emulators/re4-assets-private/items-20261014/tex-items.pak"
ACC="/mnt/c/Game Dev/Emulators/re4-assets-private/ps2lib/cast/common/acc12/tex"
mkdir -p $OUT
sha256sum $BASE $FX $VR "$ITM" | cut -c1-16 | paste -sd' '
python3 $D/texpack.py "$MER" $OUT/tex-merchant.pak
python3 $D/texpack.py "$ACC" $OUT/tex-acc12.pak
python3 $D/tex_merge.py $BASE $OUT/tex-t12c-merge.pak $FX $VR $OUT/tex-merchant.pak "$ITM" $OUT/tex-acc12.pak
python3 $D/tex_wrapsafe.py $OUT/tex-t12c-merge.pak $OUT/tex-t12c.pak > $OUT/ws-t12c.txt
tail -1 $OUT/ws-t12c.txt
python3 $D/texpack.py --verify $OUT/tex-t12c.pak
rm -f $OUT/tex-t12c-merge.pak $OUT/tex-merchant.pak $OUT/tex-acc12.pak
sha256sum $OUT/tex-t12c.pak
