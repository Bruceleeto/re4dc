#!/bin/bash
# fp_master.sh <release-tree> <release-manifest.json> <IP.BIN> <outdir> [twin-out-dir]   (WSL; tools/d367/fullplay)
# Masters a BASE disc for the full-play gate from the release's own extracted game tree (fp_iso.py extract):
#   - no twin-out-dir: the release tree as is (same 1ST_READ.BIN, same overlays) = the "release binary" base;
#   - twin-out-dir (route build out-fp<label>W): 1ST_READ.BIN and the dc/*.ovl overlays from the twin build.
# Both get two fixture files, dc/warp.txt and dc/padscript.txt, whose directory records (ISO9660 + Joliet) point
# into track 1 (LBA 400 / 420, 8192 bytes each, NUL-padded): fp_run.py writes each segment's fixtures into its own
# 1.2 MB track01.iso, so every segment shares one hard-linked track03.iso (no per-segment 840 MB disc).
# The base's file manifest is diffed against the release manifest: only 1ST_READ.BIN, dc/*.ovl (twin) and the two
# fixture files may differ (fixture-identity proof, base-diff.txt). Same genisoimage arguments as mkgdi.sh; the
# release's own IP.BIN. Output: outdir/{track01-template.iso,track02.raw,track03.iso,base.json,base-diff.txt}.
set -euo pipefail
TREE=${1:?tree}; MAN=${2:?manifest}; IP=${3:?IP.BIN}; OUT=${4:?outdir}; TW=${5:-}
here=$(cd "$(dirname "$0")" && pwd)
TOOL=/opt/toolchains/dc/sh-elf/bin
HD=45000; LBA_W=400; LBA_P=420; FIXB=8192; T1=606; T2=302
WORK=$(mktemp -d /root/probe/lanes-20261014/fullplay/work/master.XXXXXX)
trap 'rm -rf "$WORK"' EXIT
rm -rf "$OUT"; mkdir -p "$OUT"
cp -al "$TREE" $WORK/cdroot
for f in dc/warp.txt dc/padscript.txt; do
  [ ! -e $WORK/cdroot/$f ] || { echo "fp_master: the release carries $f (a fixture file on a user disc)" >&2; exit 1; }
  head -c $FIXB /dev/zero > $WORK/cdroot/$f
done
ALLOW=(--allow 'dc/warp\.txt' --allow 'dc/padscript\.txt')
KIND=release
if [ -n "$TW" ]; then
  KIND=twin
  rm -f $WORK/cdroot/1ST_READ.BIN
  $TOOL/sh-elf-objcopy -R .stack -O binary $TW/re4dc-game.elf $WORK/cdroot/1ST_READ.BIN
  for o in $TREE/dc/*.ovl; do
    n=$(basename $o)
    [ -s $TW/$n ] || { echo "fp_master: twin build lacks overlay $n" >&2; exit 1; }
    rm -f $WORK/cdroot/dc/$n; cp $TW/$n $WORK/cdroot/dc/$n
  done
  ALLOW+=(--allow '1ST_READ\.BIN' --allow 'dc/[^/]*\.ovl')
fi
genisoimage -quiet -C 0,$HD -G "$IP" -r -J -l -input-charset iso8859-1 -V RE4DCROOM -o "$OUT/track03.iso" $WORK/cdroot
python3 $here/fp_iso.py manifest "$OUT/track03.iso" -o "$OUT/base-manifest.json" > /dev/null
python3 $here/fp_iso.py diff "$MAN" "$OUT/base-manifest.json" "${ALLOW[@]}" > "$OUT/base-diff.txt" \
  || { echo "fp_master: the base differs from the release beyond the allowed files:" >&2; grep DIFF "$OUT/base-diff.txt" >&2; exit 1; }
python3 $here/fp_iso.py redirect "$OUT/track03.iso" /dc/warp.txt $LBA_W $FIXB >> "$OUT/base-diff.txt"
python3 $here/fp_iso.py redirect "$OUT/track03.iso" /dc/padscript.txt $LBA_P $FIXB >> "$OUT/base-diff.txt"
mkdir -p $WORK/t1root
printf 'RE4DC GD-ROM image. The game is in the high-density area (track 3).\r\n' > $WORK/t1root/README.TXT
genisoimage -quiet -G "$IP" -V RE4DCLD -input-charset iso8859-1 -o $WORK/track01.iso $WORK/t1root
t1=$(( $(stat -c %s $WORK/track01.iso) / 2048 ))
[ $t1 -lt $LBA_W ] || { echo "fp_master: track01 ISO reaches LBA $t1" >&2; exit 1; }
truncate -s $((T1 * 2048)) $WORK/track01.iso
cp $WORK/track01.iso "$OUT/track01-template.iso"
head -c $((T2 * 2352)) /dev/zero > "$OUT/track02.raw"
ELF=$( [ -n "$TW" ] && echo $TW/re4dc-game.elf || echo -)
python3 - "$OUT/base.json" "$KIND" "$TREE" "$ELF" $LBA_W $LBA_P $FIXB <<'E'
import json, sys, hashlib
o, kind, tree, elf, lw, lp, fb = sys.argv[1:8]
json.dump(dict(kind=kind, tree=tree, elf=elf, warp_lba=int(lw), pad_lba=int(lp), fixture_bytes=int(fb),
               gdi='3\n1 0 4 2048 track01.iso 0\n2 756 0 2352 track02.raw 0\n3 45000 4 2048 track03.iso 0\n'),
          open(o, 'w'), indent=1)
E
sha256sum "$OUT/track03.iso" | cut -c1-64 > "$OUT/track03.sha256"
echo "MASTER $KIND $OUT $(tail -1 "$OUT/base-diff.txt" | head -c 0)$(grep -c . "$OUT/base-diff.txt") diff lines; $(grep '^identical' "$OUT/base-diff.txt")"
