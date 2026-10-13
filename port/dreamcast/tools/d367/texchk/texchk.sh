#!/bin/bash
# texchk.sh <run-output.txt>... : texture presence PASS/FAIL gate (lane texchk, issue #26; texchk.py has the rules).
# The run must come from a TEX_CHECK=1 or 2 build (game/Makefile, test only). Route coverage: r100 house (h2 warp +
# tour padscript), r101 square (st-square), r103 (st-r103). Exit 0 only when every log passes.
set -u
exec python3 "$(dirname "$0")/texchk.py" "$@"
