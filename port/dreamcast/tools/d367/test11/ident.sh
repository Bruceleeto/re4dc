#!/bin/bash
# ident.sh <out-label-A> <out-label-B>: play-image identity (objcopy ELF image + every overlay + syms)
A=/root/probe/lanes/route/out-$1; B=/root/probe/lanes/route/out-$2
TOOL=/opt/toolchains/dc/sh-elf/bin
ok=1
for x in $A $B; do $TOOL/sh-elf-objcopy -R .stack -O binary $x/re4dc-game.elf /tmp/img-$(basename $x).bin; done
ia=/tmp/img-out-$1.bin; ib=/tmp/img-out-$2.bin
if cmp -s $ia $ib; then echo "IMAGE identical $(sha256sum < $ia | cut -c1-16) $(stat -c%s $ia)"; else echo "IMAGE DIFFERENT $(stat -c%s $ia) $(stat -c%s $ib)"; ok=0; fi
for f in $(cd $A; ls *.ovl syms.txt end.txt) ; do
  if cmp -s $A/$f $B/$f; then echo "$f identical"; else echo "$f DIFFERENT"; ok=0; fi
done
la=$(cd $A; ls *.ovl | tr '\n' ' '); lb=$(cd $B; ls *.ovl | tr '\n' ' '); [ "$la" = "$lb" ] || { echo "overlay set differs: $la | $lb"; ok=0; }
rm -f $ia $ib
[ $ok = 1 ] && echo "IDENTITY PASS $1 vs $2" || echo "IDENTITY FAIL $1 vs $2"
