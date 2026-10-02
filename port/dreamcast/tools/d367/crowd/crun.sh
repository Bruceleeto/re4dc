#!/bin/bash
# Lane crowd: a Flycast run of one arm (Git Bash on Windows; stages through WSL).
#   crun.sh <label> <name> [seconds]: stage scenario cw-<name> (program candidate-cw<label>, FIX), run it with the
#   harness's run-emulator.py (screenshots every PERIOD s), then delete the disc image (disc.sha256 kept).
# Evidence: <harness>/scenarios/cw-<name>/capture (run-output.txt = the game log, shots/).
set -euo pipefail
L=${1:?label}; N=${2:?name}; SECS=${3:-300}
FIX=${FIX:-tour/rel-r101-entry-pw.json}; PERIOD=${PERIOD:-20}
H="/c/Game Dev/Emulators/re4-assets-private/world-agent-20260926/continuation-20260927/playability-r11-r1"
HW="/mnt/c/Game Dev/Emulators/re4-assets-private/world-agent-20260926/continuation-20260927/playability-r11-r1"
T=/root/work/lanes/crowd/port/dreamcast/tools/d367/crowd
# An existing scenario whose disc is still staged (a run that failed before it started) is run again as is.
if [ ! -f "$H/scenarios/cw-$N/disc/disc.bin" ]; then
MSYS_NO_PATHCONV=1 wsl -d Ubuntu-24.04 -- bash -c "cd '$HW' && { [ -d programs/candidate-cw$L ] || python3 $T/cprep.py $L; } && python3 stage-scenario.py cw-$N --arm candidate-cw$L --programs programs-crowd.json --overlay /mnt/c/Flycast-Evidence/re4-dreamcast/r11-media-overlay-r1/payloads --fixture $FIX > /root/probe/lanes/crowd/stage-cw-$N.json 2>&1; python3 -c \"import json;d=json.load(open('/root/probe/lanes/crowd/stage-cw-$N.json'));print(d['status'],d['disc_sha256'])\"" | tee "$H/scenarios/cw-$N-stage.txt"
fi
cd "$H"
python run-emulator.py cw-$N --seconds $SECS --period $PERIOD > scenarios/cw-$N-run-stdout.txt 2>&1 || true
C=scenarios/cw-$N/capture
python -c "import json;d=json.load(open('$C/run-result.json'));print(d['status'],d.get('errors'))" || tail -3 scenarios/cw-$N-run-stdout.txt
D=$(awk '{print $2}' scenarios/cw-$N-stage.txt | tail -1)
echo "$D  disc.bin (deleted after run)" > scenarios/cw-$N/disc.sha256
rm -f $C/disc.bin scenarios/cw-$N/disc/disc.bin
grep -a -c '^CROWDC' $C/run-output.txt || true
