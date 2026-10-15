#!/bin/bash
# t13-texpak.sh (WSL): the test 13 dc/tex.pak (t11-fix.py data set t13tex), deterministic, built on ext4.
#   base     tex-t12d.pak  (test 12, 43be4b59; the base both lanes below built from)
#   + 12.1   tex-t121.pak  (b097d061: tex-t12d + the 293 re-keyed PS2-formula world pictures of blackps2w, no key changed)
#   + objs13 tex-t13o.pak  (lane objs v5, 06e18e13: tex-t12d + the 32 objs13 PS2 object pictures)
#   + Ashley 4 pictures    (ps2lib/cast/r117/ashley-pl11/dc/tex: atlas + head / hair / extra 9 mask pairs; PS2_ASHLEY=2),
#                          packed (texpack.py), not loose (test 11's loose-texture lesson)
# Every key keeps the bytes of the gated pak it came from (no wrapsafe pass here: tex-t121 and tex-t13o were each gated as
# built). tex_merge.py refuses a key two inputs change differently. resident.bin is test 12's (r101 only), unchanged.
# Output: $OUT (default /root/probe/lanes-20261015/t13rc/data)/tex-t13.pak.
set -euo pipefail
D=$(cd "$(dirname "$0")/.." && pwd)
OUT=${OUT:-/root/probe/lanes-20261015/t13rc/data}
BASE=/root/probe/lanes-20261014/t12rc/data/tex-t12d.pak
T121=/root/probe/t12dark/data/tex-t121.pak
T13O=${T13O:-/root/probe/lanes-20261014/objs/work/tex-t13o.pak}
ASH="/mnt/c/Game Dev/Emulators/re4-assets-private/ps2lib/cast/r117/ashley-pl11/dc/tex"
mkdir -p $OUT
sha256sum $BASE $T121 $T13O | cut -c1-16 | paste -sd' '
python3 $D/texpack.py "$ASH" $OUT/tex-ashley.pak
python3 $D/tex_merge.py $BASE $OUT/tex-t13.pak $T121 $T13O $OUT/tex-ashley.pak
python3 $D/texpack.py --verify $OUT/tex-t13.pak
rm -f $OUT/tex-ashley.pak
sha256sum $OUT/tex-t13.pak
