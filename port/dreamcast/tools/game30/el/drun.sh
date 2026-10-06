#!/bin/bash
# (Git Bash) drun.sh <name> <arm label> <fixture (WSL path)> <seconds> [period s] ["regex=name@delay" ...]
# Lane el (el-20261005; copy of the fm lane drun.sh) dynarec Flycast run of one preset: stages with el/kit/stage-el.py to
# D:\Flycast-Evidence\re4-dreamcast\_el-stage\perfdyn-<name>, evidence D:\Flycast-Evidence\re4-dreamcast\el-20261005\
# dyn-<name> from the harness template (controllers off), relative CUE, PURPOSE.txt, warp-capture.py. ALIGN=1: the
# hwmodel Flycast, interpreter, HWTRACE_ALIGN=1 (hwtrace.log MISALIGN lines). Prints the capture PID.
# After the run: dfinish.sh <name>.
set -e
N=$1; L=$2; FIX=$3; SEC=$4; PER=${5:-30}; shift 4; [ $# -gt 0 ] && shift
SK=/c/Users/lambd/.claude/skills/re4-dreamcast-testing/scripts
T=/c/Flycast-Evidence/re4-dreamcast/d367-harness-par
D=/d/Flycast-Evidence/re4-dreamcast/el-20261005/dyn-$N
# CST=1 (D: below the stage floor): run dir + staged disc both under C:\Flycast-Evidence\re4-dreamcast\_el-cstage (the
# CUE path must be relative on one drive); dfinish.sh moves the run dir to the D: evidence root after deleting the disc.
GW=/mnt/d/Flycast-Evidence/re4-dreamcast/_el-stage; CUEREL='..\..\_el-stage'
if [ "${CST:-0}" = 1 ]; then
  [ -e "$D" ] && { echo "$D exists"; exit 1; }
  D=/c/Flycast-Evidence/re4-dreamcast/_el-cstage/run/dyn-$N; GW=/mnt/c/Flycast-Evidence/re4-dreamcast/_el-cstage/stage; CUEREL='..\..\stage'
fi
O=//wsl.localhost/Ubuntu-24.04/root/probe/lanes/route/out-$L
LG=/root/probe/lanes-20261005/el/logs
[ -e "$D" ] && { echo "$D exists"; exit 1; }
HW="/mnt/c/Game Dev/Emulators/re4-assets-private/world-agent-20260926/continuation-20260927/playability-r11-r1"
SF=$(mktemp /tmp/el-stage-XXXXXX.sh)                                     # Git Bash temp file
SW=/mnt/$(cygpath -m "$SF" | sed 's#^\(.\):#\L\1#')                     # the same file from WSL
cat > $SF <<EOF
cd "$HW" && python3 /root/probe/lanes-20261005/el/kit/stage-el.py perfdyn-$N --stage-root $GW --arm candidate-route$L --programs "$HW/programs-route.json" --overlay /mnt/c/Flycast-Evidence/re4-dreamcast/r11-media-overlay-r1/payloads --fixture $FIX > $LG/stage-dyn-$N.json 2>&1; python3 -c "import json;d=json.load(open('$LG/stage-dyn-$N.json'));print(d['status'],d['disc_sha256'])" || tail -3 $LG/stage-dyn-$N.json
cp $FIX $GW/perfdyn-$N/fixture.json
cp \$(python3 -c "import json;print(json.load(open('$FIX'))['replace']['dc/warp.txt'])") $GW/perfdyn-$N/warp.txt 2>/dev/null || true
EOF
R=$(MSYS_NO_PATHCONV=1 wsl -d Ubuntu-24.04 -- bash $SW)
rm -f $SF
echo "stage $R"
case "$R" in STAGED_PAYLOAD_IDENTITY_PASS*) ;; *) echo "stage failed"; exit 1 ;; esac
G=/d/Flycast-Evidence/re4-dreamcast/_el-stage/perfdyn-$N
[ "${CST:-0}" = 1 ] && G=/c/Flycast-Evidence/re4-dreamcast/_el-cstage/stage/perfdyn-$N
mkdir -p $D
for f in flycast.exe emu.cfg boot2.ps1 read_log.py read_pcs.py capture_ui_vram.py README.txt; do cp "$T/$f" "$D/"; done
cp -r "$T/data" "$D/"
cp "$SK/warp-capture.py" $D/
printf 'FILE "%s\\perfdyn-%s\\disc\\disc.bin" BINARY\r\n  TRACK 01 MODE1/2048\r\n    INDEX 01 00:00:00\r\n' "$CUEREL" "$N" > $D/game.cue
for f in re4dc-game.elf elf.sha256 syms.txt candidate.txt stack.txt resolved-knobs.txt; do cp "$O/$f" $D/; done
cp $G/fixture.json $D/; cp $G/warp.txt $D/ 2>/dev/null || true
echo "$R" | awk '{print $2"  disc.bin (staged '"$G"', deleted after the run)"}' > $D/disc.sha256
echo "el-20261005 (lane el, exact enemy logic) run $N: arm $L, fixture $FIX, $SEC s" > $D/PURPOSE.txt
grep -q "maple_sdl_joystick_0 = -1" $D/emu.cfg || { echo "emu.cfg lacks the controllers-off block"; exit 1; }
if [ "${VSYNC:-1}" = 0 ]; then
  sed -i 's/^rend.vsync = yes/rend.vsync = no/' $D/emu.cfg
  echo "vsync off in emu.cfg (look check: frame-locked freeze)" >> $D/PURPOSE.txt
fi
if [ "${ALIGN:-0}" = 1 ]; then
  cp "/c/Game Dev/Emulators/flycast-hwmodel/build-hwtrace/flycast.exe" $D/flycast.exe
  # interpreter: drop any Dynarec.Enabled line, add "Dynarec.Enabled = no" under [config]
  sed -i -e '/^Dynarec\.Enabled = /d' -e '0,/^\[config\]/s//[config]\nDynarec.Enabled = no/' $D/emu.cfg
  grep -n Dynarec $D/emu.cfg
  export HWTRACE_DIR="$(cygpath -w $D)" HWTRACE_ALIGN=1
  echo "align variant: interpreter + HWTRACE_ALIGN=1 (hwtrace.log MISALIGN lines)" >> $D/PURPOSE.txt
fi
M='"backing:.close=closed@3"'
for m in "$@"; do M="$M \"$m\""; done
powershell.exe -NoProfile -Command "Start-Process -FilePath python -ArgumentList 'warp-capture.py $SEC $PER $M' -WorkingDirectory '$(cygpath -w $D)' -RedirectStandardOutput '$(cygpath -w $D)\capture-run.out' -RedirectStandardError '$(cygpath -w $D)\capture-run.err' -WindowStyle Hidden -PassThru | Select-Object -ExpandProperty Id"
