#!/bin/bash
# q.sh: worldtest16 still runs (trace arm wtrT, 60 s, shots every 10 s), at most MAXP at once.
cd /c/Flycast-Evidence/re4-dreamcast/worldtest-20261016/_tools
MAXP=${MAXP:-3}
for n in "$@"; do
  while [ $(jobs -rp | wc -l) -ge $MAXP ]; do sleep 5; done
  ( TRACE=1 PERIOD=10 bash t-run.sh $n wtrT /root/probe/worldtest16-20261016/fix/$n.json 60 > $n.log 2>&1 ) &
  sleep 15
done
wait; echo Q_DONE
