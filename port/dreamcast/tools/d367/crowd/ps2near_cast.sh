#!/bin/bash
# Lane crowd: a cast dir (symlink farm) = the external cast (cast-20260925 + the revision-20260926 overlay) with
# ganado-em15-00 taken from the ps2cast lane's PS2 conversion (ps2cast-20260930/cast/ganado-em15-00, revision ps2-v1).
# Feed it to cast_bundle.py (LEVEL=conservative REVISION=revision-20260926) for the "PS2 em15-00 near" bundle: the other
# four appearances are byte-identical to the play bundle's (checked by diffing their arrays afterwards).
#   ps2near_cast.sh <out dir>
set -euo pipefail
OUT=${1:?out dir}
C="/mnt/c/Game Dev/Emulators/re4-assets-private/cast-20260925"
P="/mnt/c/Game Dev/Emulators/re4-assets-private/ps2cast-20260930/cast"
[ -e "$OUT" ] && { echo "$OUT exists"; exit 1; }
mkdir -p "$OUT/source" "$OUT/revision-20260926/integration-bundle"
for e in "$C"/*; do
  n=$(basename "$e")
  case $n in ganado-em15-00|source|revision-20260926) ;; *) ln -s "$e" "$OUT/$n" ;; esac
done
ln -s "$P/ganado-em15-00" "$OUT/ganado-em15-00"
for e in "$C"/source/*; do [ "$(basename "$e")" = candidate-revisions.json ] || ln -s "$e" "$OUT/source/"; done
for e in "$C"/revision-20260926/*; do [ "$(basename "$e")" = integration-bundle ] || ln -s "$e" "$OUT/revision-20260926/"; done
for e in "$C"/revision-20260926/integration-bundle/*; do [ "$(basename "$e")" = catalog.json ] || ln -s "$e" "$OUT/revision-20260926/integration-bundle/"; done
python3 - "$C" "$P" "$OUT" <<'PY'
import json, sys
c, p, out = sys.argv[1:]
rev = json.load(open(f'{c}/source/candidate-revisions.json'))
rev['ganado-em15-00'] = json.load(open(f'{p}/source/candidate-revisions.json'))['ganado-em15-00']
json.dump(rev, open(f'{out}/source/candidate-revisions.json', 'w'), indent=1)
cat = [e for e in json.load(open(f'{c}/revision-20260926/integration-bundle/catalog.json')) if e['name'] != 'ganado-em15-00']
json.dump(cat, open(f'{out}/revision-20260926/integration-bundle/catalog.json', 'w'), indent=1)
print('ps2near cast dir', out, 'catalog', len(cat), 'em15-00', rev['ganado-em15-00'])
PY
