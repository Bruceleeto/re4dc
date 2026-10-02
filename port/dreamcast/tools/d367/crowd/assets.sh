#!/bin/bash
# Lane crowd: the asset dirs (cbuild.sh ASSETS=...) and fixtures of the crowd tier arms. Private outputs stay on ext4
# under /root/probe/lanes/crowd (and the private store crowd-<date>), never in the repo.
#   assets-far     play bundle + ganado_far_runtime.h (far tier = external cast v4-fit lean, bundle-lean)
#   assets-ps2     play bundle with ganado_cast_runtime.h from bundle-ps2near (em15-00 = PS2 ps2-v1, rest unchanged)
#   assets-ps2far  assets-ps2 + ganado_far_runtime.h
#   fix/*-ps2.json the benchmark fixtures + the PS2 em15-00 atlas (dc/tex/e/ebed7ba6-2ca7490f.re4tex, an addition)
# Inputs: bundle-lean, bundle-ps2near (cast_bundle.py; ps2near_cast.sh for the latter's cast dir).
set -euo pipefail
EV=/root/probe/lanes/crowd
T=$(cd "$(dirname "$0")" && pwd)
H="/mnt/c/Game Dev/Emulators/re4-assets-private/world-agent-20260926/continuation-20260927/playability-r11-r1"
PLAY=$EV/assets-play-actor-bundle-20260928
mk() {  # mk <dir> <near header> <far header or ->
  local D=$1
  rm -rf "$D"; mkdir -p "$D"; cp "$PLAY"/* "$D"/
  cp "$2" "$D/ganado_cast_runtime.h"
  [ "$3" = - ] || python3 "$T/far_header.py" "$3" "$D/ganado_far_runtime.h"
  (cd "$D" && rm -f SHA256SUMS && sha256sum * > ../SHA256SUMS.$$ && mv ../SHA256SUMS.$$ SHA256SUMS)
  echo "$D: $(wc -l < "$D/SHA256SUMS") files"
}
mk $EV/assets-far $PLAY/ganado_cast_runtime.h $EV/bundle-lean/ganado_cast_runtime.h
mk $EV/assets-ps2 $EV/bundle-ps2near/ganado_cast_runtime.h -
mk $EV/assets-ps2far $EV/bundle-ps2near/ganado_cast_runtime.h $EV/bundle-lean/ganado_cast_runtime.h
mkdir -p $EV/fix
for f in tour/rel-r101-entry-pw.json tour/rel-r100-s20-pw.json tour/enc-rel-r101-bell-fight-pw.json kite-mesh-fixture-r21.json; do
  python3 - "$H/$f" "$EV/fix/$(basename "$f" .json)-ps2.json" "$EV/bundle-ps2near/tex/ebed7ba6-2ca7490f.re4tex" <<'PY'
import json, sys
from pathlib import Path
src, out, tex = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
d = json.loads(src.read_text())
d['replace'] = {k: str((src.parent / v).resolve()) for k, v in d['replace'].items()}  # absolute: the copy moves
k = 'dc/tex/e/' + tex.name
assert k not in d['replace']
d['replace'][k] = str(tex)
out.write_text(json.dumps(d, indent=1) + '\n')
print(out, len(d['replace']))
PY
done
