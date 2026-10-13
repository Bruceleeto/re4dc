#!/usr/bin/env python3
"""Offline Luis PS2 mesh conversion with explicit GC source coverage.

The actor emits five draw chunks covering six original GC infos. The registry
and transaction currently require one draw chunk per info; these artifacts are
not admissible until that ownership contract is implemented and qualified.
No source gameplay, cloth, hand, lighting, or transaction code is modified.
"""
import argparse
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image

import ps2_cast as pc

PS2_SHA = '4949d656d05a3e25f37f5c511a3cdbb5aa04ab2a8bdb649071b63c2e34e2d4a5'
GC_SHA = '2b5b554d45a67f12612474a9ed0a1bbeb7cf5882d16a7c67ce7ff25018676f27'
GC_ACTOR = [(4, 5, 'body'), (6, 7, 'head'), (8, 7, 'face'),
            (9, 5, 'hair'), (10, 5, 'right-hand'), (11, 5, 'left-hand')]
# role = the primary GC source info. gc_infos proves the complete owned set.
ACTOR_COVERAGE = [dict(role=0, gc_infos=[0], bin=4, tpl=5, materials=[1, 2, 3, 4]),
                  dict(role=1, gc_infos=[1, 2], bin=4, tpl=5, materials=[0]),
                  dict(role=3, gc_infos=[3], bin=6, tpl=5, materials=[0]),
                  dict(role=4, gc_infos=[4], bin=7, tpl=5, materials=[0, 1]),
                  dict(role=5, gc_infos=[5], bin=8, tpl=5, materials=[0, 1])]
HAIR_MAP = {64: 64, 65: 66, 66: 72, 67: 74, 68: 78, 69: 80, 70: 85, 71: 88}
EXACT_HAIR = {66: 72, 67: 74, 68: 78, 69: 80}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def check_coverage(coverage, info_count, materials_by_bin):
    """All GC infos and all PS2 material sections are covered exactly once."""
    infos, source_materials = [], []
    for row in coverage:
        require(row['gc_infos'] and row['role'] == row['gc_infos'][0], 'primary role differs from coverage owner')
        infos.extend(row['gc_infos'])
        for mat in row['materials']:
            require(row['bin'] in materials_by_bin and 0 <= mat < materials_by_bin[row['bin']],
                    'PS2 material selection outside the source BIN')
            source_materials.append((row['bin'], mat))
    require(sorted(infos) == list(range(info_count)), 'GC source infos are missing or multiply covered')
    expected = [(b, m) for b, n in materials_by_bin.items() for m in range(n)]
    require(sorted(source_materials) == sorted(expected), 'PS2 material sections are missing or multiply covered')


def luis_bone_map(ps2_bones, gc_bones):
    """Pinned source anatomical roots plus explicit rest-offset transforms.

    Every PS2 hair root is a direct child of head 4. Its paired GC root is the
    unique direct child of head 4 with the same exact X coordinate. Four pairs
    also have the same full translation. The other four retain their measured
    source offset, represented by G_rest^-1 * P_rest. Animated equivalence is
    not implied by this bind-space transform.
    """
    require(len(ps2_bones) == 72 and len(gc_bones) == 90, 'unexpected Luis skeleton cardinality')
    require([b['id'] for b in ps2_bones] == list(range(72)), 'PS2 skeleton ids are not ordered')
    require([b['attach'] for b in gc_bones] == list(range(90)), 'GC owner ids are not ordered')
    for i in range(64):
        p, g = ps2_bones[i], gc_bones[i]
        require(p['parent'] == g['parent'], f'body bone {i} parent mismatch')
        require(max(abs(x-y) for x, y in zip(p['pos'], g['translation'])) < 1e-8,
                f'body bone {i} translation mismatch')
    mapping = {i: i for i in range(64)}
    proof = []
    for p_id, g_id in HAIR_MAP.items():
        p, g = ps2_bones[p_id], gc_bones[g_id]
        require(p['parent'] == 4 and g['parent'] == 4, f'hair root {p_id} is not a direct head child')
        matches = [b['attach'] for b in gc_bones[64:] if b['parent'] == 4 and b['translation'][0] == p['pos'][0]]
        require(matches == [g_id], f'hair root {p_id} has no unique source X/parent identity')
        delta = [x-y for x, y in zip(p['pos'], g['translation'])]
        require(all(math.isfinite(x) for x in delta) and math.dist(p['pos'], g['translation']) < 60,
                f'hair root {p_id} source displacement changed')
        if p_id in EXACT_HAIR:
            require(max(abs(x) for x in delta) < 1e-8, f'exact hair root {p_id} moved')
        offset = np.eye(4)
        offset[:3, 3] = delta
        mapping[p_id] = g_id
        proof.append(dict(ps2=p_id, gc=g_id, source_parent=4, exact_xyz=p_id in EXACT_HAIR,
                          unique_source_x=p['pos'][0], gc_to_ps2_rest_offset=offset.tolist(),
                          root_distance_mm=math.sqrt(sum(x*x for x in delta))))
    return mapping, proof


def bind_pose_proof(ps2_bones, gc_bones, mapping, positions, source_weights):
    """Check rest-position identity and retarget transform algebra per vertex."""
    p_rest = {}
    for b in ps2_bones:
        m = np.eye(4)
        m[:3, 3] = b['pos']
        if b['parent'] >= 0:
            m = p_rest[b['parent']] @ m
        p_rest[b['id']] = m
    g_rest = {b['attach']: np.asarray(b['rest']) for b in gc_bones}
    max_rest = max_algebra = 0.0
    # Deterministic nonidentity rigid poses check the transform equation, not
    # source gameplay/cloth animation. Real animation capture remains pending.
    for position, weights in zip(positions, source_weights):
        ph = np.r_[position, 1.0]
        direct = np.zeros(4)
        virtual = np.zeros(4)
        bind = np.zeros(4)
        for p_id, weight in weights:
            g_id = mapping[p_id]
            G, P = g_rest[g_id], p_rest[p_id]
            offset = np.linalg.inv(G) @ P
            angle = (g_id + 1) * .013
            pose = np.array([[math.cos(angle), -math.sin(angle), 0, g_id * 1.1],
                             [math.sin(angle), math.cos(angle), 0, -g_id * .7],
                             [0, 0, 1, g_id * .3], [0, 0, 0, 1]]) @ G
            direct += weight * (pose @ np.linalg.inv(G) @ ph)
            virtual += weight * (pose @ offset @ np.linalg.inv(P) @ ph)
            bind += weight * (G @ np.linalg.inv(G) @ ph)
        max_rest = max(max_rest, float(np.linalg.norm(bind[:3] - ph[:3])))
        max_algebra = max(max_algebra, float(np.linalg.norm(direct[:3] - virtual[:3])))
    require(max_rest < 0.001 and max_algebra < 1e-8, 'inverse-bind retarget transform proof failed')
    return dict(vertices=len(positions), maximum_rest_error_mm=max_rest,
                maximum_virtual_root_algebra_error_mm=max_algebra,
                animation_evidence='NONE: nonidentity matrices test algebra only, not original cloth poses')


def combine_gc_meshes(gc, source_specs, info_ids):
    meshes = [pc.gc_mesh(pc.gc_entry(gc, source_specs[i][0], 'BIN')) for i in info_ids]
    pos, tris, normals = [], [], []
    for m in meshes:
        off = len(pos)
        pos.extend(m['positions'])
        tris.extend(m['triangles'] + off)
        normals.extend(m['corner_normals'])
    return dict(positions=np.asarray(pos), triangles=np.asarray(tris), corner_normals=normals)


def convert(kind, inputs, out, pack=False):
    require(not out.exists(), 'output already exists; choose a fresh evidence directory')
    pd, gd = (inputs/'pl14.dat').read_bytes(), (inputs/'pl14.drs').read_bytes()
    require(pc.sha(pd) == PS2_SHA and pc.sha(gd) == GC_SHA, 'source archive identity differs from the mapped audit')
    ps2 = {i+4: (tag, b) for i, tag, b in pc.pb.dat_entries(pd)}
    gc = pc.drs.Drs(gd)
    source_specs = GC_ACTOR if kind == 'actor' else [(14, 15, 'gun')]
    coverage = ACTOR_COVERAGE if kind == 'actor' else [dict(role=0, gc_infos=[0], bin=11, tpl=12, materials=[0])]
    pbins = {r['bin']: pc.pb.parse_bin(ps2[r['bin']][1]) for r in coverage}
    check_coverage(coverage, len(source_specs), {b: len(m.materials) for b, m in pbins.items()})
    bones = pc.gc_skeleton(pc.gc_entry(gc, source_specs[0][0], 'BIN'))
    pbody = pbins[coverage[0]['bin']]
    if kind == 'actor':
        bone_map, hair_proof = luis_bone_map(pbody.bones, bones)
    else:
        require(len(pbody.bones) == len(bones) == 7, 'gun skeleton cardinality differs')
        require(all((p['id'], p['parent'], list(p['pos'])) == (g['attach'], g['parent'], g['translation'])
                    for p, g in zip(pbody.bones, bones)), 'gun source skeleton differs')
        bone_map, hair_proof = {i: i for i in range(7)}, []
    # Sparse attachment ids are owner ids, never local part-table positions.
    for m in pbins.values():
        require(all(b['id'] in bone_map for b in m.bones), 'unmapped sparse PS2 attachment bone')
    out.mkdir(parents=True)
    textures = out/'textures'; textures.mkdir()
    decoder = pc.load_module('ps2_tpl_decode', pc.WA/'from-main/ps2-trees/tools/ps2_tpl_decode.py')
    images, tpl_records = {}, {}
    for tpl in sorted({r['tpl'] for r in coverage}):
        tag, data = ps2[tpl]
        require(tag == 'TPL', 'mapped PS2 texture is not a TPL')
        parsed = decoder.parse_tpl(data)
        facts = []
        for i, h in enumerate(parsed['entries']):
            w, height, rgba, stats = decoder.decode(data, h)
            img = Image.frombytes('RGBA', (w, height), bytes(rgba))
            name = f'ps2-tpl{tpl:02x}-image{i:02d}.png'
            img.save(textures/name)
            images[(tpl, i)] = img
            facts.append(dict(index=i, width=w, height=height, file='textures/'+name,
                              decoded_rgba_sha256=pc.sha(bytes(rgba)), format=decoder.describe(h)['format'],
                              alpha_raw=sorted(stats['alpha_raw_hist'])))
        tpl_records[tpl] = dict(sha256=pc.sha(data), bytes=len(data), images=facts)
    used = sorted({(r['tpl'], pbins[r['bin']].materials[m]['diffuse']) for r in coverage for m in r['materials']})
    cells, size = pc.pack_atlas([(i, *images[key].size) for i, key in enumerate(used)])
    atlas = Image.new('RGBA', size, (0, 0, 0, 255))
    for i, key in enumerate(used):
        atlas.paste(images[key], cells[i][:2])
    atlas.save(out/'atlas-rgba.png')
    atlas.convert('RGB').convert('RGBA').save(out/'atlas.png')
    vertices, positions, weights, ps2_weights, triangles = {}, [], [], [], []
    val_coverage, degenerates, zero_normals = [], 0, 0
    all_source_triangles, kept_source_triangles = set(), set()
    for r in coverage:
        m = pbins[r['bin']]
        candidates = [(k, mat, cs) for k, (mat, cs) in enumerate(pc.pb.triangles(m)) if mat in r['materials']]
        start = len(triangles)
        mats = []
        for mi in r['materials']:
            material = dict(m.materials[mi]); material['index'] = mi
            if material['flag'] & 4:
                require((r['tpl'], material['opacity']) in images, 'source opacity image is absent')
                material['opacity_file'] = f"textures/ps2-tpl{r['tpl']:02x}-image{material['opacity']:02d}.png"
            mats.append(material)
        for k, mi, corners in candidates:
            source_key = (r['bin'], k)
            require(source_key not in all_source_triangles, 'source triangle multiply selected')
            all_source_triangles.add(source_key)
            a, b, c = (np.asarray(v['p']) for v in corners)
            face = np.cross(b-a, c-a)
            if not np.linalg.norm(face):
                degenerates += 1
                continue
            face /= np.linalg.norm(face)
            cell = cells[used.index((r['tpl'], m.materials[mi]['diffuse']))]
            cs = []
            for corner in corners:
                original = [(int(bone), float(w)) for bone, w in corner['w'] if w > 0]
                require(original and all(b in bone_map for b, _ in original), 'unmapped PS2 skin weight')
                require(abs(sum(w for _, w in original)-1) < .0001, 'PS2 skin weights do not sum to one')
                mapped = [(bone_map[b], w) for b, w in original]
                key = (tuple(corner['p']), tuple(original))
                if key not in vertices:
                    vertices[key] = len(positions)
                    positions.append(list(corner['p'])); weights.append(mapped); ps2_weights.append(original)
                normal = corner['n']
                if not any(normal):
                    normal = face.tolist(); zero_normals += 1
                u, v = corner['raw']['uv']
                require(0 <= u <= 256 and 0 <= v <= 256, 'source UV exceeds its atlas cell')
                cs.append(dict(vertex=vertices[key], normal=list(normal),
                               uv=[(cell[0]+u*cell[2]/256)/size[0], (cell[1]+v*cell[3]/256)/size[1]]))
            triangles.append(dict(source_info=r['role'], corners=cs,
                                  ps2_source=dict(bin=r['bin'], triangle=k, material=mi)))
            kept_source_triangles.add(source_key)
        gc_mesh = combine_gc_meshes(gc, source_specs, r['gc_infos'])
        selected = triangles[start:]
        pt = np.asarray([[c['vertex'] for c in t['corners']] for t in selected])
        g_wind = pc.winding_agreement(gc_mesh['positions'], gc_mesh['triangles'], gc_mesh['corner_normals'])
        p_wind = pc.winding_agreement(np.asarray(positions), pt,
                                    [[np.asarray(c['normal']) for c in t['corners']] for t in selected])
        flip = (g_wind > .5) != (p_wind > .5)
        if flip:
            for tri in selected:
                tri['corners'].reverse()
        val_coverage.append(dict(r, source_bin_sha256=pc.sha(ps2[r['bin']][1]), source_materials=mats,
                                 source_triangles=len(candidates), nondegenerate_triangles=len(selected),
                                 winding_flipped=flip, gc_winding_agreement=g_wind, ps2_winding_as_read=p_wind))
    expected = sum(len(pc.pb.triangles(m)) for m in pbins.values())
    require(len(all_source_triangles) == expected and len(kept_source_triangles)+degenerates == expected,
            'PS2 triangle coverage is incomplete')
    identity_infos, bindings = [], []
    for i, (arc, tpl, role) in enumerate(source_specs):
        gb = pc.gc_entry(gc, arc, 'BIN')
        sig = pc.gc_signature(gb)
        identity_infos.append(dict(id=i, address=f'pl14:arc:{arc:03x}', source_data_address=f'pl14:arc:{arc:03x}',
                                   source_bin_arc=arc, source_tpl_arc=tpl, source_sha256=pc.sha(gb), role=role))
        bindings.append(dict(bin=arc, tpl=tpl, role=role, **sig,
                             binding_scope='Exact GC source info; local part numbers are not owner bone identities'))
    source = dict(name=f'luis-{kind}', schema='ps2cast-mapped-source-1', source_units='millimetres',
                  source_archive='pl14', source_archive_sha256=GC_SHA, ps2_archive_sha256=PS2_SHA,
                  bones=[dict(id=b['id'], parent=b['parent'], address=f"pl14:part:{b['id']}", rest=b['rest'], capture=b['capture'])
                         for b in bones], infos=identity_infos, category='registry', rooms=['r11c'], types=[0],
                  source_coverage=coverage, registry_admission='pending merged-source ownership support' if kind == 'actor' else 'not tested')
    sp = out/'source.json'; sp.write_text(json.dumps(source))
    mesh = dict(schema='re4dc-approved-render-mesh-1', source_sha256=pc.sha(sp.read_bytes()), mesh=f'luis_{kind}_ps2',
                positions_mm=positions, weights=weights, bones=source['bones'], triangles=triangles,
                policy='All nondegenerate PS2 triangles, source normals/UV/material identities; explicit GC owner bone map. '
                       'No geometry reduction. Rest transform verified; original animation and runtime admission pending.')
    mp = out/'mesh.json'; mp.write_text(json.dumps(mesh))
    (out/'source-bindings.json').write_text(json.dumps(bindings, indent=2))
    proof = bind_pose_proof(pbody.bones, bones, bone_map, positions, ps2_weights)
    validation = dict(kind=kind, source_sha256=pc.sha(sp.read_bytes()), mesh_sha256=pc.sha(mp.read_bytes()),
                      source_archives=dict(ps2=PS2_SHA, gc=GC_SHA), coverage=val_coverage,
                      gc_source_infos=len(source_specs), draw_chunks=len(coverage),
                      raw_source_triangles=expected, nondegenerate_triangles=len(triangles),
                      degenerate_triangles_dropped=degenerates, zero_normals_replaced=zero_normals,
                      bone_map=bone_map, hair_root_proof=hair_proof, bind_pose=proof,
                      textures=tpl_records, atlas=dict(size=size, cells={str(key): cells[i] for i, key in enumerate(used)}),
                      runtime_admission=False, visual_acceptance=False, original_animation_review=False)
    (out/'coverage-manifest.json').write_text(json.dumps(validation, indent=2))
    # Minimal native-host staging metadata; admission still requires the complete
    # coverage manifest. This colour atlas does not implement the hair mask.
    stage = dict(validation, texture=dict(key=pc.texture_key(out/'atlas.png'), atlas=list(size),
                 alpha_contract='Original opacity images retained separately; native mask runs pending'))
    (out/'validation.json').write_text(json.dumps(stage, indent=2))
    if pack:
        packer = pc.load_module('pack_coarse_actor', pc.PROTO/'tools/pack_coarse_actor.py')
        packer.pack(mp, sp, out/'native', 'castmodel')
        pc.host_fixture(out/'native', source)
    print(json.dumps({k:validation[k] for k in ('kind', 'gc_source_infos', 'draw_chunks', 'raw_source_triangles',
                     'nondegenerate_triangles', 'degenerate_triangles_dropped', 'bind_pose')}, indent=2))
    return validation


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kind', choices=['actor', 'gun'], required=True)
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--pack', action='store_true')
    args = parser.parse_args()
    convert(args.kind, args.inputs, args.output, args.pack)


if __name__ == '__main__':
    main()
