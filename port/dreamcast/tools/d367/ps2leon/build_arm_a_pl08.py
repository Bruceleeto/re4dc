#!/usr/bin/env python3
"""ps2leon arm A for the no-jacket costume (PS2_LEON=1, pl08 rooms): the PS2 pl08 Leon's own sections as an approved
render mesh (re4dc-approved-render-mesh-1, nine pl08 source infos), the input of pack_coarse_actor.py with the pl08
source (pl08-source.json), as the pl08 4k candidate was packed (native-scene/pl08/merge_pack.py).

  build_arm_a_pl08.py <arm-a mesh.json> <out dir>      writes <out>/mesh.json and <out>/report-pl08.json

pl08 list positions (source infos) and owner roles: 0 body (BIN4, role 0), 1 BIN10 (role 1), 2 BIN13 (role 2),
3 face (role 3), 4 head (role 4), 5 hair (role 7), 6 BIN16 (role 8, no pl00 counterpart), 7 right hand (wep02, role 5),
8 left hand (role 6). The owner draws pl08's own infos 0, 1 and 6 from the ACTOR_PL08_PACK package and roles 2..7 from
the arm's leon4k chunks, so only infos 0, 1, 6 are new here; the shared infos are arm A's triangles (remapped, order
kept) so the packer sees a complete nine-info mesh.

Geometry: the PS2 pl08.dat sections at the GC arcs 0x004, 0x00a, 0x010 (every strip triangle except zero-area joints),
positions in the GC model space (88-96 % of the PS2 vertices sit on a GC pl08 vertex). Normals: the PS2 corner
normals. Weights: the PS2 weights (every weighted bone is a GC skeleton bone with the GC parent: 1-30, 113, 114; the
PS2-only cloth bones 67+ carry no weight in these sections). UVs: PS2 raw / 256 (= the GC UV at coincident corners,
checked below) mapped into the pl08 512 atlas tiles (7506e95f-68cf2211, native-scene/pl08/blender/asset-report.json).
PS2 material -> GC image: the image of the nearest GC pl08 triangle, by majority per PS2 material (reported); no
texture, atlas or VRAM change. Render only.
"""
import hashlib, json, sys
from collections import Counter
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
import leon_sources as ls  # noqa: E402
import ps2_bin as pb  # noqa: E402

NS = ls.PRIV / 'architect-review-20261003/tools/supervisor-20261003/native-scene/pl08'
SRC = NS / 'source/pl08-source.json'
TILES = {k.replace('SourceTex_', ''): t for k, t in json.loads((NS / 'blender/asset-report.json').read_text())['source_uv_tiles'].items()}
OWN = ((0x004, 0), (0x00a, 1), (0x010, 6))          # PS2 pl08 arc -> pl08 source info
SHARED = {2: 2, 3: 3, 4: 4, 7: 5, 5: 7, 6: 8}         # arm A (pl00 role) -> pl08 source info (merge_pack.py)


def atlas_uv(key, u, v):
    t = TILES[key]
    return [(t['x'] + 2 + u * t['inner_width']) / 512.0, 1.0 - (t['y'] + 2 + (1.0 - v) * t['inner_height']) / 512.0]


def main():
    arm_a, out = Path(sys.argv[1]), Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
    src = json.loads(SRC.read_text())
    a = json.loads(arm_a.read_text())
    pl8 = {i: (t, b) for i, t, b in pb.dat_entries(ls._cached('ps2-pl08.dat', lambda: pb.afs_read(ls.PS2_ISO, 'pl08.dat')))}
    parents, _ = ls.gc_skeleton()
    regions = ls.bone_regions(parents)
    positions, weights, triangles, remap = [], [], [], {}
    for t in a['triangles']:
        if t['source_info'] not in SHARED:
            continue
        cs = []
        for c in t['corners']:
            v = c['vertex']
            if v not in remap:
                remap[v] = len(positions); positions.append(a['positions_mm'][v]); weights.append(a['weights'][v])
            cs.append(dict(c, vertex=remap[v]))
        triangles.append(dict(t, source_info=SHARED[t['source_info']], corners=cs))
    rep = dict(shared_from=str(arm_a), shared_sha256=hashlib.sha256(arm_a.read_bytes()).hexdigest(), roles=[])
    for arc, info in OWN:
        t, d = pl8[arc - 4]
        assert t == 'BIN', (arc, t)
        m = pb.parse_bin(d)
        # PS2 bones that are not the GC skeleton's (different parent, e.g. the PS2 cloth bones 67+): must carry no weight
        foreign = {b['id'] for b in m.bones if b['id'] >= 119 or b['parent'] != parents[b['id']]}
        I = src['infos'][info]
        P = np.asarray(I['positions'], float)
        guv = {int(k): v for k, v in I['uv'].items()}
        gcent, gkey, gcorner = [], [], []
        for part in I['parts']:
            for tri in part['triangles']:
                gcent.append(P[[c[0] for c in tri]].mean(0)); gkey.append(part['texture'])
                for c in tri:
                    gcorner.append((P[c[0]], guv[c[2]]))
        gcent = np.asarray(gcent)
        gcp = np.asarray([p for p, _ in gcorner]); gcu = np.asarray([u for _, u in gcorner])
        tris = []
        dropped = 0
        for node, cs in pb.triangles(m):
            Q = np.asarray([c['p'] for c in cs], float)
            if np.linalg.norm(np.cross(Q[1] - Q[0], Q[2] - Q[0])) < 1e-6:
                dropped += 1; continue
            tris.append((node, cs))
        vote = {}
        for node, cs in tris:
            c = np.mean([x['p'] for x in cs], 0)
            vote.setdefault(m.materials[node]['diffuse'], Counter())[gkey[int(((gcent - c) ** 2).sum(1).argmin())]] += 1
        key_of = {dif: cnt.most_common(1)[0][0] for dif, cnt in vote.items()}
        for dif, cnt in vote.items():
            assert cnt.most_common(1)[0][1] >= .9 * sum(cnt.values()), ('ambiguous material', arc, dif, cnt)
        bad_bones = set()
        uv_d, vid, regs, mats = [], {}, Counter(), Counter()
        for node, cs in tris:
            key = key_of[m.materials[node]['diffuse']]
            mats[key] += 1
            tc, cw = [], []
            for c in cs:
                pk = tuple(np.round(c['p'], 4))
                w = tuple(sorted(((int(b), float(x)) for b, x in c['w']), key=lambda bw: -bw[1])[:3])
                bad_bones |= {b for b, _ in w if b in foreign}
                s = sum(x for _, x in w)
                w = tuple(sorted((b, x / s) for b, x in w))
                vk = (pk, w)
                if vk not in vid:
                    vid[vk] = len(positions); positions.append([float(x) for x in c['p']]); weights.append([[b, x] for b, x in w])
                cw.append(w)
                u, v = c['raw']['uv'][0] / 256.0, c['raw']['uv'][1] / 256.0
                # UV check: the GC corner at the same position with the nearest UV
                dd = ((gcp - np.asarray(c['p'])) ** 2).sum(1)
                near = dd < .0025
                if near.any():
                    uv_d.append(float(np.min(np.abs(gcu[near] - [u, v]).max(1))))
                tc.append(dict(vertex=vid[vk], normal=[float(x) for x in c['n']], uv=atlas_uv(key, u, v)))
            triangles.append(dict(source_info=info, corners=tc))
            regs[ls.triangle_region(cw, regions)] += 1
        assert not bad_bones, bad_bones
        uv_d = np.asarray(uv_d)
        row = dict(arc=arc, info=info, ps2_triangles=len(tris) + dropped, zero_area_dropped=dropped, triangles=len(tris),
                   vertices=len(vid), materials={str(k): v for k, v in key_of.items()}, images=dict(mats), regions=dict(regs),
                   gc_triangles=len(gcent), uv_check=dict(coincident_corners=int(len(uv_d)),
                   within_half_texel_256=float((uv_d <= .5 / 256).mean()) if len(uv_d) else None,
                   max=float(uv_d.max()) if len(uv_d) else None))
        rep['roles'].append(row)
        print(json.dumps(row))
    mesh = {
        'schema': 're4dc-approved-render-mesh-1', 'blend_sha256': None,
        'source_sha256': hashlib.sha256(SRC.read_bytes()).hexdigest(),
        'mesh': 'Leon_pl08_PS2_A_RenderMesh',
        'positions_mm': positions, 'weights': weights, 'bones': src['bones'], 'triangles': triangles,
        'source_info_counts': {str(i): sum(t['source_info'] == i for t in triangles) for i in range(len(src['infos']))},
        'policy': 'ps2leon arm A pl08: PS2 pl08 own sections (infos 0, 1, 6) + arm A shared sections on the GC skeleton; render only.',
    }
    text = json.dumps(mesh, separators=(',', ':'))
    (out / 'mesh.json').write_text(text)
    rep.update(triangles=len(triangles), own_triangles=sum(r['triangles'] for r in rep['roles']), vertices=len(positions),
               source_info_counts=mesh['source_info_counts'], mesh_sha256=hashlib.sha256(text.encode()).hexdigest())
    (out / 'report-pl08.json').write_text(json.dumps(rep, indent=1))
    print('ARM_A_PL08', rep['own_triangles'], 'own triangles', rep['triangles'], 'total', mesh['source_info_counts'])


if __name__ == '__main__':
    main()
