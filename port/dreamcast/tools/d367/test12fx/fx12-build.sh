#!/bin/bash
# fx12-build.sh <arm>... (WSL): test 12 effects lane arms, built from lane/fx12 by test11/t11-build.sh (the test 11
# release recipe T11REC + the fx12 knobs). One build at a time (-j4 through d367-buildslot.sh). Fresh label = fresh objdir.
# Arms (label in /root/probe/lanes/route/out-<label>):
#   base   fx12btP  lane/t11 tree (T11 HEAD), play arm: the identity reference
#   knob   fx12ktP  lane/fx12, play arm, fx12 knobs off: must be byte-identical to fx12btP (ident.sh)
#   L0T L1T L2T fx12l<n>tT  trace arms, T11REC + FX12 + FX_LEVEL=<n>
#   cT     fx12ctT  trace control: T11REC, fx12 knobs off, image padded to the L arms' _end (heap 4 couples to the
#                  image size: an unpadded control moves the r100 s30 staging failures, see docs/lanes/fx12.md)
#   L0W L1W L2W cW  warp arms (ms runs), same knobs, no pad
#   mW     fx12m0mW  warp + MCHECK_LEONGC=1 TEX_CHECK=2, FX_LEVEL=0 (the most effect draws: TEX_CHECK coverage)
set -u
K=/root/probe/lanes-20261014/fx12
T=$K/tree
B=$T/port/dreamcast/tools/d367/test11/t11-build.sh
FX12="PS2_FX_GEN=1 EFFECT_OWNERS_ALL=1 FX_SPRITE_TRIM=1"
R=/root/probe/lanes/route
endof() { cat $R/out-$1/end.txt 2>/dev/null; }
for a in "$@"; do case $a in
  base) K=$K T=/root/probe/lanes-20261014/t11/tree LP=fx12b bash $B tP ;;
  knob) K=$K T=$T LP=fx12k bash $B tP ;;
  L[012]T) n=${a:1:1}; K=$K T=$T LP=fx12l$n XON="$FX12 FX_LEVEL=$n" bash $B tT ;;
  L[012]W) n=${a:1:1}; K=$K T=$T LP=fx12l$n XON="$FX12 FX_LEVEL=$n" bash $B tW ;;
  cW) K=$K T=$T LP=fx12c bash $B tW ;;
  mW) K=$K T=$T LP=fx12m0 XON="$FX12 FX_LEVEL=0" bash $B mW ;;
  cT) # pad the control to the L1 trace arm's _end (build L1T first)
      want=$(endof fx12l1tT); [ -n "$want" ] || { echo "build L1T first"; exit 1; }
      pad=${PAD_C:-0}
      for i in 1 2 3; do
        rm -rf $R/out-fx12ctT
        K=$K T=$T LP=fx12c PAD_T=$pad bash $B tT
        got=$(endof fx12ctT); d=$(( 0x$want - 0x$got ))
        echo "cT pad=$pad end=$got want=$want diff=$d"
        [ $d = 0 ] && break
        pad=$(( pad + d ))
      done ;;
  *) echo "arm? $a"; exit 1 ;;
esac; done
