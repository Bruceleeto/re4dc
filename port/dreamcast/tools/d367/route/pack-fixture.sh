#!/bin/bash
# pack-fixture.sh <fixture> <arm> <out fixture>  (TEX_PACK, 2026-10-03; paths relative to the playability harness)
# Stages <fixture> with <arm> once, packs the staged disc's dc/tex packages (texpack.py) into
# texpack-20261003/<out name>.pak beside the harness, and writes <out fixture>: <fixture>'s replacements minus its
# dc/tex/ entries, plus dc/tex.pak, removing every base dc/tex/ package except the media overlay's (stage-scenario.py
# writes those itself; they stay loose and are also in the pack). The arm only picks the staging program: the pack
# holds disc data, not code. Re-run whenever the fixture or the base disc's textures change.
set -euo pipefail
FIX=$1; ARM=$2; OUTFIX=$3
H="/mnt/c/Game Dev/Emulators/re4-assets-private/world-agent-20260926/continuation-20260927/playability-r11-r1"
BASE=/root/probe/d367-resume-20260927/integration-01/disc-ig27rc1-kite7/payload-manifest.json
TOOLS=$(cd "$(dirname "$0")/.." && pwd)
cd "$H"
N=packstage-$(basename "$OUTFIX" .json)
rm -rf "scenarios/$N"
python3 stage-scenario.py "$N" --arm "$ARM" --programs programs-route.json \
  --overlay /mnt/c/Flycast-Evidence/re4-dreamcast/r11-media-overlay-r1/payloads --fixture "$FIX" \
  > "/root/probe/stage-$N.json" 2>&1 || { tail -5 "/root/probe/stage-$N.json"; exit 1; }
mkdir -p "$H/../texpack-20261003"
PK="$H/../texpack-20261003/$(basename "$OUTFIX" .json).pak"
python3 "$TOOLS/texpack.py" "scenarios/$N/disc/disc.bin" "$PK"
rm -rf "scenarios/$N"
python3 - "$FIX" "$OUTFIX" "$PK" "$BASE" <<'PY'
import json, os, sys
fix, out, pk, base_path = sys.argv[1:5]
d = json.load(open(fix))
base = json.load(open(base_path))
fdir = os.path.dirname(os.path.abspath(fix)); odir = os.path.dirname(os.path.abspath(out))
# replacement sources are relative to the fixture's own directory
rep = {k: os.path.relpath(os.path.join(fdir, v), odir) for k, v in d['replace'].items() if not k.startswith('dc/tex/')}
rep['dc/tex.pak'] = os.path.relpath(pk, odir)
media = {e['eventual_disc_destination'] for e in json.load(open('../integration-source-r11/MEDIA.json'))['assets']}
rem = list(d.get('remove', []))
rem += sorted(k for k in base if k.startswith('dc/tex/') and k not in rem and k not in media)
json.dump({'replace': rep, 'remove': rem}, open(out, 'w'), indent=1)
print(out, 'replace', len(rep), 'remove', len(rem))
PY
