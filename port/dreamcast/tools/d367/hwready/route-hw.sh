#!/bin/bash
# route-hw.sh <align|ta> <name> <label> <fixture> [seconds]   (Git Bash; hardware readiness, 2026-10-02)
# route-run.sh with the hwmodel Flycast (port/dreamcast/tools/hwmodel/flycast: hwtrace.patch + hwready.patch,
# built at $HW_FLYCAST, default C:\Game Dev\Emulators\flycast-hwmodel\build-hwtrace\flycast.exe):
#   align - interpreter (Dynarec.Enabled = no) + HWTRACE_ALIGN=1: every guest PC that makes a misaligned
#           16/32/64-bit access is logged once to capture/hwtrace.log ("MISALIGN pc=..."). Flycast performs
#           those accesses; a Dreamcast's SH-4 raises an address error. A new room or data format must log 0.
#           About 6 game fps: 900 s of wall time reaches ~frame 12000. Fixture input timed in wall ms lands on
#           other ticks than in a dynarec run, so compare game state against dynarec runs only.
#   ta    - dynarec + RE4DC_TA_STATS: TA input bytes per rendered scene to capture/ta-stats.txt ("TA peak"),
#           against the 2 MB vertex buffer (TA_VERTBUF_KB=2048; the PVR stores ~3/4 of the input).
# PERIOD=<s> (5..90) as route-run.sh. Needs C: free >= image + 16.25 GiB (stage-scenario floor): one at a time.
set -u
MODE=$1; shift
D="$(cd "$(dirname "$0")" && pwd)"
T=$(mktemp -d)
python "$D/mk-run-variant.py" "$MODE" "$T/run-variant.py" || exit 1
sed "s#python run-emulator.py#python '$T/run-variant.py'#" "$D/../route/route-run.sh" > "$T/route-run-variant.sh"
grep -q run-variant.py "$T/route-run-variant.sh" || { echo "route-run.sh changed: no run-emulator.py call"; exit 1; }
bash "$T/route-run-variant.sh" "$@"
rc=$?
rm -rf "$T"
exit $rc
