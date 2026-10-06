#!/bin/bash
# PS2_INTERIOR_CULL: run the hull caster (cast_cell.cpp) for every sub-cell that build_cell.py prepare wrote: the face
# targets (exits_<i>.txt) and the occluder boundary-edge targets (exits_e_<i>.txt).
# usage: cast_cell.sh <work dir> [threads]     (Linux / WSL, g++ with OpenMP)
#        cast_cell.sh --verify <work dir> [threads] [directions]   after build_cell.py emit: probe_eye.cpp from each
#        sub-cell's corners and centre, every escaping direction must exit inside that sub-cell's portals.
set -eu
D=$(cd "$(dirname "$0")" && pwd)
if [ "$1" = --verify ]; then
  W=$2; J=${3:-8}; K=${4:-400000}
  g++ -O2 -fopenmp -o "$W/probe_eye" "$D/probe_eye.cpp"
  read NEAR CELL EPS < "$W/params.txt"
  n=$(ls "$W"/cams_*.bin | wc -l); bad=0
  for i in $(seq 0 $((n - 1))); do
    out=$(PROBE_MISS_OUT="$W/exits_v_$i.txt" PROBE_CELL=$CELL OMP_NUM_THREADS=$J "$W/probe_eye" "$W/tris.bin" "$W/hull.txt" "$W/portals_$i.txt" "$K" "$NEAR" $(cat "$W/verify_eyes_$i.txt"))
    m=$(echo "$out" | awk '/^eye/ {s+=$7} END {print s+0}')
    [ "$m" = 0 ] || { echo "sub-cell $i: $m directions outside its portals"; echo "$out" | grep MISS | head -5; bad=$((bad + m)); }
  done
  [ "$bad" = 0 ] || echo "misses appended to exits_v_<i>.txt: re-run build_cell.py emit, then --verify again"
  echo "verify: $n sub-cells, $K directions per eye, $bad directions outside the portals"
  exit 0
fi
W=$1; J=${2:-8}
g++ -O2 -fopenmp -o "$W/cast_cell" "$D/cast_cell.cpp"
read NEAR CELL EPS < "$W/params.txt"
n=$(ls "$W"/cams_*.bin | wc -l)
for i in $(seq 0 $((n - 1))); do
  OMP_NUM_THREADS=$J "$W/cast_cell" "$W/tris.bin" "$W/cams_$i.bin" "$W/targets.bin" "$W/hull.txt" "$W/exits_$i.txt" "$NEAR" "$CELL" "$EPS"
  OMP_NUM_THREADS=$J "$W/cast_cell" "$W/tris.bin" "$W/cams_$i.bin" "$W/targets_edges.bin" "$W/hull.txt" "$W/exits_e_$i.txt" "$NEAR" "$CELL" "$EPS"
done
cat "$W"/exits_*.txt | awk '/^#/ {r+=$3; e+=$5; k++} END {print "runs", k, "rays", r, "escaped", e}'
