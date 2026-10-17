#!/bin/bash
# mkfix.sh (WSL): worldtest16 fixtures, one per (camera, arm). Arm A = current world (r101: bake13 = pre-world32, no
# variant 5), B = world16 as built (r101: world32 as landed = T15 default data), C = landmark-protected recipe
# (re4-assets-private/worldtest-20261016). Same ELF (wtrT, WORLD_VERT=1 LEVEL=5) for every arm.
set -eu
TR=/root/probe/worldtest16-20261016/tree/port/dreamcast/tools/d367/test11/t11-fix.py
OUT=/root/probe/worldtest16-20261016/fix; mkdir -p $OUT
WD=/mnt/c/Flycast-Evidence/re4-dreamcast/worldtest-20261016/_tools/w
PRIV="/mnt/c/Game Dev/Emulators/re4-assets-private"
W16="$PRIV/world16-ch1-20261016"; WT="$PRIV/worldtest-20261016"; B13="$PRIV/crowd12-bake-20261015/r101-t13"
DATA=cast15,glod,res16,snd16,res16h,vq16cs,water16h,wv32r101
F6="ps2-world.re4mesh ps2-world.r4pw ps2-world.ids ps2-world.r4sg ps2-wv5.re4mesh ps2-wv5.r4sg"
for cam in r101-c1 r101-c2 r102-c1 r102-c2 r106-c1 r106-c2 r108-c1 r108-c2 r10a-c1 r10a-c2; do
  r=${cam%-*}
  for arm in A B C; do
    S=()
    if [ $r = r101 ]; then
      case $arm in
        A) for f in ps2-world.re4mesh ps2-world.r4pw ps2-world.ids ps2-world.r4sg; do S+=(--set "dc/native/r101/$f=$B13/$f"); done
           S+=(--rm dc/native/r101/ps2-wv5.re4mesh --rm dc/native/r101/ps2-wv5.r4sg) ;;
        B) ;;
        C) for f in $F6; do S+=(--set "dc/native/r101/$f=$WT/r101/$f"); done ;;
      esac
    else
      case $arm in
        A) ;;
        B) for f in $F6; do S+=(--set "dc/native/$r/$f=$W16/$r/$f"); done ;;
        C) for f in $F6; do S+=(--set "dc/native/$r/$f=$WT/$r/$f"); done ;;
      esac
    fi
    python3 $TR wtrT $OUT/$cam-$arm.json --base /root/probe/lanes-20261015/t14rc/fix/pkg-t14rcrP.json --base-label t14rcrP \
      --data $DATA --warp $WD/$cam.txt "${S[@]}" > $OUT/$cam-$arm.log 2>&1 || { echo "FAIL $cam-$arm"; tail -3 $OUT/$cam-$arm.log; }
  done
done
ls $OUT/*.json | wc -l
