#!/bin/bash
# usage: trig_fsca_check.sh <tree> <fsca-table.h> [opt]   numerical check of GAME_TRIG_FSCA / GAME_ROT_FSCA
# (lane fm 2026-10-05): the FSCA re4dc_sincosf of game30_trig.c (RE4DC_TRIG_FSCA=1, FSCA emulated from the dumped
# hardware table, e.g. Flycast's core/hw/sh4/fsca-table.h; the table is not in this repository) against the
# exact re4dc_exact_sincosf and the true sin / cos, every 2^32 input (tools/game30/trig_fsca_check.c).
set -euo pipefail
T=${1:?tree}; TAB=${2:?fsca-table.h}; OPT=${3:--O2}
W=$(mktemp -d); trap 'rm -rf $W' EXIT
F=$T/src/lib/fdlibm
CF="$OPT -ffp-contract=off -fno-fast-math -msse2 -mfpmath=sse -w -I$T/include -I$F"
REN="-D__kernel_sinf=ref_ksinf -D__kernel_cosf=ref_kcosf -D__ieee754_rem_pio2f=ref_rem_pio2f -D__kernel_rem_pio2f=ref_krem_pio2f"
for u in kf_sin kf_cos ef_rem_pio2 kf_rem_pio2; do gcc $CF $REN -c $F/$u.c -o $W/$u.o; done
gcc $CF -DRE4DC_SINCOS=1 -DRE4DC_TRIG_LEAN=1 -DRE4DC_TRIG_FSCA=1 -Dsinf=new_sinf -Dcosf=new_cosf \
    -D__ieee754_rem_pio2f=ref_rem_pio2f -D__kernel_rem_pio2f=ref_krem_pio2f \
    -c $T/port/dreamcast/game/game30_trig.c -o $W/new.o
gcc -O2 -msse2 -c $(dirname $0)/trig_fsca_check.c -o $W/main.o
gcc $W/*.o -o $W/tf -lpthread -lm
time $W/tf "$TAB"
