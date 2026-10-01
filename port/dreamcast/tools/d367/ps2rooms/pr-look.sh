#!/bin/bash
# pr-look.sh <name> <arm> <programs.json> <fixture (WSL path)> [seconds] [period]   (Git Bash; lane ps2rooms)
# In-game look frames of one view with a given world package (enc-census-run.sh's method): stages the playability
# harness scenario ps2rooms-<name>, runs run-emulator.py (dynarec Flycast, framebuffer shots every <period> s),
# prints HALT / MISSING / PS2MESH, deletes the disc (disc.sha256 kept). Names are single-use.
set -u
N=$1; ARM=$2; PROG=$3; FIX=$4; SECS=${5:-150}; PER=${6:-10}
HW="/mnt/c/Game Dev/Emulators/re4-assets-private/world-agent-20260926/continuation-20260927/playability-r11-r1"
H="/c/Game Dev/Emulators/re4-assets-private/world-agent-20260926/continuation-20260927/playability-r11-r1"
cd "$H" || exit 1
S=scenarios/ps2rooms-$N
[ ! -e "$S" ] || { echo "$S exists (names are single-use)"; exit 1; }
T=/c/Users/lambd/AppData/Local/Temp/ps2rooms-stage-$N.sh
cat > $T <<EOF
cd "$HW" && mkdir -p /root/probe/lanes/ps2rooms/stage && python3 stage-scenario.py ps2rooms-$N --arm $ARM --programs $PROG --overlay /mnt/c/Flycast-Evidence/re4-dreamcast/r11-media-overlay-r1/payloads --fixture $FIX > /root/probe/lanes/ps2rooms/stage/look-$N.json 2>&1; python3 -c "import json;d=json.load(open('/root/probe/lanes/ps2rooms/stage/look-$N.json'));print(d['status'],d['disc_sha256'])"
EOF
D=$(MSYS_NO_PATHCONV=1 wsl -d Ubuntu-24.04 -- bash /mnt/c/Users/lambd/AppData/Local/Temp/ps2rooms-stage-$N.sh)
rm -f $T
echo "stage $D"
case "$D" in STAGED_PAYLOAD_IDENTITY_PASS*) ;; *) echo "stage failed"; exit 1 ;; esac
python run-emulator.py ps2rooms-$N --seconds $SECS --period $PER > $S-run-stdout.txt 2>&1
C=$S/capture
python -c "import json;d=json.load(open('$C/run-result.json'));print(d['status'],d.get('errors'))"
echo "halt=$(grep -ac HALT $C/run-output.txt) missing=$(grep -ac 'RE4DC MISSING' $C/run-output.txt) ps2mesh=$(grep -ac PS2MESH $C/run-output.txt) openfail=$(grep -ac 'open failed' $C/run-output.txt)"
echo "$(echo $D | awk '{print $2}')  disc.bin (deleted after run)" > $S/disc.sha256
rm -f $C/disc.bin $S/disc/disc.bin
ls $C | grep -i -E 'png|bmp' | head -40
