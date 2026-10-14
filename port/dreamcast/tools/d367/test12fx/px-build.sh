#!/bin/bash
# px-build.sh <set>... (WSL): GPU-proxy twin builds (hwfog lane's TA-stats method: fp_master base + flycast6 TA stats)
# of the fx12 sets on lane/fx12: the test 11 play recipe (out-fx12ktP/candidate.txt) + the twin diag knobs + the set's
# knobs. Label fx12px<set>. Sets: c, t2, m (FX_LEVEL=1), lo (FX_LEVEL=2), v0 / v2 (village disc knobs at level 0 / 2).
set -u
T=/root/probe/lanes-20261014/fx12/tree
L=/root/probe/lanes-20261014/fx12/logs-build.txt
export SOURCE_DATE_EPOCH=1760000000
REC=$(cat /root/probe/lanes/route/out-fx12ktP/candidate.txt)
DIAG="DBG_WARP=1 WARP_JUMP=1 PC_SAMPLER=0 TEX_CHECK=1 MCHECK_LEONGC=1"
for s in "$@"; do
  case $s in
    c) X="" ;; t2) X="FX_SPRITE_TRIM=2" ;; m) X="FX_SPRITE_TRIM=2 FX_LEVEL=1" ;; lo) X="FX_SPRITE_TRIM=2 FX_LEVEL=2" ;;
    v0|v2) X="FX_SPRITE_TRIM=2 FX_LEVEL=${s:1:1} HW_FOG_HAZE=1" ;;
    *) echo "set? $s"; exit 1 ;;
  esac
  LAB=fx12px$s; O=/root/probe/lanes/route/out-$LAB; rm -rf $O
  echo "== $LAB $(date +%T) $X" >> $L
  (cd $T && TREE=$T bash /root/probe/d367-buildslot.sh bash port/dreamcast/tools/d367/route/route-build.sh $LAB $REC $DIAG $X >> $L 2>&1)
  echo "rc=$? $LAB $(cut -c1-16 $O/elf.sha256 2>/dev/null) missing=$(wc -c < $O/missing.txt 2>/dev/null) $(grep -E '^(FX_LEVEL|FX_SPRITE_TRIM|HW_FOG_HAZE|DBG_WARP|PC_SAMPLER)=' $O/resolved-knobs.txt 2>/dev/null | tr '\n' ' ')"
done
