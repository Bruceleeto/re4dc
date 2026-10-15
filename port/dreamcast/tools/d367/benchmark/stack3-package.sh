#!/bin/bash
# stack3-package.sh [label] (WSL): STACK v3 village console disc (lane crowd12, 2026-10-15; after fx12
# village-package.sh). The warp arm boots straight into the r101 square at the benchmark-r101 spot (village-stack3-
# warp.txt: by the cross, god, alert 30) with the test 11 data set plus the STACK v3 data: dc/tex.pak = tex_merge.py
# of tex-t11.pak + fx12 ps2lib + vram12 world VQ (tex_wrapsafe.py marked), st1/r101.dar = objs lane r101 objects.
# Assembled on ext4 (WSL), one copy to C:. Env: TEXPAK (default the v3 pak), OUT (Windows folder).
set -e
L=${1:-c12V3vtW}
K=/root/probe/lanes-20261014/crowd12
V=$K/stack3
D=$K/tree/port/dreamcast/tools/d367
O=/root/probe/lanes/route/out-$L
P=${OUT:-"/mnt/c/Game Dev/Emulators/RE4DC-Village-Stack3-20261015"}
TEXPAK=${TEXPAK:-$K/data/tex-v3-ws.pak}
DAR="/mnt/c/Game Dev/Emulators/re4-assets-private/objs-20261014/r101o/r101.dar"
mkdir -p $V
DATA=$(python3 -c "import re;print(re.search(r\"^T11_DATA = '([^']*)'\", open('$D/test11/t11-fix.py').read(), re.M).group(1))")
python3 $D/test11/t11-fix.py $L $V/stack3-$L.json --data $DATA --warp $D/benchmark/village-stack3-warp.txt | tail -1
python3 - "$V/stack3-$L.json" "$TEXPAK" "$DAR" <<'PY'
import json, sys
f, pak, dar = sys.argv[1:]
d = json.load(open(f)); d['replace']['dc/tex.pak'] = pak; d['replace']['st1/r101.dar'] = dar
json.dump(d, open(f, 'w'), indent=1); print('fixture: dc/tex.pak <-', pak, '; st1/r101.dar <-', dar)
PY
PKG_K=$V python3 /root/probe/lanes-20261011/test8/t8-pkgtree.py $L $V/stack3-$L.json > $V/pkgtree.txt
bad=$(sed -n '/PKGTREE_BAD/,$p' $V/pkgtree.txt | grep -v 'PKGTREE_BAD' | grep -v '^present dc/warp.txt$' || true)
[ -z "$bad" ] || { echo "pkgtree: $bad"; exit 1; }
cmp $V/pkgtree/dc/warp.txt $D/benchmark/village-stack3-warp.txt
cmp $V/pkgtree/dc/tex.pak "$TEXPAK" && cmp $V/pkgtree/st1/r101.dar "$DAR" && echo "pkgtree carries the v3 tex.pak and the objs r101.dar"
rm -rf $V/gdemu
(cd $D && bash mkgdi.sh $O/re4dc-game.elf $V/pkgtree $V/gdemu | tail -1)
(cd $V/gdemu && sha256sum disc.gdi track01.bin track02.raw track03.bin) > $V/gdemu-sha256.txt
rm -rf "$P/gdemu"; mkdir -p "$P/gdemu"
for f in disc.gdi track01.bin track02.raw track03.bin; do cp $V/gdemu/$f "$P/gdemu/"; done
(cd "$P/gdemu" && sha256sum disc.gdi track01.bin track02.raw track03.bin) > "$P/gdemu/SHA256SUMS"
cmp <(cut -c1-64 "$P/gdemu/SHA256SUMS") <(cut -c1-64 $V/gdemu-sha256.txt) && echo "tracks match the ext4 build"
cat "$P/gdemu/SHA256SUMS"
