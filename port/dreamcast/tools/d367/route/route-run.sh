#!/bin/bash
# route-run.sh <name> <label> <fixture> [seconds]  (Git Bash; lane route, 2026-10-01; lane enc's enc-census-run.sh)
# Dynarec Flycast run of one route view: stages scenario route-<name> with candidate-route<label> (route-build.sh)
# + the fixture (make-route-fixtures.py), runs the harness's run-emulator.py, writes route.txt (warp, room, movie,
# heap, HALT and MISSING lines) next to the capture, deletes the disc (disc.sha256 kept). Names are single-use.
set -u
N=$1; L=$2; FIX=$3; SECS=${4:-180}
HW="/mnt/c/Game Dev/Emulators/re4-assets-private/world-agent-20260926/continuation-20260927/playability-r11-r1"
H="/c/Game Dev/Emulators/re4-assets-private/world-agent-20260926/continuation-20260927/playability-r11-r1"
cd "$H" || exit 1
S=scenarios/route-$N
[ ! -e "$S" ] || { echo "$S exists (names are single-use)"; exit 1; }
cat > /c/Users/lambd/AppData/Local/Temp/route-stage-$N.sh <<EOF
cd "$HW" && mkdir -p /root/probe/lanes/route/stage && python3 stage-scenario.py route-$N --arm candidate-route$L --programs programs-route.json --overlay /mnt/c/Flycast-Evidence/re4-dreamcast/r11-media-overlay-r1/payloads --fixture $FIX > /root/probe/lanes/route/stage/run-$N.json 2>&1; python3 -c "import json;d=json.load(open('/root/probe/lanes/route/stage/run-$N.json'));print(d['status'],d['disc_sha256'])" || tail -5 /root/probe/lanes/route/stage/run-$N.json
EOF
D=$(MSYS_NO_PATHCONV=1 wsl -d Ubuntu-24.04 -- bash /mnt/c/Users/lambd/AppData/Local/Temp/route-stage-$N.sh)
rm -f /c/Users/lambd/AppData/Local/Temp/route-stage-$N.sh
echo "stage $D"
case "$D" in STAGED_PAYLOAD_IDENTITY_PASS*) ;; *) echo "stage failed"; exit 1 ;; esac
python run-emulator.py route-$N --seconds $SECS --period 60 > $S-run-stdout.txt 2>&1
C=$S/capture
python -c "import json;d=json.load(open('$C/run-result.json'));print(d['status'],d.get('errors'))"
grep -a -E 'warp:|route movie|room |heap4|heap 4|HALT|RE4DC MISSING|no-std|PS2MESH|native mesh|exec error|chapter' $C/run-output.txt > $S/route.txt
echo "route lines $(wc -l < $S/route.txt) halt=$(grep -ac HALT $C/run-output.txt) missing=$(grep -ac 'RE4DC MISSING' $C/run-output.txt)"
echo "$(echo $D | awk '{print $2}')  disc.bin (deleted after run)" > $S/disc.sha256
rm -f $C/disc.bin $S/disc/disc.bin
