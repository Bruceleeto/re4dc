#!/bin/bash
# after.sh <jobs-name> <workers> <pid...>: run the queue once every listed PID has exited
J=$1; W=$2; shift 2
T=/root/work/lanes/crowd/port/dreamcast/tools/d367/crowd
while :; do a=0; for p in "$@"; do kill -0 $p 2>/dev/null && a=1; done; [ $a = 0 ] && break; sleep 30; done
exec bash $T/cqueue.sh $T/$J.txt $W
