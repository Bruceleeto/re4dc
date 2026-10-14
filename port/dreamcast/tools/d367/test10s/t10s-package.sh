#!/bin/bash
# t10s-package.sh: test 10 (small) release CANDIDATE package from t10stP + fix/pkg-t10stP.json (copy of rel91/r91-package.sh).
# Output: /mnt/c/Game Dev/Emulators/RE4DC-Test10-Release (not published; the coordinator runs the full-play gate first)
set -e
R=/root/probe/lanes-20261014/t10s
L=t10stP
O=/root/probe/lanes/route/out-$L
SHA=${SRC_SHA:-a93e8be0}   # the image source (this recipe commit adds tools only)
DATE=20261014
P="/mnt/c/Game Dev/Emulators/RE4DC-Test10-Release"
Z=RE4DC-Console-Test-$SHA-$DATE-GDEMU.zip
A=RE4DC-Test10-$SHA-Build-Assets.zip
mkdir -p "$P" $R/logs
PKG_K=$R python3 /root/probe/lanes-20261011/test8/t8-pkgtree.py $L $R/fix/pkg-$L.json | tee $R/logs/pkgtree-$L.txt | tail -1 | grep -q PKGTREE_OK || { echo "pkgtree check failed"; tail -20 $R/logs/pkgtree-$L.txt; exit 1; }
rm -rf $R/gdemu
(cd $R/tree/port/dreamcast/tools/d367 && bash mkgdi.sh $O/re4dc-game.elf $R/pkgtree $R/gdemu | tail -1)
(cd $R/gdemu && sha256sum disc.gdi track01.bin track02.raw track03.bin) > $R/gdemu-sha256.txt
mkdir -p "$P/gdemu"
for f in disc.gdi track01.bin track02.raw track03.bin; do cp $R/gdemu/$f "$P/gdemu/"; done
tr -d '\r' < $R/README.txt | sed "s/SHA_PLACEHOLDER/$SHA/g" | sed 's/$/\r/' > "$P/README.txt"
(cd "$P/gdemu" && sha256sum disc.gdi track01.bin track02.raw track03.bin | sed 's#  #  gdemu/#') > $R/SHA256SUMS-inner.txt
cmp <(cut -c1-64 $R/SHA256SUMS-inner.txt) <(cut -c1-64 $R/gdemu-sha256.txt) && echo tracks-match-build
cd "$P"
rm -f $Z $A
python3 - "$P" "$Z" "$R/SHA256SUMS-inner.txt" <<'E'
import sys, zipfile, os
p, z, sums = sys.argv[1:4]
with zipfile.ZipFile(os.path.join(p, z), 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
    for f in ('disc.gdi', 'track01.bin', 'track02.raw', 'track03.bin'):
        zf.write(os.path.join(p, 'gdemu', f), 'gdemu/' + f)
    zf.write(os.path.join(p, 'README.txt'), 'README.txt')
    zf.write(sums, 'SHA256SUMS.txt')
print('zip ok')
E
python3 /root/probe/lanes-20261011/test8/t8-assets.py "$P/$A"
sha256sum $Z $A > SHA256SUMS.txt
cat SHA256SUMS.txt
python3 -c "import zipfile,sys;print('testzip', zipfile.ZipFile(sys.argv[1]).testzip(), zipfile.ZipFile(sys.argv[2]).testzip())" "$P/$Z" "$P/$A"
cp $O/syms.txt $R/syms-$L.txt
grep -n -- '–\|—' README.txt || echo "no long dashes"
rm -rf $R/gdemu/track0*.bin $R/gdemu/track02.raw
echo "PACKAGE $P"
