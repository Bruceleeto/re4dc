#!/bin/bash
# enc-hw.sh <name> <label> <fixture> [count A:B] [trace A:B:S]  (lane enc, 2026-09-30)
# Hardware-model cost of one view: stage the playability-harness scenario hw-enc-<name> (candidate-enc<label> from
# enc-build.sh, fixture relative to the harness dir, e.g. tour/rel-r101-entry-pw.json), run
# tools/hwmodel/hwproject.sh on it (evidence C:/Flycast-Evidence/re4-dreamcast/hwmodel-enc-<name>, traces dropped),
# extract the ENC census lines of the same run, then delete the staged disc (disc.sha256 kept).
# Default window 900:1380, trace stride 16 (the testing skill's tour window). Names are single-use.
set -euo pipefail
N=$1; L=$2; FIX=$3; COUNT=${4:-900:1380}; TRACE=${5:-900:1380:16}
T=$(cd "$(dirname "$0")/../../../../.." && pwd)
E=/root/probe/lanes/enc
H="/mnt/c/Game Dev/Emulators/re4-assets-private/world-agent-20260926/continuation-20260927/playability-r11-r1"
EV=/mnt/c/Flycast-Evidence/re4-dreamcast
IN=$EV/_enc-hwin/$N
O=$E/out-$L
mkdir -p $E/logs $E/stage
[ ! -e $EV/hwmodel-enc-$N ] || { echo "hwmodel-enc-$N exists (names are single-use)"; exit 1; }
S="$H/scenarios/hw-enc-$N"
cd "$H"
if [ ! -f "$S/disc/disc.bin" ]; then
  rm -rf "$S"
  python3 stage-scenario.py hw-enc-$N --arm candidate-enc$L --programs programs-enc.json \
    --overlay $EV/r11-media-overlay-r1/payloads --fixture "$FIX" > $E/stage/$N.json 2>&1 \
    || { tail -5 $E/stage/$N.json; exit 1; }
  python3 -c "import json,sys;d=json.load(open(sys.argv[1]));print(d['status'],d['disc_sha256'])" $E/stage/$N.json
fi
mkdir -p $IN
cp $O/re4dc-game.elf $O/syms.txt $IN/
printf 'lane enc view %s: build enc%s (%s), fixture %s, count %s trace %s\n' "$N" "$L" "$(cut -c1-16 $O/elf.sha256)" "$FIX" "$COUNT" "$TRACE" > $IN/PURPOSE.txt
export HWM_EVROOT=$EV
cd $T
bash port/dreamcast/tools/hwmodel/hwproject.sh --name enc-$N --disc "$S/disc/disc.bin" --count $COUNT --trace $TRACE \
  --drop-traces $IN > $E/logs/hw-$N.log 2>&1 || { echo "HWPROJECT FAILED"; tail -20 $E/logs/hw-$N.log; }
sha256sum "$S/disc/disc.bin" > "$S/disc.sha256"
rm -f "$S/disc/disc.bin"
R=$EV/hwmodel-enc-$N
if [ -f $R/boot.log ]; then
  iconv -f UTF-16 -t UTF-8 $R/boot.log 2>/dev/null | tr -d '\r' | grep -a '^ENC f=' > $R/enc-census.txt || true
  echo "census lines $(wc -l < $R/enc-census.txt)"
fi
grep -E 'hardware projection|Flycast \(dynarec' $E/logs/hw-$N.log || true
