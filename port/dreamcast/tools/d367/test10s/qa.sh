#!/bin/bash
# qa.sh <lane> "name label secs [runner] [period]" ... : runs one after another; two lanes = at most 2 Flycasts.
F=/root/probe/lanes-20261014/t10s/fix
cd /c/Flycast-Evidence/re4-dreamcast/t10s-20261014/_tools
id=$1; shift
for j in "$@"; do set -- $j
  for try in $(seq 1 10); do
    rm -f run-$1.log
    RUNNER=${4:-run-emulator-novsync-i26.py} PERIOD=${5:-30} bash t-run.sh $1 $2 $F/$1-$2.json $3 > run-$1.log 2>&1
    grep -q 'stage failed' run-$1.log || break
    sleep 60
  done
  echo "$(date +%T) $id done $1: $(tail -2 run-$1.log | head -1)" >> q.log
done
echo "Q_DONE $id" >> q.log
