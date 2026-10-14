#!/bin/bash
# f-run.sh (copy of test10s/t-run.sh, FSAA lane) <name> <label> <fixture> [seconds]  (Git Bash): test 10 (small) candidate runs (copy of crash14 cr-run.sh).
# Evidence C:\Flycast-Evidence\re4-dreamcast\fsaa-20261014\<name>; the disc is deleted (disc.sha256 kept).
# RUNNER (default run-emulator-novsync-i26.py, the 9.1 release gate runner), RE4DC_LOG_STOP_TICK passes through.
set -u
N=$1; L=$2; FIX=$3; SECS=${4:-100}
HW="/mnt/c/Game Dev/Emulators/re4-assets-private/world-agent-20260926/continuation-20260927/playability-r11-r1"
H="/c/Game Dev/Emulators/re4-assets-private/world-agent-20260926/continuation-20260927/playability-r11-r1"
SP=/c/Flycast-Evidence/re4-dreamcast/fsaa-20261014/_tools
E=/c/Flycast-Evidence/re4-dreamcast/fsaa-20261014
ST=/root/probe/lanes-20261014/fsaa/stage
cd "$H" || exit 1
S=scenarios/route-fsaa-$N
[ ! -e "$S" ] || { echo "$S exists (names are single-use)"; exit 1; }
[ ! -e "$E/$N" ] || { echo "$E/$N exists"; exit 1; }
cat > $SP/stage-$N.sh <<EOS
cd "$HW" && mkdir -p $ST && python3 stage-scenario.py route-fsaa-$N --arm candidate-route$L --programs programs-route.json --overlay /mnt/c/Flycast-Evidence/re4-dreamcast/r11-media-overlay-r1/payloads --fixture $FIX > $ST/run-$N.json 2>&1; python3 -c "import json;d=json.load(open('$ST/run-$N.json'));print(d['status'],d['disc_sha256'])" || tail -5 $ST/run-$N.json
EOS
D=$(MSYS_NO_PATHCONV=1 wsl -d Ubuntu-24.04 -u root -- bash /mnt/c/Flycast-Evidence/re4-dreamcast/fsaa-20261014/_tools/stage-$N.sh)
rm -f $SP/stage-$N.sh
echo "stage $D"
case "$D" in STAGED_PAYLOAD_IDENTITY_PASS*) ;; *) echo "stage failed"; exit 1 ;; esac
echo "${PURPOSE:-fsaa $N: arm $L, fixture $FIX, $SECS s} stop_tick=${RE4DC_LOG_STOP_TICK:-none}" > $S/PURPOSE.txt
C=$S/capture
python ${RUNNER:-run-emulator-novsync-i26.py} route-fsaa-$N --seconds $SECS --period ${PERIOD:-30} > $S-run-stdout.txt 2>&1
python -c "import json;d=json.load(open('$C/run-result.json'));print(d['status'],d.get('errors'))"
grep -a -E 'res: |quality: render|warp:|room |route movie|HALT|RE4DC MISSING|FAULT|LHPACK|LEONGC|texchk|LOG OVERRUN' $C/run-output.txt > $S/route.txt
echo "$N halt=$(grep -ac HALT $C/run-output.txt) missing=$(grep -ac 'RE4DC MISSING' $C/run-output.txt) fault=$(grep -ac FAULT $C/run-output.txt) leongc=$(grep -ac '^LEONGC f=' $C/run-output.txt) overrun=$(grep -ac 'LOG OVERRUN' $C/run-output.txt)"
echo "$(echo $D | awk '{print $2}')  disc.bin (deleted after run)" > $S/disc.sha256
rm -f $C/disc.bin $S/disc/disc.bin
mkdir -p $E; mv $S $E/$N && mv $S-run-stdout.txt $E/$N/run-stdout.txt && echo "moved to $E/$N"
