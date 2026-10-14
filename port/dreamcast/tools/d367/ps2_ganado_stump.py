#!/usr/bin/env python3
"""Export the reviewed exact BIN479 PS2 head into a private app2 asset header.

First run ps2_cast.py convert ganado-em13-03-stump and ps2_cast_native.sh.
The approved native header hash seals all 90 oriented triangles, weights and
atlas UVs checked by that pipeline. This exporter never writes a game texture:
the normal app2 atlas must contain the same descriptor and encoded texels.
"""
import argparse
import json
from pathlib import Path
import re

import model_registry as mr

PINS = {
    'em13.drs': '7e2266f4c404264f97bd29c07225d6e069d828c3728a2001570b314e6cce132d',
    'em13.dat': 'd2f71183ae1921fddec626b5e72b5c40df937aa30bd3e0508c528fc3aa4aa6ed',
    'em15.drs': 'b6a4cfbe7d517728de72cb1081b833af2911e59967a4fecbd84013be09730874',
    'em15.dat': '4dcfa55f6825b91949fe67a59d04d02678e44b24c42e9a50017c2d58be265415',
}
RUNTIME_SHA = 'abcc46030280e07ec6c372e2e17863dddeed24aa82e2ebc1319f2e00bc474388'
GC_SHA = '9876c71e4c4480aa05dcb92f79462a880d7916661a80a69ac2a8943e7415e8ff'
CAST_SHA = 'aa47772e4366f54d4ace27f8be4613c99f7d3f7b4f3561e00c2c48f6649e0bb4'


def require(ok, message):
    if not ok:
        raise mr.Fail(message)


def generate(inputs, converted, cast_header, normal_atlas, out):
    tree = Path(__file__).resolve().parents[4]
    for name, expected in PINS.items():
        require(mr.sha((inputs / name).read_bytes()) == expected, f'{name}: source pin mismatch')
    archive, parse_tpl, le_mirror = mr.archive_facts(str(tree))
    facts = []
    for name in ('em13', 'em15'):
        arc = archive.Archive(str(inputs / (name + '.drs')))
        f = mr.bin_facts(arc, le_mirror, name, 479)
        require(f['sha256'] == GC_SHA and f['normalized'] == [2976, 1450011754, 3920562518],
                f'{name}: source identity differs from the reviewed material row')
        tpl = mr.tpl_facts(arc, parse_tpl, name, 477)['textures']
        require([t['key'] for t in tpl] == [[2614095805, 3625741105], [1267036948, 4074767808], [1710877097, 1483325243]]
                and all(t['whf'] == [256, 256, 14] and t['sampler'] == [1, 1, 1, 1, 0, 0, 0, 0]
                        and t['palette'] is None for t in tpl), f'{name}: source TPL477 differs')
        facts.append(f['sha256'])
    # Keep the public material certificate reproducible without writing private
    # source arrays. The normalized digest above is the load-time admission seal.
    u = lambda xs: ','.join(str(x) + 'u' for x in xs)
    part = f['parts'][0]
    expected = '\n'.join([
        '// Exact original GC em13/em15 BIN479 facts, derived by ps2_ganado_stump.py.',
        '// Mesh bytes remain private; this table only certifies the source-selected head.',
        'static const Part p_ps2_stump_479[] = {',
        '{{' + u(bytes.fromhex(part[0])) + '},' + u(part[1:]) + '},', '};',
        'static const Model m_ps2_stump_479 = {{' + u(f['header']) + '},' +
        ','.join('{' + u(f[k]) + '}' for k in ('positions', 'normals', 'weights', 'uv')) + ',p_ps2_stump_479};', ''])
    require((tree / 'port/dreamcast/game/actor_material_records_ps2_stump.inc').read_text() == expected,
            'public material facts differ from pinned archives')
    native = converted / 'runtime/castmodel_runtime.h'
    require(mr.sha(native.read_bytes()) == RUNTIME_SHA, 'native header differs from the reviewed exact conversion')
    chunks, bones = mr.parse_header(native)
    require(bones == 34 and len(chunks) == 4, 'unexpected skeleton/role layout')
    c = chunks[1]
    require(c['source_info'] == 1 and c['triangles'] == 90 and c['palette_count'] == 6,
            'not the reviewed source head')
    mr.preflight_chunk(c, bones)
    v = json.loads((converted / 'validation.json').read_text())
    require(v['sections'][1]['ps2_bin_sha256'] == 'b614f5d0b7163892fcaf95978ea70d1e9f849286a92b763e45118d76dbb16432'
            and v['sections'][1]['ps2_triangles'] == 90 and not v['winding_flipped'], 'conversion provenance differs')
    require(v['texture']['cells'] == {'0': [0, 0, 256, 256], '1': [256, 0, 256, 256], '2': [0, 256, 256, 256]}
            and v['texture']['key'] == '65c6fe5a-2593694e', 'app2 atlas remap differs')
    tex = (converted / 'texture/65c6fe5a-2593694e.re4tex').read_bytes()
    base_tex = normal_atlas.read_bytes()
    # RE4DCTX v2: bytes 48..95 are the diagnostic label, 36..39 its CRC.
    # All format, key, sampler, descriptor and encoded payload bytes must agree.
    require(len(tex) == len(base_tex) == 67728 and tex[:36] == base_tex[:36]
            and tex[40:48] == base_tex[40:48] and tex[96:] == base_tex[96:], 'normal atlas payload differs')
    require(mr.sha(cast_header.read_bytes()) == CAST_SHA, 'normal cast differs from the reviewed app2 bundle')
    gc = cast_header.read_text()
    parents = re.search(r'static const int parents\[34\] = (\{[^;]+\});', gc).group(1)
    bind = re.search(r'static const float bind\[5\]\[34\]\[12\] = \{\n(.*?)\n\};', gc, re.S).group(1).splitlines()
    require(len(bind) == 5, 'normal cast bind layout differs')
    bind2 = bind[2].rstrip(',')
    require('"ganado-em15-03"' in gc and '{0x65c6fe5au,0x2593694eu,512,512}' in gc, 'normal cast lacks app2 atlas')
    lines = ['// Private generated asset. Do not commit.', '#pragma once', '#include "ganado_cast_runtime.h"',
             'namespace ganado_ps2_stump {', 'using Weight=ganadocast::Weight;',
             f'static const int parents[34]={parents};', f'static const float bind[34][12]={bind2};',
             'static constexpr unsigned atlas_crc=0x65c6fe5au,atlas_fnv=0x2593694eu;']
    for kind, key in [('pos', 'positions'), ('nrm', 'normals'), ('uv', 'uv'), ('gx', 'stream')]:
        const = '' if kind == 'gx' else 'const '
        lines.append(f'alignas(32) static {const}unsigned char head_{kind}[]={{\n{mr.cbytes(c[key])}\n}};')
    lines.append('static const Weight head_weights[]={')
    for b, n, w in c['weights']:
        lines.append('{{%s},%s,{%s}},' % (','.join(map(str, b)), n, ','.join(map(mr.cfloat, w))))
    lines.extend(['};', 'static ganadocast::Chunk head={1,%u,%u,%u,%u,%u,head_pos,head_nrm,head_uv,head_gx,head_weights};' %
                  tuple(c[k] for k in ('position_count', 'normal_count', 'palette_count', 'triangles', 'stream_bytes')),
                  f'static constexpr unsigned skin_stream_bytes={mr.skin_stream_bytes(c["weights"])};', '}'])
    out.mkdir(parents=True, exist_ok=True)
    target = out / 'ganado_ps2_stump_runtime.h'
    target.write_text('\n'.join(lines) + '\n')
    report = dict(source_pins=PINS, gc_bin479_sha256=facts, native_sha256=RUNTIME_SHA,
                  runtime_sha256=mr.sha(target.read_bytes()), triangles=90, palette_count=c['palette_count'],
                  used_bones=sorted({b[i] for b, n, w in c['weights'] for i in range(n) if w[i]}),
                  atlas_payload_sha256=mr.sha(tex[96:]), cast_header_sha256=mr.sha(cast_header.read_bytes()),
                  normal_atlas=str(normal_atlas), private_header=str(target))
    (out / 'stump-manifest.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for arg in ('inputs', 'converted', 'cast-header', 'normal-atlas', 'out'):
        p.add_argument('--' + arg, type=Path, required=True)
    a = p.parse_args()
    generate(a.inputs, a.converted, a.cast_header, a.normal_atlas, a.out)
