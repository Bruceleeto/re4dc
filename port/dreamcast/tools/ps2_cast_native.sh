#!/bin/bash
# ps2_cast.py stage 2 (WSL): the converted appearance's native arrays -> the runtime header and texture package.
#   1. host check: the cast agent's test_cast_dynamic.cpp against THIS tree's native_actor_fast.cpp (the
#      unchanged runtime converter; writes native/info<i>.meshlets, the reference blobs);
#   2. fastpath build_blob.py (meshlets + strips, --look 8 as the cast's fit_and_check.py), verify_blob.py
#      (exact triangle multiset + layout), patch_header.py -> runtime/castmodel_runtime.h;
#   3. atlas.png -> pvrtex VQ (RGB565) -> vq_export.py --pack-existing -> texture/<key>.re4tex.
# usage: ps2_cast_native.sh <appearance out dir (WSL path)>
set -euo pipefail
O=$(realpath "$1")
T=$(cd "$(dirname "$0")/../../.." && pwd)                 # this repo tree
PRIV=${RE4_PRIVATE:-/mnt/c/Game Dev/Emulators/re4-assets-private}
F="$PRIV/character-prototype-20260925/tools/fastpath"
CT="$PRIV/cast-20260925/tools"
H=${PS2CAST_HOSTCHECK:-/root/probe/lanes/ps2cast/host-check}
PVRTEX=${PVRTEX:-/root/work/kos-re4dc-d336/utils/pvrtex/pvrtex}
N="$O/native"
mkdir -p "$H/host/dc"
[ -f "$H/host/dc/pvr.h" ] || cp /root/probe/d367-agents/actors30/test/host/dc/pvr.h "$H/host/dc/pvr.h"
# the check binary is rebuilt whenever the runtime sources or the test change (stamp = their sha256)
STAMP=$(cat "$T/port/dreamcast/game/platform/native_actor_fast.cpp" "$T/port/dreamcast/room/pvr_geometry.cpp" \
        "$T/port/dreamcast/room/source_lighting.cpp" "$CT/test_cast_dynamic.cpp" | sha256sum | cut -c1-16)
if [ ! -x "$H/check-$STAMP" ]; then
  FLAGS=(-O1 -g -std=gnu++20 -DRE4DC_ACTOR_TEST -DRE4DC_D349_RENDERER_STACK=1 -DRE4DC_NATIVE_ACTOR_SKIN=1
         -DRE4DC_NATIVE_ACTOR_SKIN_LAZY=1 -DRE4DC_ACTOR_LOD_BUDGET=0 -I"$H/host" -I"$T/port/dreamcast/game/platform/include"
         -I"$T/port/dreamcast/room")
  objs=()
  for s in game/platform/native_actor_fast.cpp room/pvr_geometry.cpp room/source_lighting.cpp; do
    g++ "${FLAGS[@]}" -c "$T/port/dreamcast/$s" -o "$H/$(basename "$s")-$STAMP.o"; objs+=("$H/$(basename "$s")-$STAMP.o")
  done
  g++ "${FLAGS[@]}" "$CT/test_cast_dynamic.cpp" "${objs[@]}" -o "$H/check-$STAMP"
fi
echo "host check $H/check-$STAMP (tree $(git -C "$T" rev-parse --short HEAD))"
"$H/check-$STAMP" "$N" > "$N/host-check.txt"
cat "$N/host-check.txt"
rm -rf "$O/fitted" "$O/runtime"; mkdir -p "$O/fitted" "$O/runtime"
python3 "$F/build_blob.py" "$N" "$O/fitted" --report "$O/fit-report.json" --look 8 > "$O/fit.log"
python3 "$F/verify_blob.py" "$N" "$O/fitted" > "$O/verify.log"; cat "$O/verify.log"
python3 "$F/patch_header.py" "$N/castmodel_native.h" "$O/fitted" "$O/runtime/castmodel_runtime.h" > "$O/header.log"; cat "$O/header.log"
# texture
KEY=$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['texture']['key'])" "$O/validation.json")
rm -rf "$O/texture"; mkdir -p "$O/texture"
"$PVRTEX" -i "$O/atlas.png" -o "$O/texture/atlas.dt" -f RGB565 -c -p "$O/texture/vq-preview.png" > "$O/texture/compress.log"
python3 "$T/port/dreamcast/tools/vq_export.py" --pack-existing "$O/texture/atlas.dt" --package "$O/texture/$KEY.re4tex" \
  --material "ps2cast_$(basename "$O" | tr '-' '_')" > "$O/texture/package.log"
python3 - "$O" "$KEY" <<'PY'
import hashlib, json, struct, sys
from pathlib import Path
o, key = Path(sys.argv[1]), sys.argv[2]
p = o / 'texture' / (key + '.re4tex')
b = p.read_bytes()
# RE4DCTX header (g_re4tex.py): first texture record -> width, height, payload bytes
magic, ver, hsize, tsize, count, toff, doff, dlen, crc, nimg, _ = struct.unpack_from('<8s10I', b, 0)
name, w, h, fmt, off, size, flags, payload, _ = struct.unpack_from('<64s8I', b, toff)
r = dict(key=key, width=w, height=h, format='VQ RGB565' if payload == 2 else fmt, vram_bytes=size,
         package=str(p), package_sha256=hashlib.sha256(b).hexdigest(), package_bytes=len(b))
(o / 'texture' / 'package.json').write_text(json.dumps(r, indent=1))
print('texture', json.dumps(r))
PY
