#!/bin/bash
# hw-ab.sh <name> <arm> <fixture-name> <A:B>: one cost arm on a preset (D: staging), then its buckets
K=/root/probe/perf-20261004/kit; I=/root/probe/lanes-20261005/el/kit; L=/root/probe/lanes-20261005/el/logs
FIX=${FIXDIR:-/root/probe/perf-20261004/fixtures}/$3.json
bash $I/hwrun.sh $1 $2 $FIX $4 7 > $L/hw-$1.log 2>&1
tail -3 $L/hw-$1.log
python3 $K/bucket.py /mnt/d/Flycast-Evidence/re4-dreamcast/el-20261005/hwmodel-$1 "$1 ($2 on $3)" > $L/buckets/$1.md 2>&1
head -20 $L/buckets/$1.md
