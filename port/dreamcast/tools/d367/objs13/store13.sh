#!/bin/bash
# store13.sh <room...>: copy the test 13 object dars (work/out/<r>x: geometry minus breakables + items pack + PS2 pictures)
# and their loose pictures to re4-assets-private/objs-20261014/t13/<r>/ and refresh t13/sha256.txt.
S="/mnt/c/Game Dev/Emulators/re4-assets-private/objs-20261014/t13"
O=/root/probe/lanes-20261014/objs/work/out
mkdir -p "$S"
for r in "$@"; do
  mkdir -p "$S/$r/tex"
  cp $O/${r}x/$r.dar "$S/$r/"; cp $O/${r}x/tex/*.re4tex "$S/$r/tex/" 2>/dev/null
  cp $O/${r}x/tex.json "$S/$r/tex.json"; cp $O/${r}g/report.json "$S/$r/objects.json"; cp $O/${r}t/pack.json "$S/$r/items.json"
done
( cd "$S" && find . -type f ! -name sha256.txt | sort | xargs -d '\n' sha256sum > sha256.txt; wc -l sha256.txt )
# tex-all: one copy per key for the combined objs13 set (a picture shared by rooms is the same texels; its header names
# the room it was made for: offsets 36..39 source crc, 48.. source name), first room in sorted order wins.
( cd "$S" && rm -rf tex-all && mkdir tex-all && for r in r1*; do for f in $r/tex/*.re4tex; do [ -e tex-all/$(basename $f) ] || cp $f tex-all/; done; done
  find . -type f ! -name sha256.txt | sort | xargs -d '\n' sha256sum > sha256.txt; echo "tex-all $(ls tex-all | wc -l)" )
# per-room copies take the tex-all bytes, so objs13-<room> sets combine without a "staged twice" refusal
( cd "$S" && for r in r1*; do for f in $r/tex/*.re4tex; do cp tex-all/$(basename $f) $f; done; done
  find . -type f ! -name sha256.txt | sort | xargs -d '\n' sha256sum > sha256.txt; echo "per-room tex normalised" )
