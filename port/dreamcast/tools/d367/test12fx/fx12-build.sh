#!/bin/bash
# fx12-build.sh <arm>... (WSL): test 12 effects lane arms, built from lane/fx12 by test11/t11-build.sh (the test 11
# release recipe T11REC + the arm's knobs). One build at a time (-j4 through d367-buildslot.sh). Fresh label = fresh objdir.
# Priority (user 10-14): r101 village fps first = FX_SPRITE_TRIM and the FX_LEVEL medium / low settings; the generator
# and EFFECT_OWNERS_ALL (arm g) after, and they must not cost r101 frame time at the shipped level.
# Arm names <set><kind>; label fx12<set>t<kind> in /root/probe/lanes/route/out-<label> (kind T trace, W warp, mW TEX_CHECK):
#   c   control: T11REC, fx12 knobs off            t1  FX_SPRITE_TRIM=1 (box)        t2  FX_SPRITE_TRIM=2 (box + octagon)
#   z   t2 + FX_LEVEL=0 (dial built, level 0)      m   t2 + FX_LEVEL=1 (medium)      lo  t2 + FX_LEVEL=2 (low)
#   g0 g1 g2  t2 + PS2_FX_GEN=1 EFFECT_OWNERS_ALL=1 + FX_LEVEL=0/1/2 (the full lane)
#   e.g. "c:T t2:T m:T lo:T"  "c:W t1:W t2:W m:W lo:W"  "g0:mW"
# Special arms: base = lane/t11 tree play arm fx12btP (identity reference); knob = lane/fx12 play arm fx12ktP, every
# fx12 knob off (must be byte-identical to fx12btP: test11/ident.sh fx12btP fx12ktP).
# Trace arms are padded (IMAGE_PAD_BYTES, .bss) to PAD_TO's _end (default: the largest trace arm, g arms; build g1:T
# first) because heap 4 couples to the image size: an unpadded pair moves the r100 s30 staging failures (af field).
set -u
K=/root/probe/lanes-20261014/fx12
T=$K/tree
B=$T/port/dreamcast/tools/d367/test11/t11-build.sh
R=/root/probe/lanes/route
TR2="FX_SPRITE_TRIM=2"
knobs() { case $1 in
  c) echo "" ;; t1) echo "FX_SPRITE_TRIM=1" ;; t2) echo "$TR2" ;;
  z) echo "$TR2 FX_LEVEL=0" ;; m) echo "$TR2 FX_LEVEL=1" ;; lo) echo "$TR2 FX_LEVEL=2" ;;
  g0|g1|g2) echo "$TR2 PS2_FX_GEN=1 EFFECT_OWNERS_ALL=1 FX_LEVEL=${1:1:1}" ;;
  *) echo "?" ;; esac; }
endof() { cat $R/out-$1/end.txt 2>/dev/null; }
for a in "$@"; do
  case $a in
    base) K=$K T=/root/probe/lanes-20261014/t11/tree LP=fx12b bash $B tP; continue ;;
    knob) K=$K T=$T LP=fx12k bash $B tP; continue ;;
  esac
  set_=${a%%:*}; kind=${a#*:}; x=$(knobs $set_)
  [ "$x" = "?" ] && { echo "arm? $a"; exit 1; }
  case $kind in
    W)  K=$K T=$T LP=fx12$set_ XON="$x" bash $B tW ;;
    mW) K=$K T=$T LP=fx12$set_ XON="$x" bash $B mW ;;
    T)  lab=fx12${set_}tT; want=$(endof ${PAD_TO:-fx12g1tT}); pad=0
        for i in 1 2 3; do
          rm -rf $R/out-$lab
          K=$K T=$T LP=fx12$set_ XON="$x" PAD_T=$pad bash $B tT
          got=$(endof $lab); [ -n "$want" ] || { echo "$lab end=$got (no pad target)"; break; }
          d=$(( 0x$want - 0x$got )); echo "$lab pad=$pad end=$got want=$want diff=$d"
          [ $d = 0 ] && break; [ $d -lt 0 ] && { echo "$lab is larger than the pad target: rebuild the target padded"; break; }
          if [ $pad = 0 ] && [ $d -ge 32 ]; then pad=$(( d - 32 )); else pad=$(( pad + d )); fi   # a pad of N adds N + 32
        done ;;
    *) echo "kind? $a"; exit 1 ;;
  esac
done
