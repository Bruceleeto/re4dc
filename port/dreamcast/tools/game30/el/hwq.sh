#!/bin/bash
# hwq.sh <parallel> <name:arm:fixture:A:B> ...: hwmodel cost runs (lane el kit), N at a time, <= 10 flycast.exe machine-wide
# FIXDIR (env) selects the fixture directory (default /root/probe/perf-20261004/fixtures).
set -u
I=/root/probe/lanes-20261005/el/kit; L=/root/probe/lanes-20261005/el/logs
mkdir -p $L/buckets
P=$1; shift
run() { IFS=: read n a f w1 w2 <<<"$1"; bash $I/hw-ab.sh $n $a $f $w1:$w2 > $L/hwq-$n.out 2>&1; echo "$n done: $(grep -m1 -E 'drawn|total' $L/buckets/$n.md 2>/dev/null)"; }
for j in "$@"; do
  # <= P of mine, <= 10 flycast.exe machine-wide, D: >= 12 GB free before a launch (hwrun.sh drops the staged disc once its _el-discs copy is complete)
  while [ $(jobs -rp | wc -l) -ge $P ] || [ $(/mnt/c/Windows/System32/tasklist.exe 2>/dev/null | grep -ci flycast) -ge 10 ] || [ $(df --output=avail -B1G /mnt/${FREEDRV:-d} | tail -1) -lt ${MINFREEG:-12} ]; do sleep 15; done
  run "$j" &
  sleep 20
done
wait
echo HWQ-DONE
