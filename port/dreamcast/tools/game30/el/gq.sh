#!/bin/bash
# (Git Bash) gq.sh <P> "<name> <label> <fixture WSL path> <secs> <period> [ALIGN]" ...: lane el gate runs through drun.sh
# (D: staging, vsync off), at most P of mine at once, < 10 flycast.exe machine-wide, D: >= 12 GB free at each launch
# (a staged disc is 0.94 GB); each run's staged disc deleted by dfinish.sh when its capture is done.
cd "$(dirname "$0")"   # the kit directory (drun.sh, dfinish.sh next to this script)
E=/d/Flycast-Evidence/re4-dreamcast/el-20261005
mkdir -p runs
P=$1; shift
freeg() { df -BG /${FREEDRV:-d} | awk 'NR==2{gsub("G","",$4); print $4}'; }
one() {  # name label fixture secs period [ALIGN]
  ALIGN=${6:-0} VSYNC=0 bash drun.sh $1 $2 $3 $4 $5 > runs/$1.launch 2>&1 || { echo "$1 launch failed: $(tail -2 runs/$1.launch | tr '\n' ' ')" >> runs/done.txt; return; }
  until grep -q '^done' $E/dyn-$1/capture-run.out 2>/dev/null || grep -q '^done' /c/Flycast-Evidence/re4-dreamcast/_el-cstage/run/dyn-$1/capture-run.out 2>/dev/null; do sleep 20; done
  bash dfinish.sh $1 >> runs/done.txt 2>&1
}
for j in "$@"; do
  while [ "$(jobs -rp | wc -l)" -ge "$P" ] || [ "$(tasklist | grep -ci flycast)" -ge 10 ] || [ "$(freeg)" -lt ${MINFREE:-12} ]; do sleep 20; done
  one $j &
  sleep 60
done
wait
echo "GQ-DONE $*" >> runs/done.txt
