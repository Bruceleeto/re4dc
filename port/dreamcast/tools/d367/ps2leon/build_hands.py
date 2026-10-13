#!/usr/bin/env python3
"""ps2leon hands (issue #26, 2026-10-13; LEON_HAND_POSES / LEON_HAND_DIR): the PS2 hand of every pose Leon's hand
slots can show, packed with arm A's pipeline, as the private header ps2leon_hands.h.

  build_hands.py <hands-inventory.json> <out dir>

Input: hands_inventory.py's list (every GC BIN the right / left hand slots can show, its runtime key and whether
the PS2 disc has the same file and arc). One pose per distinct runtime key; the standard hands (the handgun grip
wep02 arc 0x0a and the left grip pl00 arc 0x18, arm A's roles 5 / 6) are not repeated. For each pose: arm A's
mesh.json with role 5 (right) or 6 (left) replaced by the PS2 section of the pose's file and arc (build_arm_a's
rules for the hands: PS2 positions, normals and weights, PS2 UVs / 256 into the atlas tile of the PS2 texture),
packed exactly as pack_arm.py packs arm A (pack_coarse_actor, build_blob, verify_blob, patch_header); the role's
arrays and chunk row are taken from that header. A pose whose PS2 section cannot be converted (no PS2 BIN, a
texture outside the atlas tiles, a pack failure) is left out: at run time it draws arm A's standard hand.

ps2leon_hands.h (namespace leon_hands, after ps2leon_runtime.h): per pose its arrays, Chunk row, ChunkInput
spans, side (5 / 6) and GC runtime keys; count; max palettes. report-hands.json: per pose its source, PS2 status,
triangles, bytes, and every inventory entry with the pose it maps to.
"""
import copy, hashlib, json, re, sys, tempfile
from pathlib import Path
import numpy as np
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import leon_sources as ls  # noqa: E402
import build_arm_a as ba  # noqa: E402
import pack_arm as pa  # noqa: E402
import ps2_bin as pb  # noqa: E402

STANDARD = {5: 634592671, 6: 3988996401}   # GC vertex_hash of arm A's role 5 (wep02/0x0a) and role 6 (pl00/0x18)
ROLE = {'right': 5, 'left': 6}


def ps2_section(file, arc):
    d = None
    for i, t, b in pb.dat_entries(ls._cached('ps2-%s.dat' % file, lambda: pb.afs_read(ls.PS2_ISO, '%s.dat' % file))):
        if i == arc - 4:
            assert t == 'BIN', (file, arc, t)
            d = b
    if d is None:
        raise ValueError('no PS2 entry %s arc %#x' % (file, arc))
    m = pb.parse_bin(d)
    return m, pb.triangles(m)


def pose_triangles(role, file, arc, positions, weights):
    m, tris = ps2_section(file, arc)
    vid, out = {}, []
    for node, cs in tris:
        P = np.asarray([c['p'] for c in cs], float)
        if np.linalg.norm(np.cross(P[1] - P[0], P[2] - P[0])) < 1e-6:
            continue
        tex = m.materials[node]['diffuse']
        if tex not in ba.PS2_KEY[role]:
            raise ValueError('PS2 texture %d of %s arc %#x is not an atlas tile of role %d' % (tex, file, arc, role))
        key = ba.PS2_KEY[role][tex]
        tc = []
        for c in cs:
            pk = tuple(np.round(c['p'], 4))
            w = tuple(sorted(((int(b), float(x)) for b, x in c['w']), key=lambda bw: -bw[1])[:3])
            s = sum(x for _, x in w)
            if not w or s <= 0:
                raise ValueError('unweighted corner in %s arc %#x' % (file, arc))
            w = tuple(sorted((b, x / s) for b, x in w))
            if any(b >= 119 for b, _ in w):
                raise ValueError('bone outside the GC skeleton in %s arc %#x' % (file, arc))
            vk = (pk, w)
            if vk not in vid:
                vid[vk] = len(positions)
                positions.append([float(x) for x in c['p']])
                weights.append([[b, x] for b, x in w])
            u, v = c['raw']['uv'][0] / 256.0, c['raw']['uv'][1] / 256.0
            tc.append(dict(vertex=vid[vk], normal=[float(x) for x in c['n']], uv=ba.atlas_uv(key, u, v)))
        out.append(dict(source_info=role, corners=tc))
    return out


ARRAY = re.compile(r'alignas\(32\)\s+static\s+(?:const\s+)?unsigned\s+char\s+(i\d)_(pos|nrm|uv|gx)\[\]\s*=\s*\{([^}]*)\};', re.S)


def pack_role(mesh, role, work):
    work.mkdir(parents=True, exist_ok=True)
    mp = work / 'mesh.json'
    mp.write_text(json.dumps(mesh, separators=(',', ':')))
    pca = pa.load('pack_coarse_actor', pa.PROTO / 'tools/pack_coarse_actor.py')
    native, blobd = work / 'native', work / 'blob'
    pca.pack(mp, ls.LEON_SOURCE, native, 'leon4k')
    pa.run(pa.FAST / 'build_blob.py', native, blobd, '--report', work / 'blob-report.json')
    pa.run(pa.FAST / 'verify_blob.py', blobd, blobd)
    tmp = work / 'runtime.h'
    pa.run(pa.FAST / 'patch_header.py', native / 'leon4k_native.h', blobd, tmp)
    head = tmp.read_text()
    arrays = {}
    for m in ARRAY.finditer(head):
        if m.group(1) == 'i%d' % role:
            arrays[m.group(2)] = m.group(3).strip()
    wt = re.search(r'static const (?:leon4k::)?Weight i%d_weights\[\] = \{(.*?)\};' % role, head, re.S).group(1).strip()
    row = re.search(r'\{%d,(\d+),(\d+),(\d+),(\d+),(\d+),i%d_pos' % (role, role), head)
    assert set(arrays) == {'pos', 'nrm', 'uv', 'gx'} and row, 'role %d arrays not found' % role
    return arrays, wt, [int(x) for x in row.groups()]


def main():
    inv = json.loads(Path(sys.argv[1]).read_text())
    out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
    base = json.loads((ls.WORK / 'arms/a/mesh.json').read_text())
    poses, by_key = [], {}
    for e in inv:
        role = ROLE[e['side']]
        k = (role, e['key']['positions'], e['key']['normals'], e['key']['palette'], e['key']['vertex_hash'])
        if e['key']['vertex_hash'] == STANDARD[role]:
            e['pose'] = 'standard'
            continue
        if k not in by_key:
            by_key[k] = len(poses)
            poses.append(dict(role=role, file=e['file'], arc=e['arc'], keys=[], sources=[]))
        p = poses[by_key[k]]
        p['sources'].append('%s/%#x' % (e['file'], e['arc']))
        if list(k[1:]) not in p['keys']:
            p['keys'].append(list(k[1:]))
        e['pose'] = by_key[k]
    lines = ['// Private generated asset (ps2leon build_hands.py). Do not commit.',
             '// LEON_HAND_POSES / LEON_HAND_DIR: the PS2 hand of every pose of Leon\'s hand slots (namespace leon_hands).',
             'namespace leon_hands {', 'using leon4k::Chunk; using leon4k::Weight;']
    table, keys, spans, rep = [], [], [], []
    n = 0
    for i, p in enumerate(poses):
        r = dict(pose=i, role=p['role'], file=p['file'], arc=p['arc'], sources=p['sources'], keys=p['keys'])
        try:
            mesh = copy.deepcopy(base)
            mesh['triangles'] = [t for t in mesh['triangles'] if t['source_info'] != p['role']]
            tris = pose_triangles(p['role'], p['file'], p['arc'], mesh['positions_mm'], mesh['weights'])
            mesh['triangles'] += tris
            mesh['source_info_counts'] = {str(k): sum(t['source_info'] == k for t in mesh['triangles']) for k in range(8)}
            arrays, wt, row = pack_role(mesh, p['role'], out / 'work' / ('pose%02d' % i))
        except Exception as ex:   # noqa: BLE001 - recorded, the pose draws the standard hand
            r.update(status='standard-hand', reason=str(ex))
            rep.append(r); print('pose', i, p['file'], hex(p['arc']), 'FALLBACK', ex); continue
        pre = 'h%d' % n
        for a in ('pos', 'nrm', 'uv', 'gx'):
            lines.append('alignas(32) static const unsigned char %s_%s[] = {%s};' % (pre, a, arrays[a]))
        lines.append('static const Weight %s_weights[] = {%s};' % (pre, wt))
        pc, nc, pal, tri, sb = row
        table.append('{%d,%d,%d,%d,%d,%d,%s_pos,%s_nrm,%s_uv,%s_gx,%s_weights}' % (p['role'], pc, nc, pal, tri, sb, pre, pre, pre, pre, pre))
        spans.append(pre)
        for k in p['keys']:
            keys.append('{%d,%d,%d,%d,%uu,%d}' % (p['role'], k[0], k[1], k[2], k[3], n))
        nbytes = sum(len(arrays[a].split(',')) for a in ('pos', 'nrm', 'uv', 'gx')) + 16 * pal
        r.update(status='ps2', index=n, triangles=tri, positions=pc, palettes=pal, bytes=nbytes)
        rep.append(r); print('pose', i, p['file'], hex(p['arc']), 'PS2', tri, 'tris', nbytes, 'bytes')
        n += 1
    lines.append('static Chunk chunks[] = {%s};' % ','.join(table) if table else 'static Chunk chunks[1] = {};')
    lines.append('struct Key { unsigned role, positions, normals, palette, vertex_hash, pose; };')
    lines.append('static const Key keys[] = {%s};' % ','.join(keys) if keys else 'static const Key keys[1] = {};')
    lines.append('static constexpr unsigned count=%d, key_count=%d;' % (n, len(keys)))
    lines.append('static constexpr unsigned standard_vertex_hash[2]={%du,%du}; // arm A roles 5, 6' % (STANDARD[5], STANDARD[6]))
    lines.append('#define RE4DC_LEON_HAND_SPAN(p) {RE4DC_OWNER_SPAN(leon_hands::p##_pos),RE4DC_OWNER_SPAN(leon_hands::p##_nrm),'
                 'RE4DC_OWNER_SPAN(leon_hands::p##_uv),RE4DC_OWNER_SPAN(leon_hands::p##_gx),RE4DC_OWNER_SPAN(leon_hands::p##_weights)}')
    lines.append('struct Spans { re4dc_source::ByteSpan positions, normals, uv, stream, weights; };')
    lines.append('static const Spans spans[] = {%s};' % ','.join('RE4DC_LEON_HAND_SPAN(%s)' % s for s in spans) if spans else 'static const Spans spans[1] = {};')
    lines.append('}')
    text = '\n'.join(lines) + '\n'
    (out / 'ps2leon_hands.h').write_text(text)
    summary = dict(poses=len(poses), ps2=n, standard_fallback=len(poses) - n, header_sha256=hashlib.sha256(text.encode()).hexdigest(),
                   array_bytes=sum(r.get('bytes', 0) for r in rep))
    (out / 'report-hands.json').write_text(json.dumps(dict(summary=summary, poses=rep, inventory=inv), indent=1))
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
