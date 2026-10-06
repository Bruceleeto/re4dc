#!/bin/bash
# idc.sh <labelA> <labelB>: section hashes + whole objcopy image + overlay compare of two route-build outputs (lane el copy of fm's)
R=/root/probe/lanes/route
OC=/opt/toolchains/dc/sh-elf/bin/sh-elf-objcopy
S=$(mktemp -d)
for L in $1 $2; do
  E=$R/out-$L/re4dc-game.elf
  line="$L"
  for s in .text .data .rodata .bss .re4dc_char_data; do
    $OC -O binary -j $s $E $S/$L$s.bin 2>/dev/null
    line="$line $s=$(sha256sum $S/$L$s.bin | cut -c1-12)($(stat -c %s $S/$L$s.bin))"
  done
  $OC -R .stack -O binary $E $S/$L.img
  echo "$line img=$(sha256sum $S/$L.img | cut -c1-12) ovl=$(sha256sum $R/out-$L/sscrn.ovl | cut -c1-12) missing=[$(cat $R/out-$L/missing.txt)]"
done
echo "rodata differing bytes: $(cmp -l $S/$1.rodata.bin $S/$2.rodata.bin | wc -l); image differing bytes: $(cmp -l $S/$1.img $S/$2.img | wc -l)"
cmp -s $S/$1.img $S/$2.img && cmp -s $R/out-$1/sscrn.ovl $R/out-$2/sscrn.ovl && echo "IDENTITY: image + overlay byte-identical"
echo "resolved-knobs diff:"; diff $R/out-$1/resolved-knobs.txt $R/out-$2/resolved-knobs.txt | head -20
rm -rf $S
