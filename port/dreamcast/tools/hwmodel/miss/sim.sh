#!/bin/bash
# sim.sh VARIANT "hwsim args..."  : re-simulate the 4 kept hwcal live-scene trace sets with the phase table.
# Output: $OUT/hw-<scene>/proj/<VARIANT>.phases.tsv (layout like hwcal, so regress.py reads it).
set -u
V=$1; shift; ARGS="$*"
H=/root/probe/hwmiss-20261015/hwsim-m
SRC=/mnt/d/Flycast-Evidence/re4-dreamcast/hwcal-20261015
OUT=/mnt/c/Flycast-Evidence/re4-dreamcast/hwmiss-20261015/sim
PH=/root/probe/hwcal-20261015/phase-sites.txt
for sc in cross house dellago farm; do
  P=$OUT/hw-$sc/proj; mkdir -p $P
  ( cd $P && $H --elf $SRC/hw-$sc/re4dc-game.elf --out $V --phase $PH $ARGS $SRC/hw-$sc/trace/trace-*.bin > $V.log 2>&1
    rm -f $V.pcs.tsv $V.lines.tsv ) &
done
wait
for sc in cross house dellago farm; do echo "$sc $(tail -1 $OUT/hw-$sc/proj/$V.log)"; done
