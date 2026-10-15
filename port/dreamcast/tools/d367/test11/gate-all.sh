#!/bin/bash
# gate-all.sh <gdemu dir or GDEMU zip> <label>   (Git Bash; 2026-10-14, user: "all checks 5 minutes, total and concurrent")
# Starts every release check of a packaged candidate at once and waits for all of them:
#   fp  full-play gate (fullplay/segments.conf; every segment ends within ~5 min, the 30-min `long` is opt-in)
#   cr  crash suite (fullplay/crash.conf on the hwmodel interpreter with the align logger, W11_FIXTURE twin)
#   st  STRICT/decisions windows (trace.sh pairs through trace_lock.sh, 4 slots): A = h2 to tick 2000 (s03, s20,
#       ambush, s30 340/340), B = the r101 square fight to tick 2000; each window ref vs test arm
#   kit the contributor kit check, when KIT_CMD is set (started now, alongside the gates)
# Env: FP_BUILD (release out dir, WSL path; required: another lane's identical knob-off build can otherwise be picked),
#      ST_REF / ST_TEST (trace arm labels, e.g. t11hkT / t11htT), ST_FIX_A_REF ST_FIX_A_TEST ST_FIX_B_REF ST_FIX_B_TEST
#      (fixture json paths, WSL), ST_STOP (default 2000), FP_JOBS (default 10), KIT_CMD (a Git Bash command line).
# Pass the candidate's extracted gdemu dir (not the zip) to skip the 0.9 GB _release extraction on C:.
# Disk: full-play ~1.6 GB of base discs, the crash suite ~0.8 GB (its rel base is dropped after prep), each trace
# stage ~1 GB while it runs; fp_run aborts below 15 GB free on C: and stage-scenario.py needs 16 GB + the image.
set -u
SRC=$1; LAB=$2
D="$(cd "$(dirname "$0")" && pwd)"
FPD="$D/../fullplay"
OUT=/c/Users/lambd/AppData/Local/Temp/gate-all-$LAB
mkdir -p $OUT
: "${FP_BUILD:?FP_BUILD=<release out dir> is required}"
export MSYS2_ENV_CONV_EXCL='FP_BUILD'
t0=$(date +%s)
echo "gate-all $LAB $(date +%T) src=$SRC free_c=$(df --output=avail -B1G /c | tail -1)G"
FP_JOBS=${FP_JOBS:-10} bash "$FPD/fullplay.sh" "$SRC" --label ${LAB}fp > $OUT/fp.log 2>&1 &
P_FP=$!
sleep 20
FP_TWIN_EXTRA=W11_FIXTURE=1 bash "$FPD/fullplay.sh" "$SRC" --label ${LAB}cr --conf crash.conf --align > $OUT/cr.log 2>&1 &
P_CR=$!
PIDS="$P_FP $P_CR"
if [ -n "${ST_REF:-}" ]; then
  S=${ST_STOP:-2000}
  for w in A B; do
    eval fr=\$ST_FIX_${w}_REF; eval ft=\$ST_FIX_${w}_TEST
    bash "$D/trace.sh" ${LAB}st$w-r $ST_REF $fr $S 420 > $OUT/st$w-r.log 2>&1 &
    PIDS="$PIDS $!"
    bash "$D/trace.sh" ${LAB}st$w-t $ST_TEST $ft $S 420 > $OUT/st$w-t.log 2>&1 &
    PIDS="$PIDS $!"
  done
fi
if [ -n "${KIT_CMD:-}" ]; then
  bash -c "$KIT_CMD" > $OUT/kit.log 2>&1 &
  PIDS="$PIDS $!"
fi
for p in $PIDS; do wait $p; done
if [ -n "${ST_REF:-}" ]; then
  for w in A B; do
    MSYS_NO_PATHCONV=1 wsl -d Ubuntu-24.04 -u root -- bash "/root/probe/lanes-20261014/t11/tree/port/dreamcast/tools/d367/test11/strict.sh" \
      ${LAB}st$w-r ${LAB}st$w-t ${LAB}st$w > $OUT/st$w-strict.txt 2>&1
  done
fi
echo "== full-play: $(grep -a 'verdict rc=' $OUT/fp.log | tail -1)"
echo "== crash suite: $(grep -a 'verdict rc=' $OUT/cr.log | tail -1)"
[ -n "${ST_REF:-}" ] && for w in A B; do echo "== STRICT window $w:"; cat $OUT/st$w-strict.txt; done
[ -n "${KIT_CMD:-}" ] && echo "== kit: $(tail -1 $OUT/kit.log)"
echo "gate-all $LAB wall $(( ($(date +%s) - t0) / 60 )) min; logs $OUT"
