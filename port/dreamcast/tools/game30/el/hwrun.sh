#!/bin/bash
# (lane el copy) hwrun.sh <name> <arm label> <fixture> <A:B> [stride]   (perf-20261004)
# Stages the fixture with candidate-route<label> (no emulator run), then the SH-4 hardware model of the window
# (tree hwproject.sh, --frameaddr = &pG->Frame_cnt, traces kept for modesplit.sh), then modesplit.sh, then deletes the
# traces. Evidence: D:\Flycast-Evidence\re4-dreamcast\perf-20261004\hwmodel-<name>.
set -u
N=$1; L=$2; FIX=$3; WIN=$4; ST=${5:-7}
HW="/mnt/c/Game Dev/Emulators/re4-assets-private/world-agent-20260926/continuation-20260927/playability-r11-r1"
T=${HWTREE:-/root/probe/lanes-20261005/el/tree}
K=/root/probe/perf-20261004/kit
B=/root/probe/lanes/route/out-$L
EV=/mnt/d/Flycast-Evidence/re4-dreamcast/el-20261005
LOG=/root/probe/lanes-20261005/el/logs
# HWC=1 (D: short): stage, disc copy and the run's evidence dir under C:/Flycast-Evidence/re4-dreamcast/_el-cstage; the
# evidence dir (traces dropped) moves to the D: evidence root at the end.
EVD=$EV; SR=/mnt/d/Flycast-Evidence/re4-dreamcast/_el-stage; DD=/mnt/d/Flycast-Evidence/re4-dreamcast/_el-discs
if [ "${HWC:-0}" = 1 ]; then
  [ ! -e "$EVD/hwmodel-$N" ] || { echo "$EVD/hwmodel-$N exists"; exit 1; }
  EV=/mnt/c/Flycast-Evidence/re4-dreamcast/_el-cstage/hw; SR=/mnt/c/Flycast-Evidence/re4-dreamcast/_el-cstage/stage
  DD=/mnt/c/Flycast-Evidence/re4-dreamcast/_el-cstage/discs
fi
mkdir -p $EV $LOG $DD
E=$EV/hwmodel-$N
[ ! -e "$E" ] || { echo "$E exists"; exit 1; }
cd "$HW" || exit 1
S=$SR/perfhw-$N
[ ! -e "$S" ] || { echo "$S exists"; exit 1; }
python3 /root/probe/lanes-20261005/el/kit/stage-el.py perfhw-$N --stage-root $SR --arm candidate-route$L --programs "$HW/programs-route.json" \
  --overlay /mnt/c/Flycast-Evidence/re4-dreamcast/r11-media-overlay-r1/payloads --fixture $FIX > $LOG/stage-$N.json 2>&1
python3 -c "import json,sys;d=json.load(open('$LOG/stage-$N.json'));print(d['status'],d['disc_sha256'])" || { tail -5 $LOG/stage-$N.json; exit 1; }
DISC="$S/disc/disc.bin"
# lane el (D: space, from lane fm): hwproject.sh copies the staged disc to _el-discs and runs from that copy; drop the staged
# original as soon as the copy is complete (same size) instead of holding both for the whole run.
DBC=$DD/hwmodel-$N.bin
( while [ -f "$DISC" ]; do if [ -f "$DBC" ] && [ "$(stat -c %s "$DBC")" = "$(stat -c %s "$DISC")" ]; then sleep 3; rm -f "$DISC"; break; fi; sleep 2; done ) &
FA=$(bash $K/fa.sh $B/re4dc-game.elf | awk '{print $NF}')
echo "frameaddr $FA window $WIN stride $ST"
HWM_EVROOT=$EV HWM_DISCS=$DD HWM_MINFREE_MB=${MINFREE:-7000} \
  bash $T/port/dreamcast/tools/hwmodel/hwproject.sh --name $N --disc "$DISC" --frameaddr $FA --count $WIN \
  --trace $WIN:$ST $B
rc=$?
rm -f "$DISC"
cp $S/stage.json $E/stage.json 2>/dev/null
cp $FIX $E/fixture.json 2>/dev/null; cp $(python3 -c "import json;print(json.load(open('$FIX'))['replace']['dc/warp.txt'])") $E/warp.txt
echo "$L $(cut -c1-64 $B/elf.sha256)" > $E/arm.txt
[ $rc = 0 ] || { echo "hwproject rc=$rc"; exit $rc; }
bash $K/modesplit.sh $E
for f in "$E"/trace/trace-*.bin; do [ -f "$f" ] && printf '%s %s\n' "$(basename "$f")" "$(stat -c %s "$f")"; done > "$E/trace/traces-dropped.txt"
rm -f "$E"/trace/trace-*.bin
rm -f $DD/hwmodel-$N.bin $DD/hwmodel-$N.cue
if [ "$EV" != "$EVD" ]; then
  echo "run dir: C:\Flycast-Evidence\re4-dreamcast\_el-cstage\hw\hwmodel-$N (HWC=1), moved by hwrun.sh" >> $E/PURPOSE.txt
  cp -r $E $EVD/hwmodel-$N && rm -rf $E
fi
echo "done $N"
