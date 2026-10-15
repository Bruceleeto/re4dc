#!/bin/bash
# fsaa-package.sh: console FSAA test disc = test 10 recipe (t10s-build.sh tP) + RENDER_FSAA=1, test 10 package data
set -e
R=/root/probe/lanes-20261014/fsaa
L=fsaFtP
O=/root/probe/lanes/route/out-$L
P="/mnt/c/Game Dev/Emulators/RE4DC-FSAA-Test-20261014"
mkdir -p "$P" $R/logs
PKG_K=$R python3 /root/probe/lanes-20261011/test8/t8-pkgtree.py $L $R/fix/pkg-$L.json | tee $R/logs/pkgtree-$L.txt | tail -1 | grep -q PKGTREE_OK || { echo "pkgtree check failed"; tail -20 $R/logs/pkgtree-$L.txt; exit 1; }
rm -rf $R/gdemu
(cd $R/tree/port/dreamcast/tools/d367 && bash mkgdi.sh $O/re4dc-game.elf $R/pkgtree $R/gdemu | tail -1)
mkdir -p "$P/gdemu"
for f in disc.gdi track01.bin track02.raw track03.bin; do mv $R/gdemu/$f "$P/gdemu/"; done
(cd "$P/gdemu" && sha256sum disc.gdi track01.bin track02.raw track03.bin) | tee "$P/SHA256SUMS.txt"
cp $O/syms.txt $R/syms-$L.txt
echo "PACKAGE $P"
