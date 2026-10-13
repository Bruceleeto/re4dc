#!/bin/bash
# mcheck.sh <run-output.txt>... : the test 9 console-only machine checks over one or more runs of a check build.
#   Build: the test arm's knobs + TA_HASH=2 MCHECK_PT=1 MCHECK_SAFE=1 (mcheck.mk; test builds only: the play image is
#   byte-identical without them). Stage with quality.txt speed=screen; warps st-house (r100 house / trees) and
#   st-square (r101 village, Ganados on screen), ~100 s each.
#   PT_ROOMS (default 100,101): rooms that must show punch-through headers across the logs given.
#   SAFE_MARGIN (default 0): overscan pixels lost on each side.
# Prints PT-BLEND PASS/FAIL and SPEED-SAFE PASS/FAIL and exits non-zero if either fails.
set -u
D=$(cd "$(dirname "$0")" && pwd)
[ $# -ge 1 ] || { echo "usage: mcheck.sh <run-output.txt>..." >&2; exit 2; }
ALL=$(mktemp); trap 'rm -f $ALL' EXIT
cat "$@" > $ALL
python3 $D/pt_check.py $ALL --rooms ${PT_ROOMS:-100,101}; a=$?
python3 $D/safe_check.py $ALL --margin ${SAFE_MARGIN:-0}; b=$?
[ $a = 0 ] && [ $b = 0 ] && { echo "MCHECK PASS"; exit 0; }
echo "MCHECK FAIL (pt=$a safe=$b)"; exit 1
