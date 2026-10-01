#!/bin/bash
# Lane crowd: detached queue. cqueue.sh <jobfile> <workers>
# Job lines:  build <label> [ASSETS=<dir>] [knobs...]          (run in file order by worker 1 before any hw job that needs it)
#             hw <label> <name> <view>           view e = r101 entry 900:1380, l = r101 entry 2040:2520 (worst view),
#                                                s = r100 s20 ambush 1240:1720 (enc lane's views, stride 15);
#                                                b = r101 bell fight 1240:1720 (enc lane's Ganados-on-screen view);
#                                                k = r101 kite (kite-mesh-fixture-r21.json) 900:1380, ~5 Ganados < 5 m;
#                                                e2/l2/s2/b2/k2 = the same with the PS2 em15-00 atlas staged (fix/*-ps2.json)
# MINFREE (default 22): a job starts only with C: >= MINFREE GB (a traced run peaks at ~1.5 GB of C:; keep >= 16).
# Launch: setsid nohup bash cqueue.sh jobs.txt 2 > /root/probe/lanes/crowd/logs/queue-<x>.out 2>&1 < /dev/null &
set -u
J=$1; W=${2:-2}
T=$(cd "$(dirname "$0")" && pwd)
EV=/root/probe/lanes/crowd; mkdir -p $EV/logs
LOCK=$EV/logs/$(basename $J).lock; DONE=$EV/logs/$(basename $J).done; : >> $DONE
log() { echo "$(date +%T) $*"; }
# Builds first, serially (one objdir each; link.sh's missing.txt is per tree).
grep '^build ' $J | while read -r _ L K; do
  grep -qx "build $L" $DONE && continue
  A=; KK=; for k in $K; do case $k in ASSETS=*) A=${k#ASSETS=} ;; *) KK="$KK $k" ;; esac; done
  log "build $L $K"; ASSETS="$A" bash $T/cbuild.sh $L $KK > $EV/logs/build-$L.out 2>&1; log "built $L rc=$? $(tail -2 $EV/logs/build-$L.out | tr '\n' ' ')"
  H="/mnt/c/Game Dev/Emulators/re4-assets-private/world-agent-20260926/continuation-20260927/playability-r11-r1"
  rm -rf "$H/programs/candidate-cw$L"; python3 $T/cprep.py $L >> $EV/logs/build-$L.out 2>&1
  echo "build $L" >> $DONE
done
worker() {
  while true; do
    job=$(flock $LOCK bash -c "grep '^hw ' $J | while read -r l; do grep -qxF \"\$l\" $DONE $DONE.taken 2>/dev/null || { echo \"\$l\"; echo \"\$l\" >> $DONE.taken; break; }; done")
    [ -z "$job" ] && return
    set -- $job; L=$2; N=$3; V=$4
    case $V in
      e) FIX=tour/rel-r101-entry-pw.json; C=900:1380 ;;
      l) FIX=tour/rel-r101-entry-pw.json; C=2040:2520 ;;
      s) FIX=tour/rel-r100-s20-pw.json; C=1240:1720 ;;
      e2) FIX=$EV/fix/rel-r101-entry-pw-ps2.json; C=900:1380 ;;
      b) FIX=tour/enc-rel-r101-bell-fight-pw.json; C=1240:1720 ;;
      k) FIX=kite-mesh-fixture-r21.json; C=900:1380 ;;
      k2) FIX=$EV/fix/kite-mesh-fixture-r21-ps2.json; C=900:1380 ;;
      b2) FIX=$EV/fix/enc-rel-r101-bell-fight-pw-ps2.json; C=1240:1720 ;;
      l2) FIX=$EV/fix/rel-r101-entry-pw-ps2.json; C=2040:2520 ;;
      s2) FIX=$EV/fix/rel-r100-s20-pw-ps2.json; C=1240:1720 ;;
    esac
    free=$(df -BG /mnt/c | awk 'NR==2{print $4}' | tr -d G)
    while [ "$free" -lt ${MINFREE:-22} ]; do log "C: ${free}G free, waiting"; sleep 60; free=$(df -BG /mnt/c | awk 'NR==2{print $4}' | tr -d G); done
    log "start $N ($L $V)"
    FIX=$FIX COUNT=$C TRACE=$C:15 bash $T/chw.sh $L $N > $EV/logs/hw-$N.out 2>&1
    log "done $N: $(grep -h 'hardware projection' $EV/hw-$N.log | head -1)"
    echo "$job" >> $DONE
  done
}
for w in $(seq $W); do worker & sleep 40; done
wait
log "queue finished"
