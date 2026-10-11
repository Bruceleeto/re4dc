#!/usr/bin/env python3
"""ps2leon pl08: pack a nine-info pl08 render mesh into pl08's own three chunks (roles 0, 1, 8 = pl08 infos 0, 1, 6)
with the recipe that made the frozen pl08 assets (native-scene/pl08: merge_pack.py's pack_coarse_actor.pack with the
pl08 source, the fastpath build_blob / verify_blob / patch_header, slim_header.py), then the ACTOR_PL08_PACK package
(tools/d367/pl08_pack.py).

  pack_pl08.py <pl08 mesh.json> <out dir> [--reproduce]

Writes <out>/native, <out>/blob, <out>/leon_pl08_full.h (all nine infos), <out>/leon_pl08_runtime.h (slim: namespace
leon_pl08, r0 / r1 / r8 arrays and chunks[3], as slim_header.py), <out>/leon_pl08_ps2.re4cp (the package) and
<out>/ps2leon_pl08_pack_identity.inc (its identity, the include PS2_LEON's ACTOR_PL08_PACK validates against), plus
report-pl08-pack.json. pack_arm.py --pl08 <out>/leon_pl08_runtime.h takes the plan constants from the slim header.

--reproduce: the mesh is the frozen pl08 4k mesh (native-scene/pl08/mesh.json); every own array, weight table and
chunk row is compared with the frozen slim header the play package was made from (a check of this pipeline).
"""
import hashlib, importlib.util, json, re, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import leon_sources as ls  # noqa: E402

NS = ls.PRIV / 'architect-review-20261003/tools/supervisor-20261003/native-scene/pl08'
SRC = NS / 'source/pl08-source.json'
FAST = ls.PROTO / 'tools/fastpath'
PL08_PACK = ls.TREE / 'port/dreamcast/tools/d367/pl08_pack.py'
OWN = ((0, 0), (1, 1), (8, 6))   # role, pl08 info


def sha(b):
    return hashlib.sha256(b).hexdigest()


def run(*cmd):
    r = subprocess.run([sys.executable, *map(str, cmd)], capture_output=True, text=True)
    if r.returncode:
        raise SystemExit('failed: %s\n%s%s' % (' '.join(map(str, cmd)), r.stdout, r.stderr))
    return r.stdout


def slim(full, note):
    """slim_header.py's transform of the full nine-info header."""
    chunks = {int(m.group(1)): m.group(0) for m in re.finditer(r'\{(\d+),\d+,\d+,\d+,\d+,\d+,i\d+_pos,i\d+_nrm,i\d+_uv,i\d+_gx,i\d+_weights\}', full)}
    out = ['// Private generated asset. Do not commit. pl08 (no-jacket Leon) own chunks for ACTOR_PL08 (%s).' % note,
           '#pragma once', '#include "leon4k_runtime.h"', 'namespace leon_pl08 {']
    for role, info in OWN:
        for k in ('pos', 'nrm', 'uv', 'gx'):
            m = re.search(r'alignas\(32\) static (?:const )?unsigned char i%d_%s\[\] = \{.*?\};' % (info, k), full, re.S)
            t = m.group(0).replace(f'i{info}_{k}[]', f'r{role}_{k}[]')
            out.append(t.replace('alignas(32) static unsigned char', 'alignas(32) static const unsigned char'))
        m = re.search(r'static const Weight i%d_weights\[\] = \{.*?\};' % info, full, re.S)
        out.append(m.group(0).replace(f'Weight i{info}_weights[]', f'leon4k::Weight r{role}_weights[]'))
    out.append('// {source_info (pl08 list position), positions, normals, palettes, triangles, stream bytes, arrays}')
    out.append('static const leon4k::Chunk chunks[3] = {')
    for role, info in OWN:
        out.append(re.sub(r'i\d+_(pos|nrm|uv|gx|weights)', lambda mm: f'r{role}_' + mm.group(1), chunks[info]) + ',')
    out += ['};', '}']
    return '\n'.join(out) + '\n'


def body(text):
    """the slim header's data (arrays, weights, chunk rows) without comments."""
    return [l for l in text.splitlines() if not l.startswith('//')]


def main():
    a = sys.argv[1:]
    reproduce = '--reproduce' in a
    a = [x for x in a if x != '--reproduce']
    mesh, out = Path(a[0]), Path(a[1]); out.mkdir(parents=True, exist_ok=True)
    spec = importlib.util.spec_from_file_location('pack_coarse_actor', str(ls.PROTO / 'tools/pack_coarse_actor.py'))
    pca = importlib.util.module_from_spec(spec); spec.loader.exec_module(pca)
    native, blob = out / 'native', out / 'blob'
    pca.pack(mesh, SRC, native, 'leon_pl08')
    print(run(FAST / 'build_blob.py', native, blob, '--report', out / 'blob-report.json'))
    print(run(FAST / 'verify_blob.py', blob, blob))
    full = out / 'leon_pl08_full.h'
    print(run(FAST / 'patch_header.py', native / 'leon_pl08_native.h', blob, full))
    text = slim(full.read_text(), 'ps2leon pack_pl08.py from %s sha256 %s' % (mesh.name, sha(mesh.read_bytes())))
    (out / 'leon_pl08_runtime.h').write_text(text, newline='\n')
    pkg, ident = out / 'leon_pl08_ps2.re4cp', out / 'ps2leon_pl08_pack_identity.inc'
    print(run(PL08_PACK, 'pack', out / 'leon_pl08_runtime.h', pkg, '--identity', ident))
    nrep = json.loads((native / 'native-report.json').read_text())
    rep = dict(mesh=str(mesh), mesh_sha256=sha(mesh.read_bytes()),
               own=[dict(role=r, info=i, **{k: c[k] for k in ('triangles', 'positions', 'normals', 'uvs', 'palettes', 'stream_bytes') if k in c})
                    for r, i in OWN for c in nrep['chunks'] if c['info'] == i],
               package=dict(bytes=pkg.stat().st_size, sha256=sha(pkg.read_bytes())),
               headers={n: sha((out / n).read_bytes()) for n in ('leon_pl08_runtime.h', 'ps2leon_pl08_pack_identity.inc', 'leon_pl08_full.h')})
    if reproduce:
        frozen = ls.PRIV / 'architect-review-20261003/tools/supervisor-20261003/native-scene/pl08/leon_pl08_runtime.h'
        ref = slim(frozen.read_text(), 'reference')
        rep['reproduce_slim_body_same'] = body(ref) == body(text)
        rep['reproduce_identity_same'] = (ls.TREE / 'port/dreamcast/game/actor_pl08_pack_identity.inc').read_text().splitlines()[1:] == ident.read_text().splitlines()[1:]
    (out / 'report-pl08-pack.json').write_text(json.dumps(rep, indent=1))
    print(json.dumps(rep, indent=1))


if __name__ == '__main__':
    main()
