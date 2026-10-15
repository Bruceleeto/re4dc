#!/bin/bash
# mkfix16.sh <room...>: test 13 objects gates on the published test 12 package (pkg-t12c2tP.json, t12rc ac1c912e).
# Per room: control g16-<r>-c-t12c2tT (test 12 data + warp), test g16-<r>-t-t12c2tT and g16-<r>-t-t12c2mW
# (+ st1/<r>.dar = work/out/<r>x (gen13 geometry minus breakables + items pack + ps2_objects_tex pictures) + loose tex).
set -e
R=/root/probe/lanes-20261014/objs; W=$R/work/warps; F=$R/fix; O=$R/work/out
FX="python3 /root/probe/lanes-20261014/t12rc/tree/port/dreamcast/tools/d367/test11/t11-fix.py"
B="--base /root/probe/lanes-20261014/t12rc/fix/pkg-t12c2tP.json --base-label t12c2tP"
for r in "$@"; do
  n=${r#r}; w=$W/w$n.txt; [ $n = 11b ] && w=$W/x11b.txt
  [ -s $w ] || { echo "no warp $w"; continue; }
  $FX t12c2tT $F/g16-$n-c-t12c2tT.json $B --warp $w > /dev/null
  $FX t12c2mW $F/g16-$n-c-t12c2mW.json $B --warp $w > /dev/null
  $FX t12c2tT $F/g16-$n-t-t12c2tT.json $B --set st1/$r.dar=$O/${r}x/$r.dar --texdir $O/${r}x/tex --warp $w > /dev/null
  $FX t12c2mW $F/g16-$n-t-t12c2mW.json $B --set st1/$r.dar=$O/${r}x/$r.dar --texdir $O/${r}x/tex --warp $w > /dev/null
  echo "$r fixtures ok ($(ls $O/${r}x/tex | wc -l) tex)"
done
