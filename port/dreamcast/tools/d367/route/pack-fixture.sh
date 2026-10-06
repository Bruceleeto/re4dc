#!/bin/bash
# pack-fixture.sh [--replace] <fixture> <arm> <out fixture>  (TEX_PACK, 2026-10-03; paths relative to the playability
# harness)
# Stages <fixture> with <arm> once, packs the staged disc's dc/tex packages (texpack.py) and writes <out fixture>:
# <fixture>'s replacements minus its dc/tex/ entries, plus dc/tex.pak, removing every base dc/tex/ package except the
# media overlay's (stage-scenario.py writes those itself; they stay loose and are also in the pack). The arm only
# picks the staging program: the pack holds disc data, not code. Re-run whenever the fixture or the base disc's
# textures change. A fixture staging the r100 PS2 world also gets dc/native/r100/interior.cell (PS2_INTERIOR_CULL).
# Ownership (architect review 2026-10-03): the run stages in its own scenarios/packstage-<name>-<pid>-<time> (the
# path is checked before it is removed); an existing <out fixture> is refused unless --replace; the pack is written
# once as the immutable texpack-20261003/<name>.<sha16>.pak, validated (texpack.py --verify), with
# <pak>.manifest.json beside it (input fixture, base manifest, media overlay and pack hashes, also in the fixture's
# "provenance"); <out fixture> is published last with one rename. A failed run leaves the previous fixture and the
# pack it names usable.
set -euo pipefail
REPLACE=0
if [ "${1:-}" = --replace ]; then REPLACE=1; shift; fi
[ $# = 3 ] || { sed -n '2,15p' "$0"; exit 2; }
FIX=$1; ARM=$2; OUTFIX=$3
H="/mnt/c/Game Dev/Emulators/re4-assets-private/world-agent-20260926/continuation-20260927/playability-r11-r1"
BASE=/root/probe/d367-resume-20260927/integration-01/disc-ig27rc1-kite7/payload-manifest.json
OVERLAY=/mnt/c/Flycast-Evidence/re4-dreamcast/r11-media-overlay-r1/payloads
TOOLS=$(cd "$(dirname "$0")/.." && pwd)
cd "$H"
[ -f "$FIX" ] || { echo "pack-fixture: no fixture $FIX" >&2; exit 1; }
if [ -e "$OUTFIX" ] && [ "$REPLACE" = 0 ]; then
  echo "pack-fixture: $OUTFIX exists; pass --replace to replace it" >&2; exit 1
fi
NAME=$(basename "$OUTFIX" .json)
case "$NAME" in ''|*[!A-Za-z0-9._-]*) echo "pack-fixture: bad output name '$NAME'" >&2; exit 1 ;; esac
N=packstage-$NAME-$$-$(date +%Y%m%d%H%M%S)
S="$H/scenarios/$N"
[ ! -e "$S" ] || { echo "pack-fixture: $S exists" >&2; exit 1; }
PD="$H/../texpack-20261003"
mkdir -p "$PD"
TMP="$PD/.tmp-$NAME-$$.pak"
OUTTMP="$OUTFIX.tmp-$$"
cleanup() {
  # only this run's own staging directory and temporary files
  case "$S" in "$H/scenarios/packstage-$NAME-$$-"[0-9]*) [ ! -d "$S" ] || rm -rf -- "$S" ;; esac
  rm -f -- "$TMP" "$OUTTMP"
}
trap cleanup EXIT
python3 stage-scenario.py "$N" --arm "$ARM" --programs programs-route.json --overlay "$OVERLAY" --fixture "$FIX" \
  > "/root/probe/stage-$N.json" 2>&1 || { tail -5 "/root/probe/stage-$N.json"; exit 1; }
python3 "$TOOLS/texpack.py" "$S/disc/disc.bin" "$TMP"
python3 "$TOOLS/texpack.py" --verify "$TMP"
SHA=$(sha256sum "$TMP" | cut -c1-64)
PK="$PD/$NAME.${SHA:0:16}.pak"
if [ -e "$PK" ]; then
  cmp -s "$TMP" "$PK" || { echo "pack-fixture: $PK exists with other bytes" >&2; exit 1; }
  rm -f -- "$TMP"
else
  mv -- "$TMP" "$PK"
fi
python3 - "$FIX" "$OUTTMP" "$PK" "$BASE" "$OVERLAY" "$ARM" "$TOOLS/texpack.py" "$OUTFIX" <<'PY'
import hashlib, json, os, sys, time
fix, out, pk, base_path, overlay, arm, tool, final = sys.argv[1:9]
sha = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()
d = json.load(open(fix))
base = json.load(open(base_path))
fdir = os.path.dirname(os.path.abspath(fix)); odir = os.path.dirname(os.path.abspath(final))
# replacement sources are relative to the fixture's own directory
rep = {k: os.path.relpath(os.path.join(fdir, v), odir) for k, v in d['replace'].items() if not k.startswith('dc/tex/')}
rep['dc/tex.pak'] = os.path.relpath(pk, odir)
# PS2_INTERIOR_CULL's cell travels with the r100 PS2 world (ps2world/interior/add_cell.py; harmless with the knob off)
cell = os.path.join(os.path.dirname(os.path.abspath(tool)), 'ps2world', 'interior', 'interior-r100.cell')
if 'dc/native/r100/ps2-world.re4mesh' in rep and 'dc/native/r100/interior.cell' not in rep:
    rep['dc/native/r100/interior.cell'] = os.path.relpath(cell, odir)
media_json = os.path.abspath('../integration-source-r11/MEDIA.json')
media = {e['eventual_disc_destination'] for e in json.load(open(media_json))['assets']}
rem = list(d.get('remove', []))
rem += sorted(k for k in base if k.startswith('dc/tex/') and k not in rem and k not in media)
prov = dict(tool='tools/d367/route/pack-fixture.sh', created=time.strftime('%Y-%m-%dT%H:%M:%S'), arm=arm,
            input_fixture=dict(path=os.path.abspath(fix), sha256=sha(fix)),
            base_manifest=dict(path=base_path, sha256=sha(base_path)),
            media_overlay=dict(payloads=overlay, media_json=media_json, sha256=sha(media_json)),
            pack=dict(path=os.path.abspath(pk), sha256=sha(pk), bytes=os.path.getsize(pk)),
            texpack_py_sha256=sha(tool))
mf = pk + '.manifest.json'
if not os.path.exists(mf):   # immutable beside its pack: the first fixture made from it
    json.dump(prov, open(mf + '.tmp', 'w'), indent=1); os.replace(mf + '.tmp', mf)
json.dump({'replace': rep, 'remove': rem, 'provenance': prov}, open(out, 'w'), indent=1)
print(final, 'replace', len(rep), 'remove', len(rem), 'pack', os.path.basename(pk))
PY
mv -f -- "$OUTTMP" "$OUTFIX"
echo "pack-fixture: published $OUTFIX -> $(basename "$PK")"
