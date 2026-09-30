#!/bin/bash
# Lane crowd: hardware-model cost of one arm at one view (adapted from the session's hwwin.sh).
#   chw.sh <label> <name> : stage scenario hw-<name> with program candidate-cw<label> (cprep.py) and FIX,
#   run hwproject on COUNT / TRACE (evidence C:\Flycast-Evidence\re4-dreamcast\hwmodel-<name>), delete the disc.
# Defaults: the r101 entry tour (play staging), the tour benchmark window 900..1380, stride 15 (all residues mod 16).
set -euo pipefail
L=${1:?label}; N=${2:?name}
FIX=${FIX:-tour/rel-r101-entry-pw.json}
COUNT=${COUNT:-900:1380}; TRACE=${TRACE:-900:1380:15}
H="/mnt/c/Game Dev/Emulators/re4-assets-private/world-agent-20260926/continuation-20260927/playability-r11-r1"
EV=/root/probe/lanes/crowd
ROOT=$(cd "$(dirname "$0")/../../../../.." && pwd)
IN=/mnt/c/Flycast-Evidence/re4-dreamcast/_crowd-hwin/$N
B=$EV/build-$L
cd "$H"
[ -d programs/candidate-cw$L ] || python3 "$ROOT/port/dreamcast/tools/d367/crowd/cprep.py" "$L"
if [ ! -f scenarios/hw-$N/disc/disc.bin ]; then
  python3 stage-scenario.py hw-$N --arm candidate-cw$L --programs programs-crowd.json \
    --overlay /mnt/c/Flycast-Evidence/re4-dreamcast/r11-media-overlay-r1/payloads --fixture "$FIX" > $EV/stage-$N.json 2>&1 \
    || { tail -5 $EV/stage-$N.json; exit 1; }
  python3 -c "import json;d=json.load(open('$EV/stage-$N.json'));print(d['status'],d['disc_sha256'])"
fi
mkdir -p $IN
cp $B/re4dc-game.elf $IN/re4dc-game.elf
OFF=$(/opt/toolchains/dc/sh-elf/bin/sh-elf-nm $B/re4dc-game.elf | awk '$3=="_re4dc_pcs"{print $1}')
[ -n "$OFF" ] || { echo "no _re4dc_pcs (needs PC_SAMPLER=1)"; exit 1; }
echo "$(cat programs/candidate-cw$L/syms.txt | tr -d '\r\n') 0x$(printf '%x' $((0x$OFF - 0x8c000000)))" > $IN/syms.txt
echo "arm=$L fixture=$FIX count=$COUNT trace=$TRACE elf=$(cut -c1-16 $B/elf.sha256) flags=$(cat $B/flags.txt)" > $IN/ARM.txt
export HWM_EVROOT=/mnt/c/Flycast-Evidence/re4-dreamcast
cd "$ROOT"
bash port/dreamcast/tools/hwmodel/hwproject.sh --name $N --disc "$H/scenarios/hw-$N/disc/disc.bin" --count $COUNT --trace $TRACE \
  --drop-traces $IN > $EV/hw-$N.log 2>&1 || { echo HWPROJECT FAILED; tail -20 $EV/hw-$N.log; }
cp $IN/ARM.txt $HWM_EVROOT/hwmodel-$N/ARM.txt 2>/dev/null || true
grep 'traced frames' $EV/hw-$N.log || true
sha256sum "$H/scenarios/hw-$N/disc/disc.bin" > "$H/scenarios/hw-$N/disc.sha256"
rm -f "$H/scenarios/hw-$N/disc/disc.bin"
