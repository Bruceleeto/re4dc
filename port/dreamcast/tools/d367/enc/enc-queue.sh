#!/bin/bash
# enc-queue.sh <jobs-file> [parallel]  (WSL; lane enc, 2026-09-30)
# Runs enc-hw.sh jobs ("name label fixture count trace" per line, # comments) at most <parallel> at a time (default
# 3), each only while C: keeps >= 20 GB free and fewer than 9 flycast.exe run machine-wide. Logs to
# /root/probe/lanes/enc/logs/queue-<name>.log; a job whose hwmodel-enc-<name> exists is skipped.
# Launch detached (survives a stopped session):
#   setsid nohup bash enc-queue.sh <jobs> 3 > /root/probe/lanes/enc/logs/queue-<tag>.out 2>&1 < /dev/null &
set -u
J=$1; P=${2:-3}
D=$(cd "$(dirname "$0")" && pwd)
EV=/mnt/c/Flycast-Evidence/re4-dreamcast
free_gb() { df -BG --output=avail /mnt/c | tail -1 | tr -dc 0-9; }
flycasts() { /mnt/c/Windows/System32/tasklist.exe /FI "IMAGENAME eq flycast.exe" /NH < /dev/null 2>/dev/null | grep -ci flycast; }
echo "queue pid $$ jobs $J parallel $P"
while read -r -u 3 N L F C T; do
  [ -e $EV/hwmodel-enc-$N ] && { echo "skip $N (exists)"; continue; }
  while [ "$(jobs -rp | wc -l)" -ge "$P" ] || [ "$(free_gb)" -lt 20 ] || [ "$(flycasts)" -ge 9 ]; do sleep 20; done
  echo "start $N $L $F $C $T free=$(free_gb)G $(date +%T)"
  ( bash $D/enc-hw.sh $N $L $F $C $T < /dev/null > /root/probe/lanes/enc/logs/queue-$N.log 2>&1
    echo "done $N $(date +%T): $(grep -h 'hardware projection' /root/probe/lanes/enc/logs/queue-$N.log)" ) &
  sleep 60
done 3< <(grep -v '^\s*#' "$J" | grep -v '^\s*$')   # fd 3: tasklist.exe / enc-hw.sh must not eat the list
wait
echo QUEUE-DONE
