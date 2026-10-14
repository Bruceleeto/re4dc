#!/bin/bash
# trace.sh <name> <label> <fixture> <stop tick> [seconds] (Git Bash): one logic-trace run (t-run.sh) under a trace slot
# (trace_lock.sh, WSL side, held only around the run). Both runs of a STRICT pair use the same stop tick and fixture data.
N=$1; L=$2; FIX=$3; STOP=$4; SECS=${5:-600}
K=/root/probe/lanes-20261014/t11/tree/port/dreamcast/tools/d367
G=/c/Flycast-Evidence/re4-dreamcast/t11-20261014/_tools
mkdir -p $G; cp "//wsl.localhost/Ubuntu-24.04$K/test11/t-run.sh" $G/t-run.sh
cat > $G/tr-$N.sh <<EOS
cd $G && RE4DC_LOG_STOP_TICK=$STOP PURPOSE='t11 trace $N: $L, $FIX, stop $STOP' bash t-run.sh $N $L $FIX $SECS > $G/run-$N.log 2>&1
EOS
MSYS_NO_PATHCONV=1 wsl -d Ubuntu-24.04 -u root -- env TRACE_LOCK_OWNER=claude-t11-$N bash $K/trace_lock.sh "/mnt/c/Program Files/Git/bin/bash.exe" $(cygpath -m $G/tr-$N.sh | sed 's#^C:#/c#')
tail -3 $G/run-$N.log
