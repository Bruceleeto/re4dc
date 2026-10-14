#!/bin/bash
# village-package.sh [label] (WSL): the r101 village console A/B disc (test 12 fx lane, 10-14). The warp arm
# (DBG_WARP=1) boots straight into the r101 square (village-warp.txt: the bell-fight start, god mode) with the test 11
# data set; FX level (Y + START) and HW fog (X + D-pad up + START) switch at run time. Assembled on ext4, one copy to C:.
# Env: EXTRA ("--set DEST=SRC ..." for t11-fix.py, e.g. the objs lane's r101 dar).
set -e
L=${1:-vil1tW}
V=/root/probe/lanes-20261014/fx12/village
T=/root/probe/lanes-20261014/fx12/tree
D=$T/port/dreamcast/tools/d367
O=/root/probe/lanes/route/out-$L
P="/mnt/c/Game Dev/Emulators/RE4DC-Village-Test-20261014"
mkdir -p $V
DATA=$(python3 -c "import re;print(re.search(r\"^T11_DATA = '([^']*)'\", open('$D/test11/t11-fix.py').read(), re.M).group(1))")
python3 $D/test11/t11-fix.py $L $V/village-$L.json --data $DATA --warp $D/test12fx/village-warp.txt ${EXTRA:-} | tail -1
PKG_K=$V python3 /root/probe/lanes-20261011/test8/t8-pkgtree.py $L $V/village-$L.json > $V/pkgtree.txt
# the only accepted pkgtree complaint is the warp file this disc needs
bad=$(sed -n '/PKGTREE_BAD/,$p' $V/pkgtree.txt | grep -v 'PKGTREE_BAD' | grep -v '^present dc/warp.txt$' || true)
[ -z "$bad" ] || { echo "pkgtree: $bad"; exit 1; }
cmp $V/pkgtree/dc/warp.txt $D/test12fx/village-warp.txt
rm -rf $V/gdemu
(cd $D && bash mkgdi.sh $O/re4dc-game.elf $V/pkgtree $V/gdemu | tail -1)
(cd $V/gdemu && sha256sum disc.gdi track01.bin track02.raw track03.bin) > $V/gdemu-sha256.txt
rm -rf "$P/gdemu"; mkdir -p "$P/gdemu"
for f in disc.gdi track01.bin track02.raw track03.bin; do cp $V/gdemu/$f "$P/gdemu/"; done
(cd "$P/gdemu" && sha256sum disc.gdi track01.bin track02.raw track03.bin) > "$P/gdemu/SHA256SUMS"
cmp <(cut -c1-64 "$P/gdemu/SHA256SUMS") <(cut -c1-64 $V/gdemu-sha256.txt) && echo "tracks match the ext4 build"
tr -d '\r' < $D/test12fx/WHAT-TO-TRY-ON-THE-TV.txt | sed "s/BUILD_PLACEHOLDER/$(head -1 $O/stack.txt | cut -c1-8) $L $(cut -c1-16 $O/elf.sha256)/" | sed 's/$/\r/' > "$P/WHAT-TO-TRY-ON-THE-TV.txt"
cat "$P/gdemu/SHA256SUMS"
