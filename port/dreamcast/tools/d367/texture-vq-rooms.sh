#!/bin/bash
# Room-effects texture VQ (D367 play build, 2026-09-29; checklist step 2b).
# With EFFECT_ROOM=7 the in-room texture working set (~6.5 MB in the r101 fight) is far over the 2.44 MB UI
# VRAM budget, so textures cycle through disc reads. This re-encodes, as full-codebook VQ (vq_native_ui.py),
# every model/room texture >= 32 KB padded 16-bit and every effect flip frame that the given run logs loaded,
# except the keys a play fixture already stages (PS2 world textures, manual/file VQ pages): those keep their
# staged, full-quality packages. The output directory is staged by the play fixtures (make-pw-fixtures.py).
#
# usage: texture-vq-rooms.sh <fixture-dir> <out-dir> <run-output.txt>...
#   env BASE_TEX  native package directory of the staging base (default: the kite7 base's tex/)
#       FX_TEX    effect package directory (default /root/probe/d367-fx-cache)
set -e
FIX=$1 OUT=$2; shift 2
HERE=$(cd "$(dirname "$0")/.." && pwd)
BASE_TEX=${BASE_TEX:-/root/probe/d367-resume-20260927/integration-01/fixtures-ig27rc1-kite7/tex}
FX_TEX=${FX_TEX:-/root/probe/d367-fx-cache}
SRC=$(mktemp -d)
trap 'rm -rf "$SRC"' EXIT
python3 - "$FIX" "$SRC" "$BASE_TEX" "$FX_TEX" <<'EOF'
import json, sys, os
from pathlib import Path
fix, src = Path(sys.argv[1]), Path(sys.argv[2])
skip = set()
for f in fix.rglob('*-pw.json'):
    for k, v in json.load(open(f))['replace'].items():
        if k.startswith('dc/tex/') and not any(x in v for x in ('texture-vq-', 'model-vq-', 'fx-vq-')):
            skip.add(Path(k).stem)
n = 0
for d in map(Path, sys.argv[3:]):
    for t in d.glob('*.re4tex'):
        if t.stem not in skip and not (src / t.name).exists():
            os.symlink(t, src / t.name); n += 1
print('vq source packages', n, 'kept as staged', len(skip))
EOF
LOGS=()
for L in "$@"; do LOGS+=(--log "$L"); done
python3 "$HERE/vq_native_ui.py" --textures "$SRC" "${LOGS[@]}" --output "$OUT" --previews "$OUT/previews" \
  --model-min-bytes 32768 | tail -1
