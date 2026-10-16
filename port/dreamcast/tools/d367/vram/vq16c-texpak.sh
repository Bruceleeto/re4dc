#!/bin/bash
# vq16c-texpak.sh <fixture.json> <keys.txt> <out dir> (WSL; lane resident16 2026-10-16): the chapter 1 VQ tex.pak.
#   The 16-bit packages named in keys.txt (vram/vq16-ch1.txt), taken from the fixture's disc (its dc/tex.pak, or the
#   loose dc/tex/<c>/<key>.re4tex it stages: tex.pak is looked up before the loose file, so their VQ packages go into
#   the pak), re-encoded as full-codebook VQ with vram/vq_pak.py (the tool and method of the user-approved r101 world
#   set vq16-r101.txt, Leon's atlas and the castle set vq16-c31.txt) and merged into the fixture's tex.pak
#   (tex_merge.py). Output: <out>/tex-vq16c.pak + <out>/vq16c (previews, vq-report.json for vq_sheet.py).
set -euo pipefail
FIX=${1:?fixture}; KEYS=${2:?keys}; OUT=${3:?out}
D=$(cd "$(dirname "$0")/.." && pwd)
mkdir -p $OUT; rm -rf $OUT/src16 $OUT/vq16c; mkdir -p $OUT/src16
BASE=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['replace']['dc/tex.pak'])" $FIX)
python3 - $FIX $BASE $OUT/src16 $(grep -v '^#' $KEYS | awk '{print $1}') <<'EOF'
import json, struct, sys, shutil
from pathlib import Path
fix, base, out, keys = json.load(open(sys.argv[1])), Path(sys.argv[2]).read_bytes(), Path(sys.argv[3]), sys.argv[4:]
magic, ver, count, ioff, doff = struct.unpack_from('<8s4I', base, 0)
idx = {}
for i in range(count):
    c, f, o, n = struct.unpack_from('<4I', base, ioff + 16 * i)
    idx['%08x-%08x' % (c, f)] = (o, n)
for k in keys:
    if k in idx:
        o, n = idx[k]; (out / (k + '.re4tex')).write_bytes(base[o:o + n]); print(k, 'pak')
    else:
        src = fix['replace']['dc/tex/%s/%s.re4tex' % (k[0], k)]
        shutil.copy(src, out / (k + '.re4tex')); print(k, 'loose', src)
EOF
python3 $D/texpack.py $OUT/src16 $OUT/tex-src16.pak
python3 $D/vram/vq_pak.py $OUT/tex-src16.pak $OUT/tex-vq.pak $OUT/vq16c $(grep -v '^#' $KEYS | awk '{print $1}')
python3 $D/tex_merge.py $BASE $OUT/tex-vq16c.pak $OUT/tex-vq.pak
rm -rf $OUT/src16 $OUT/tex-src16.pak $OUT/tex-vq.pak
python3 $D/texpack.py --verify $OUT/tex-vq16c.pak
sha256sum $BASE $OUT/tex-vq16c.pak
