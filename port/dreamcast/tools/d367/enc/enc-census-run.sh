#!/bin/bash
# enc-census-run.sh <name> <label> <fixture> [seconds]  (Git Bash; lane enc, 2026-09-30)
# Dynarec (normal) Flycast run of one view to find its crowd windows: stages scenario enc-<name> with
# candidate-enc<label> (enc-build.sh, ENC_CENSUS=1) + the fixture, runs the harness's run-emulator.py, writes
# census.txt (the ENC / ENC_OA lines) next to the capture, deletes the disc (disc.sha256 kept). Names single-use.
set -u
N=$1; L=$2; FIX=$3; SECS=${4:-300}
HW="/mnt/c/Game Dev/Emulators/re4-assets-private/world-agent-20260926/continuation-20260927/playability-r11-r1"
H="/c/Game Dev/Emulators/re4-assets-private/world-agent-20260926/continuation-20260927/playability-r11-r1"
cd "$H" || exit 1
S=scenarios/enc-$N
[ ! -e "$S" ] || { echo "$S exists (names are single-use)"; exit 1; }
cat > /c/Users/lambd/AppData/Local/Temp/enc-stage-$N.sh <<EOF
cd "$HW" && mkdir -p /root/probe/lanes/enc/stage && python3 stage-scenario.py enc-$N --arm candidate-enc$L --programs programs-enc.json --overlay /mnt/c/Flycast-Evidence/re4-dreamcast/r11-media-overlay-r1/payloads --fixture $FIX > /root/probe/lanes/enc/stage/run-$N.json 2>&1; python3 -c "import json;d=json.load(open('/root/probe/lanes/enc/stage/run-$N.json'));print(d['status'],d['disc_sha256'])"
EOF
D=$(MSYS_NO_PATHCONV=1 wsl -d Ubuntu-24.04 -- bash /mnt/c/Users/lambd/AppData/Local/Temp/enc-stage-$N.sh)
rm -f /c/Users/lambd/AppData/Local/Temp/enc-stage-$N.sh
echo "stage $D"
case "$D" in STAGED_PAYLOAD_IDENTITY_PASS*) ;; *) echo "stage failed"; exit 1 ;; esac
python run-emulator.py enc-$N --seconds $SECS --period 60 > $S-run-stdout.txt 2>&1
C=$S/capture
python -c "import json;d=json.load(open('$C/run-result.json'));print(d['status'],d.get('errors'))"
grep -a '^ENC' $C/run-output.txt > $S/census.txt
echo "census lines $(grep -c '^ENC f=' $S/census.txt) halt=$(grep -ac HALT $C/run-output.txt) missing=$(grep -ac 'RE4DC MISSING' $C/run-output.txt)"
echo "$(echo $D | awk '{print $2}')  disc.bin (deleted after run)" > $S/disc.sha256
rm -f $C/disc.bin $S/disc/disc.bin
