#!/bin/bash
# proof 1 (lane stage-ext4): byte identity + time + 9p bytes, one staging at a time.
set -u
S=/mnt/c/Users/lambd/AppData/Local/Temp/stx4
T=/root/probe/lanes-20261014/stage/tree/port/dreamcast/tools/d367/stage_ext4
mkdir -p $T
for f in stage_scenario.py disccache.py clean.sh freeze.py harness-shim.py; do tr -d '\r' < $S/$f > $T/$f; done
chmod +x $T/*.py $T/clean.sh
HW="/mnt/c/Game Dev/Emulators/re4-assets-private/world-agent-20260926/continuation-20260927/playability-r11-r1"
OV=/mnt/c/Flycast-Evidence/re4-dreamcast/r11-media-overlay-r1/payloads
FIX=${FIX:-/root/probe/lanes-20261014/t10s/fix/h2-t10stT.json}
ARM=${ARM:-candidate-routet10stT}
P=/root/probe/lanes-20261014/stage/proof; mkdir -p $P
FT=1792000000
TIMEFORMAT='%R wall %U user %S sys'
ARGS="--arm $ARM --programs programs-route.json --overlay $OV --fixture $FIX"
st() {  # name, then command
  local n=$1; shift
  { time "$@" > $P/$n.json 2> $P/$n.err; } 2> $P/$n.time
  echo "$n: $(cat $P/$n.time) $(python3 -c "import json,sys;d=json.load(open(sys.argv[1]));print(d['status'],d['disc_sha256'][:16],d.get('ext4',{}).get('reused_image',''))" $P/$n.json 2>/dev/null || tail -3 $P/$n.err)"
}
tr9p() {  # strace log -> bytes through 9p (/mnt/) vs other files
  awk '{ if (match($0, /^[0-9]+ +(read|write|pread64|pwrite64|readv|writev|sendfile|copy_file_range)\(([0-9]+)<([^>]*)>/, m)) {
           r=$0; sub(/.*= /, "", r); r=r+0; if (r<0) next;
           rw=(m[1] ~ /write/)?"w":"r";
           if (m[1]=="sendfile"||m[1]=="copy_file_range") { rw="copy" }
           fs=(m[3] ~ /^\/mnt\//)?"9p":"ext4/other"; b[fs" "rw]+=r } }
       END { for (k in b) printf "  %s %.1f MB\n", k, b[k]/1048576 }' "$1"
}
cd "$HW"
R=${R:-1}
case "${1:-all}" in
orig)
  st stx4-orig-$R python3 $S/freeze.py $FT stage-scenario.py stx4-orig-$R $ARGS ;;
origtrace)
  strace -f -qq -y -s0 -e trace=read,write,pread64,pwrite64,readv,writev,sendfile,copy_file_range -o $P/orig-trace.log \
    python3 $S/freeze.py $FT stage-scenario.py stx4-origtr-$R $ARGS > $P/origtr.json 2>&1; tr9p $P/orig-trace.log; rm -f $P/orig-trace.log ;;
ext4cold)
  rm -rf /root/stage-proof
  RE4DC_STAGE_ROOT=/root/stage-proof RE4DC_STAGE_REUSE=0 RE4DC_STAGE_FREEZE_TIME=$FT st stx4-e4cold-$R python3 $T/stage_scenario.py stx4-e4cold-$R $ARGS ;;
ext4trace)
  RE4DC_STAGE_ROOT=/root/stage-proof RE4DC_STAGE_REUSE=0 RE4DC_STAGE_FREEZE_TIME=$FT strace -f -qq -y -s0 -e trace=read,write,pread64,pwrite64,readv,writev,sendfile,copy_file_range -o $P/e4-trace.log \
    python3 $T/stage_scenario.py stx4-e4tr-$R $ARGS > $P/e4tr.json 2>&1; tr9p $P/e4-trace.log; rm -f $P/e4-trace.log ;;
ext4warm)
  RE4DC_STAGE_ROOT=/root/stage-proof RE4DC_STAGE_REUSE=0 RE4DC_STAGE_FREEZE_TIME=$FT st stx4-e4warm-$R python3 $T/stage_scenario.py stx4-e4warm-$R $ARGS ;;
ext4reuse)
  RE4DC_STAGE_ROOT=/root/stage-proof st stx4-e4reuse-$R python3 $T/stage_scenario.py stx4-e4reuse-$R $ARGS ;;
esac
