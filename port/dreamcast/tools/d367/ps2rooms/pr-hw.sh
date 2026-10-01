#!/bin/bash
# pr-hw.sh <name> <arm> <programs.json> <fixture> [count A:B] [trace A:B:S]   (lane ps2rooms, 2026-10-01)
# Hardware-model cost of one view with a given world package: tools/d367/enc/enc-hw.sh's method (lane enc) with the
# arm and programs file as arguments and the fixture an absolute path (e.g. a tour fixture copy whose PS2-world
# package entries were swapped, made by the lane's mkfix step). Stages the playability-harness scenario
# hw-<name>, runs tools/hwmodel/hwproject.sh (evidence C:/Flycast-Evidence/re4-dreamcast/hwmodel-<name>, traces
# dropped), then deletes the staged disc (disc.sha256 kept). Names are single-use.
set -euo pipefail
N=$1; ARM=$2; PROG=$3; FIX=$4; COUNT=${5:-900:1380}; TRACE=${6:-900:1380:16}
T=$(cd "$(dirname "$0")/../../../../.." && pwd)
E=/root/probe/lanes/ps2rooms
H="/mnt/c/Game Dev/Emulators/re4-assets-private/world-agent-20260926/continuation-20260927/playability-r11-r1"
EV=/mnt/c/Flycast-Evidence/re4-dreamcast
IN=$EV/_ps2rooms-hwin/$N
mkdir -p $E/logs $E/stage
[ ! -e $EV/hwmodel-$N ] || { echo "hwmodel-$N exists (names are single-use)"; exit 1; }
S="$H/scenarios/hw-$N"
ELF=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))[sys.argv[2]]['elf'])" "$H/$PROG" "$ARM")
O=$(dirname "$ELF")
cd "$H"
if [ ! -f "$S/disc/disc.bin" ]; then
  rm -rf "$S"
  python3 stage-scenario.py hw-$N --arm $ARM --programs $PROG \
    --overlay $EV/r11-media-overlay-r1/payloads --fixture "$FIX" > $E/stage/$N.json 2>&1 \
    || { tail -5 $E/stage/$N.json; exit 1; }
  python3 -c "import json,sys;d=json.load(open(sys.argv[1]));print(d['status'],d['disc_sha256'])" $E/stage/$N.json
fi
mkdir -p $IN
cp $O/re4dc-game.elf $O/syms.txt $IN/
printf 'lane ps2rooms view %s: arm %s (%s), fixture %s, count %s trace %s\n' "$N" "$ARM" "$(cut -c1-16 $O/elf.sha256)" "$FIX" "$COUNT" "$TRACE" > $IN/PURPOSE.txt
export HWM_EVROOT=$EV
cd $T
bash port/dreamcast/tools/hwmodel/hwproject.sh --name $N --disc "$S/disc/disc.bin" --count $COUNT --trace $TRACE \
  --drop-traces $IN > $E/logs/hw-$N.log 2>&1 || { echo "HWPROJECT FAILED"; tail -20 $E/logs/hw-$N.log; }
sha256sum "$S/disc/disc.bin" > "$S/disc.sha256"
rm -f "$S/disc/disc.bin"
grep -E 'hardware projection|Flycast \(dynarec' $E/logs/hw-$N.log || true
