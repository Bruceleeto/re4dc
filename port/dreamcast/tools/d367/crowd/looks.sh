#!/bin/bash
# Lane crowd: look-sheet builds. Each arm of the draw-fewer / tier table rebuilt with CROWD_FREEZE_AT / AT2 / HOLD, so
# a Flycast run (crun.sh) holds the same game frames in every arm: the kite fixture's t=FZ1-1 (~5 Ganados < 5 m) and
# the r101 entry tour's t=FZ2-1 (two Ganados at 12..25 m). Labels z<arm>.
#   looks.sh build            build every z arm (serially; cbuild.sh)
#   looks.sh run <arm> <k|l>   (Git Bash) crun.sh of z<arm> on the kite (k) or tour (l) fixture
set -euo pipefail
EV=/root/probe/lanes/crowd
T=$(cd "$(dirname "$0")" && pwd)
FZ="CROWD_FREEZE_AT=${FZ1:-1100} CROWD_FREEZE_AT2=${FZ2:-2280} CROWD_FREEZE_HOLD=${HOLD:-40}"
arms() {
  cat <<A
c0 -
r1c - CROWD_READOPT=1 CROWD_CULL=1
r1n2 - CROWD_READOPT=1 CROWD_CULL=1 CROWD_DRAW_MAX=2
r1n4 - CROWD_READOPT=1 CROWD_CULL=1 CROWD_DRAW_MAX=4
r1d12 - CROWD_READOPT=1 CROWD_CULL=1 CROWD_DRAW_M=12
fn3 assets-far CROWD_READOPT=1 CROWD_CULL=1 CROWD_NEAR_MAX=3
f12 assets-far CROWD_READOPT=1 CROWD_CULL=1 CROWD_FAR_M=12
p2 assets-ps2 CROWD_READOPT=1 CROWD_CULL=1
p2n3 assets-ps2far CROWD_READOPT=1 CROWD_CULL=1 CROWD_NEAR_MAX=3
A
}
case ${1:?build|run} in
  build)
    arms | while read -r a s k; do
      A=; [ "$s" = - ] || A=$EV/$s
      # c0 has no crowd knob of its own: the freeze knobs alone select the crowd code (RE4DC_CROWD=1, every policy off).
      # shellcheck disable=SC2086
      ASSETS="$A" bash "$T/cbuild.sh" z$a $k $FZ 2>&1 | tail -1
    done ;;
  run)
    a=${2:?arm}; v=${3:?k|l}
    case $v in
      k) F=kite-mesh-fixture-r21.json ;; l) F=tour/rel-r101-entry-pw.json ;;
      k2) F=$EV/fix/kite-mesh-fixture-r21-ps2.json ;; l2) F=$EV/fix/rel-r101-entry-pw-ps2.json ;;
    esac
    FIX=$F PERIOD=${PERIOD:-10} bash "$T/crun.sh" z$a look-$a-$v ${SECS:-240} ;;
esac
