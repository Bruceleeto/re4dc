#!/bin/bash
# mklook.sh <room...>: objs13 look-sheet fixtures (t12c2mW, 60 s): control g16L-<n>-c (test 12 data) and test g16L-<n>-t
# (+ objs13 dar + pictures), both with the object-facing warp work/warps/look<n>.txt (freeze 1200: settled still).
set -e
R=/root/probe/lanes-20261014/objs; F=$R/fix; O=$R/work/out
FX="python3 /root/probe/lanes-20261014/t12rc/tree/port/dreamcast/tools/d367/test11/t11-fix.py"
B="--base /root/probe/lanes-20261014/t12rc/fix/pkg-t12c2tP.json --base-label t12c2tP"
for r in "$@"; do
  n=${r#r}; w=$R/work/warps/look$n.txt
  $FX t12c2mW $F/g16L-$n-c-t12c2mW.json $B --warp $w > /dev/null
  $FX t12c2mW $F/g16L-$n-t-t12c2mW.json $B --set st1/$r.dar=$O/${r}x/$r.dar --texdir $O/${r}x/tex --warp $w > /dev/null
  echo "$r look fixtures ok"
done
