#!/bin/bash
# lock-h2.sh <t|c>: one H2 trace run under a trace slot (WSL side), stop tick 4700 (as the 9.1 regfix gate)
x=$1; L=t10s${x}T
TRACE_LOCK_OWNER=claude-t10s bash /root/probe/lanes-20261014/t10s/tree/port/dreamcast/tools/d367/trace_lock.sh "/mnt/c/Program Files/Git/bin/bash.exe" -c "cd /c/Flycast-Evidence/re4-dreamcast/t10s-20261014/_tools && RE4DC_LOG_STOP_TICK=4700 PURPOSE='test 10 small H2 STRICT gate $L (t = candidate a93e8be0 + hands knobs, c = 9.1 40fb4deb padded to the same _end; both with the candidate data)' bash t-run.sh h2$x $L /root/probe/lanes-20261014/t10s/fix/h2-$L.json 600 > run-h2$x.log 2>&1"
