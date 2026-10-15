#!/usr/bin/env python3
"""Append baked object groups to a shipped PS2 world package (R4IM v3 + R4PW), keeping every existing table entry.

For crowd12's STATIC_OBJ_BAKE (lane objs 2026-10-15): the game's static objects (closed doors, windows, boxes, racks)
are baked into the room's PS2 world and drawn from it while their object asks (native_static.cpp PS2_PLACE_GATE).

Inputs
  base: the package the recipe stages (e.g. t11-20261014/r101-smx/ps2-world.re4mesh + its .r4pw; the .json beside it
        gives the LOD arguments it was built with, reused for the new meshes).
  obj:  the baked groups. `v x y z r g b [a]` (x --pos-scale = world mm; r g b a = final prelit colour 0..1, alpha 1 if
        absent), `vt u v` (the UV the GPU samples, no flip), `f` (triangles or fans, v/vt[/vn]), `usemtl <name>`, and
        `g BAKE#<em id>#<obj n>#COLOR#`. Groups with the same BAKE#<em>#<n> are one object = one placement (one part
        per material). Identical objects (same em, materials, UVs, colours, exact affine image) share one mesh.
  materials: json {name: {"key": "crc8-fnv8", "width": w, "height": h, "pass": 0 OP | 1 PT | 2 TR,
        "cull": 0 none | 1 | 2 (native part cull)}}. The key is a tex.pak key (pair keys for flag-4 parts): the world
        part binds it through the shared texture cache at draw time (no texture is written; gain 1).

Output (out dir): ps2-world.re4mesh / ps2-world.r4pw (base tables byte-identical, new meshes / parts / meshlets /
vertices / strips / clusters / levels appended, indices rebased), append.json (object -> placement field, mesh,
parts, sha256s). The new placements' field = --placement-base (default: base max + 1) + object order.
The strip-groups data (ps2_strip_groups.py, r4sg) and any crc-tied sidecar must be regenerated from the output.
Self-test: --selftest re-serializes the base alone and checks it is byte-identical.
"""
import argparse, collections, hashlib, json, math, struct, sys, zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import numpy as np
import convert_room_bins as crb
import mesh_lod

OWNER = 0x50
H, L = crb.HEADER, crb.LOD_HEADER
TABLES = (('mesh', crb.MESH), ('part', crb.PART), ('meshlet', crb.MESHLET), ('vertex', crb.VERTEX),
          ('index', None), ('palette', None), ('vcolor', None), ('part_lod', crb.PART_LOD), ('cluster', crb.CLUSTER),
          ('level', crb.LEVEL), ('class', None), ('rule', None))


def parse(blob):
    h = H.unpack_from(blob, 0)
    (magic, version, total, crc, nmesh, npart, nlet, nvert, nindex, npal, o_mesh, o_part, o_let, o_vert, o_index,
     o_pal, color, o_vcolor) = h[:18]
    assert magic == crb.MAGIC and total == len(blob), (magic, total, len(blob))
    assert zlib.crc32(blob[H.size:]) == crc, 'body crc'
    lh = L.unpack_from(blob, H.size)
    ncl, nlv, o_plod, o_cl, o_lv, o_class, o_rule = lh[:7]
    t = dict(version=version, color=color)
    t['mesh'] = [list(r) for r in crb.MESH.iter_unpack(blob[o_mesh:o_mesh + nmesh * crb.MESH.size])]
    t['part'] = [list(r) for r in crb.PART.iter_unpack(blob[o_part:o_part + npart * crb.PART.size])]
    t['meshlet'] = [list(r) for r in crb.MESHLET.iter_unpack(blob[o_let:o_let + nlet * crb.MESHLET.size])]
    t['vertex'] = [list(r) for r in crb.VERTEX.iter_unpack(blob[o_vert:o_vert + nvert * crb.VERTEX.size])]
    t['index'] = bytes(blob[o_index:o_index + nindex])
    t['palette'] = list(struct.unpack_from('<%dI' % npal, blob, o_pal))
    t['vcolor'] = bytes(blob[o_vcolor:o_vcolor + 4 * nvert]) if o_vcolor else b''
    t['part_lod'] = [list(r) for r in crb.PART_LOD.iter_unpack(blob[o_plod:o_plod + npart * crb.PART_LOD.size])]
    t['cluster'] = [list(r) for r in crb.CLUSTER.iter_unpack(blob[o_cl:o_cl + ncl * crb.CLUSTER.size])]
    t['level'] = [list(r) for r in crb.LEVEL.iter_unpack(blob[o_lv:o_lv + nlv * crb.LEVEL.size])]
    t['class'] = bytes(blob[o_class:o_class + nmesh]) if o_class else b''
    t['rule'] = bytes(blob[o_rule:o_rule + crb.CLASS_RULES * crb.CLASS_RULE.size]) if o_rule else b''
    return t


def serialize(t):
    """convert_room_bins.convert_lod's layout: 80-byte header, LOD header, 32-byte aligned tables in TABLES order."""
    blobs = dict(mesh=b''.join(crb.MESH.pack(*m) for m in t['mesh']),
                 part=b''.join(crb.PART.pack(*p) for p in t['part']),
                 meshlet=b''.join(crb.MESHLET.pack(*m) for m in t['meshlet']),
                 vertex=b''.join(crb.VERTEX.pack(*v) for v in t['vertex']),
                 index=t['index'], palette=b''.join(struct.pack('<I', c) for c in t['palette']), vcolor=t['vcolor'],
                 part_lod=b''.join(crb.PART_LOD.pack(*p) for p in t['part_lod']),
                 cluster=b''.join(crb.CLUSTER.pack(*c) for c in t['cluster']),
                 level=b''.join(crb.LEVEL.pack(*l) for l in t['level']), **{'class': t['class']}, rule=t['rule'])
    body, offsets = bytearray(), {}
    head = H.size + L.size
    for name, _ in TABLES:
        blob = blobs[name]
        if not blob and name in ('class', 'rule', 'vcolor'):
            continue
        start = crb.align(head + len(body)) - head
        body.extend(b'\0' * (start - len(body)))
        offsets[name] = head + len(body)
        body.extend(blob)
    body.extend(b'\0' * (crb.align(head + len(body)) - head - len(body)))
    lod = L.pack(len(t['cluster']), len(t['level']), offsets['part_lod'], offsets['cluster'], offsets['level'],
                 offsets.get('class', 0), offsets.get('rule', 0), 0)
    body = lod + bytes(body)
    header = H.pack(crb.MAGIC, t['version'], H.size + len(body), zlib.crc32(body), len(t['mesh']), len(t['part']),
                    len(t['meshlet']), len(t['vertex']), len(t['index']), len(t['palette']), offsets['mesh'],
                    offsets['part'], offsets['meshlet'], offsets['vertex'], offsets['index'], offsets['palette'],
                    t['color'], offsets.get('vcolor', 0), 0, 0)
    return header + body


def append_tables(a, b):
    """a + b with b's indices rebased; a's entries unchanged."""
    assert a['color'] == b['color'] == crb.COLOR_ARGB1555, 'prelit packages only'
    assert a['palette'] == b['palette'], 'palette differs (prelit packages carry one word)'
    assert not a['vcolor'] and not b['vcolor']
    t = dict(version=max(a['version'], b['version']), color=a['color'], palette=a['palette'], vcolor=b'')
    np_, nl, nv, nc, nlv = len(a['part']), len(a['meshlet']), len(a['vertex']), len(a['cluster']), len(a['level'])
    index = bytearray(a['index'])
    index.extend(b'\0' * ((-len(index)) % 4))           # keep b's indexed (u16) tables aligned
    ni = len(index)
    t['mesh'] = a['mesh'] + [m[:6] + [m[6] + np_] + m[7:] for m in b['mesh']]
    t['part'] = a['part'] + [p[:6] + [p[6] + nl] + p[7:] for p in b['part']]
    t['meshlet'] = a['meshlet'] + [[m[0] + nv, m[1] + ni] + m[2:] for m in b['meshlet']]
    t['vertex'] = a['vertex'] + b['vertex']
    t['index'] = bytes(index) + b['index']
    t['part_lod'] = a['part_lod'] + [[p[0] + nc, p[1]] for p in b['part_lod']]
    t['cluster'] = a['cluster'] + [c[:6] + [c[6] + nlv, c[7]] for c in b['cluster']]
    t['level'] = a['level'] + [[l[0] + nl, l[1], l[2]] for l in b['level']]
    t['class'] = a['class'] + (bytes(len(b['mesh'])) if a['class'] else b'')
    t['rule'] = a['rule']
    return t


def read_r4pw(blob):
    hp = struct.unpack_from('<4s7I', blob, 0)
    assert hp[0] == b'R4PW' and hp[1] == 1
    nplace, nparts, nmesh, crc = hp[2], hp[3], hp[4], hp[5]
    assert zlib.crc32(blob[32:]) == crc, 'r4pw crc'
    parts = [blob[32 + 16 * i:48 + 16 * i] for i in range(nparts)]
    base = 32 + 16 * nparts
    places = [blob[base + 52 * i:base + 52 * (i + 1)] for i in range(nplace)]
    return parts, places, nmesh


def write_r4pw(parts, places, nmesh):
    body = b''.join(parts) + b''.join(places)
    return struct.pack('<4s7I', b'R4PW', 1, len(places), len(parts), nmesh, zlib.crc32(body), 0, 0) + body


def read_obj(path, pos_scale):
    V, C, T, groups, cur, mtl = [], [], [], collections.OrderedDict(), None, None
    for ln, line in enumerate(Path(path).read_text().splitlines(), 1):
        w = line.split()
        if not w or w[0].startswith('#'):
            continue
        if w[0] == 'v':
            x = [float(s) for s in w[1:]]
            V.append([c * pos_scale for c in x[:3]])
            C.append((x[3:7] + [1.0] * 4)[:4] if len(x) >= 6 else [1.0, 1.0, 1.0, 1.0])
        elif w[0] == 'vt':
            T.append([float(w[1]), float(w[2])])
        elif w[0] == 'g':
            name = w[1] if len(w) > 1 else ''
            f = name.split('#')
            if len(f) < 4 or f[0] != 'BAKE':
                raise SystemExit('%s:%d: group name must be BAKE#<em id>#<obj n>#COLOR#' % (path, ln))
            if f[3] != 'COLOR':
                raise SystemExit('%s:%d: only COLOR (prelit) groups are supported' % (path, ln))
            cur = groups.setdefault((f[1], f[2]), dict(em=f[1], n=f[2], faces=[]))
        elif w[0] == 'usemtl':
            mtl = w[1]
        elif w[0] == 'f':
            if cur is None or mtl is None:
                raise SystemExit('%s:%d: face before g / usemtl' % (path, ln))
            c = []
            for s in w[1:]:
                p = s.split('/')
                if len(p) < 2 or not p[1]:
                    raise SystemExit('%s:%d: faces need v/vt' % (path, ln))
                c.append((int(p[0]) - 1, int(p[1]) - 1))
            for k in range(1, len(c) - 1):
                cur['faces'].append((mtl, (c[0], c[k], c[k + 1])))
    return np.asarray(V, np.float64), np.asarray(C, np.float64), np.asarray(T, np.float64), list(groups.values())


def fit_affine(a, b):
    """b = M @ [a, 1]; None unless exact (< 0.5 mm) and well conditioned (ps2_room_r4im.fit_affine)."""
    A = np.hstack([a, np.ones((len(a), 1))])
    if len(a) < 4 or np.linalg.svd(a - a.mean(0), compute_uv=False)[2] < 1.0:
        return None
    M, *_ = np.linalg.lstsq(A, b, rcond=None)
    if np.abs(A @ M - b).max() > 0.5:
        return None
    return M.T


def build(objs, V, C, T, mats):
    """Meshes (world space, or shared through an exact affine), parts per material in first-use order."""
    names = list(mats)
    meshes, sources, parts_meta, placements, firsts = [], {}, [], [], collections.defaultdict(list)
    for oi, o in enumerate(objs):
        pos = np.asarray([[V[v] for v, _ in tri] for _, tri in o['faces']])
        uv = np.asarray([[T[t] for _, t in tri] for _, tri in o['faces']])
        c8 = np.floor(np.clip(np.asarray([[C[v] for v, _ in tri] for _, tri in o['faces']]), 0, 1) * 255 + 0.5).astype(int)
        mt = [m for m, _ in o['faces']]
        for m in set(mt):
            if m not in mats:
                raise SystemExit('object %s#%s: material %s not in the materials json' % (o['em'], o['n'], m))
        sig = (tuple(mt), c8.tobytes(), np.round(uv, 5).tobytes())
        match = None
        for mi, first_pos, first_sig in firsts[o['em']]:
            if first_sig == sig:
                M = fit_affine(first_pos.reshape(-1, 3), pos.reshape(-1, 3))
                if M is not None:
                    match = (mi, M)
                    break
        if match:
            placements.append((match[0], oi, match[1].tolist()))
            continue
        mi = len(meshes)
        meshes.append(o)
        firsts[o['em']].append((mi, pos, sig))
        placements.append((mi, oi, [[1.0, 0, 0, 0], [0, 1.0, 0, 0], [0, 0, 1.0, 0]]))
        vid, positions = {}, []
        for f, (_, tri) in enumerate(o['faces']):
            for v, _ in tri:
                if v not in vid:
                    vid[v] = len(positions)
                    positions.append(tuple(float(x) for x in V[v]))
        uvs, uv_index, colors, color_index, order, loose = [], {}, [], {}, [], {}
        for f, (m, tri) in enumerate(o['faces']):
            if m not in loose:
                loose[m] = []
                order.append(m)
            corners = []
            for c, (v, _) in enumerate(tri):
                cc = tuple(int(x) for x in c8[f, c])
                u = (float(uv[f, c, 0]), float(uv[f, c, 1]))
                if cc not in color_index:
                    color_index[cc] = len(colors); colors.append(cc)
                if u not in uv_index:
                    uv_index[u] = len(uvs); uvs.append(u)
                corners.append((vid[v], color_index[cc], uv_index[u], 0))
            loose[m].append(tuple(corners))
        parts = []
        for k, m in enumerate(order):
            d = mats[m]
            crc, fnv = (int(x, 16) for x in d['key'].split('-'))
            if d['pass'] not in (0, 1, 2) or d['cull'] not in (0, 1, 2):
                raise SystemExit('material %s: pass / cull must be 0..2' % m)
            parts.append(dict(offset=32 * k, size=0, flags=0, texture=k & 255, alpha=255, strips=[], loose=loose[m]))
            parts_meta.append(struct.pack('<IIHHBBBB', crc, fnv, d['width'], d['height'], d['pass'], d['cull'],
                                          names.index(m) & 255, 0))
        sources[mi] = dict(flags=0, nvtx=min(65535, len(positions)), nparts=len(parts), positions=positions,
                           parts=parts, uv=uvs.__getitem__, color=colors.__getitem__,
                           normal=lambda n: (0.0, 1.0, 0.0), bytes=0)
    return meshes, sources, parts_meta, placements


class Token:
    def __init__(self, mesh):
        self.mesh = mesh


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('base', type=Path, help='base ps2-world.re4mesh (its .r4pw and .json beside it, or --base-pw)')
    ap.add_argument('--base-pw', type=Path)
    ap.add_argument('--base-json', type=Path, help='the base build report (LOD arguments); default <base>.json')
    ap.add_argument('--obj', type=Path)
    ap.add_argument('--materials', type=Path)
    ap.add_argument('--out', type=Path)
    ap.add_argument('--pos-scale', type=float, default=100.0, help='OBJ units -> world mm (default 100, the export)')
    ap.add_argument('--placement-base', type=int)
    ap.add_argument('--selftest', action='store_true')
    a = ap.parse_args()
    base = a.base.read_bytes()
    pw_path = a.base_pw or a.base.with_suffix('.r4pw')
    ta = parse(base)
    if serialize(ta) != base:
        raise SystemExit('the base does not re-serialize byte-identically: layout not understood, refusing')
    if a.selftest:
        print('selftest: base re-serializes byte-identically (%d bytes, %d meshes, %d parts)' % (
            len(base), len(ta['mesh']), len(ta['part'])))
        if pw_path.exists():
            pp, pl, nm = read_r4pw(pw_path.read_bytes())
            assert write_r4pw(pp, pl, nm) == pw_path.read_bytes()
            print('selftest: r4pw re-serializes byte-identically (%d placements, %d parts)' % (len(pl), len(pp)))
        return
    if not (a.obj and a.materials and a.out):
        raise SystemExit('--obj, --materials and --out are needed')
    args = json.loads((a.base_json or a.base.with_suffix('.json')).read_text())['args']
    crb.MAX_MESHLET_VERTICES = int(args.get('meshlet_vertices', 64))
    mesh_lod.STRIP_SWAPS = bool(args.get('strip_swaps', False))
    mesh_lod.UV_GUARD = args.get('lod_uv_guard')
    mats = json.loads(a.materials.read_text())
    V, C, T, objs = read_obj(a.obj, a.pos_scale)
    meshes, sources, parts_meta, placements = build(objs, V, C, T, mats)
    scales = collections.defaultdict(float)
    for mi, _, aff in placements:
        scales[(OWNER, mi)] = max(scales[(OWNER, mi)],
                                  max(math.sqrt(sum(aff[r][c] ** 2 for r in range(3))) for c in range(3)))
    entries = [(OWNER, 0, mi, Token(mi)) for mi in range(len(meshes))]
    eps = tuple(float(x) for x in str(args.get('lod_eps', '24,48,96,192,384')).split(','))
    floor = float(args.get('lod_floor', 2.0))
    blob_b, summary = crb.convert_lod(entries, 1.0, scales=dict(scales), eps_world=eps,
                                      cluster_world=float(args.get('lod_cluster', 20000.0)),
                                      min_gain=float(args.get('lod_min_gain', 0.4)),
                                      max_levels=int(args.get('lod_max_levels', 4)),
                                      floor={None: floor} if floor > 0 else None, share=not args.get('no_share', False),
                                      source=lambda token: sources[token.mesh], color_mode='prelit')
    if summary['parts'] != len(parts_meta):
        raise SystemExit('part count %d != %d (an empty mesh was skipped)' % (summary['parts'], len(parts_meta)))
    tb = parse(blob_b)
    merged = serialize(append_tables(ta, tb))
    pp, pl, nm = read_r4pw(pw_path.read_bytes())
    assert nm == len(ta['mesh']) and len(pp) == len(ta['part'])
    fields = [struct.unpack_from('<HH', p, 0)[1] for p in pl]
    pbase = a.placement_base if a.placement_base is not None else max(fields) + 1
    if pbase <= max(fields):
        raise SystemExit('--placement-base %d collides with the base placements (max %d)' % (pbase, max(fields)))
    new_places = [struct.pack('<HH12f', nm + mi, pbase + oi, *[x for row in aff for x in row])
                  for mi, oi, aff in placements]
    side = write_r4pw(pp + parts_meta, pl + new_places, nm + len(meshes))
    # checks: the base tables are unchanged inside the merged package
    tm = parse(merged)
    for k in ('mesh', 'part', 'meshlet', 'vertex', 'part_lod', 'cluster', 'level'):
        assert tm[k][:len(ta[k])] == ta[k], k
    assert tm['index'][:len(ta['index'])] == ta['index']
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / 'ps2-world.re4mesh').write_bytes(merged)
    (a.out / 'ps2-world.r4pw').write_bytes(side)
    report = dict(base=str(a.base), base_sha256=hashlib.sha256(base).hexdigest(), obj=str(a.obj),
                  obj_sha256=hashlib.sha256(a.obj.read_bytes()).hexdigest(), materials=str(a.materials),
                  lod_args=args, placement_base=pbase, base_placements=len(pl), base_meshes=nm,
                  added=dict(meshes=len(meshes), parts=len(parts_meta), placements=len(placements),
                             meshlets=len(tb['meshlet']), vertices=len(tb['vertex']), strip_bytes=len(tb['index'])),
                  objects=[dict(em=objs[oi]['em'], n=objs[oi]['n'], placement=pbase + oi, mesh=nm + mi,
                                instanced=aff != [[1.0, 0, 0, 0], [0, 1.0, 0, 0], [0, 0, 1.0, 0]])
                           for mi, oi, aff in placements],
                  re4mesh_bytes=len(merged), re4mesh_sha256=hashlib.sha256(merged).hexdigest(),
                  r4pw_bytes=len(side), r4pw_sha256=hashlib.sha256(side).hexdigest(),
                  mesh_crc='%08x' % struct.unpack_from('<I', merged, 12)[0],
                  r4pw_crc='%08x' % struct.unpack_from('<I', side, 20)[0])
    (a.out / 'append.json').write_text(json.dumps(report, indent=1))
    print(json.dumps({k: report[k] for k in ('placement_base', 'added', 're4mesh_bytes', 'r4pw_bytes', 'mesh_crc')}))


if __name__ == '__main__':
    main()
