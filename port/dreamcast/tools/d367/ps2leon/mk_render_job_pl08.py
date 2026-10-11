#!/usr/bin/env python3
"""ps2leon pl08: bl_render.py job for the no-jacket Leon: GC pl08 (the original, from pl08-source.json), today's pl08
(the 4k candidate the play package carries: native-scene/pl08/mesh.json) and arm A pl08 (build_arm_a_pl08.py). The
nine pl08 infos are renumbered to bl_render's pl00 roles (hair 5 -> 7, the BIN13 knife 2 stays 2, hands 7/8 -> 5/6,
BIN16 6 -> 0), textured with the pl08 atlas (7506e95f-68cf2211) and its tiles.

  mk_render_job_pl08.py <arm-a-pl08 mesh.json> <work dir>    writes <work>/render-meshes/*.json and <work>/renders-job.json
"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import leon_sources as ls  # noqa: E402
CB = ls.PRIV / 'charbake-20261010/src'
# mk_render_job.py's six views (copied: that module writes its job at import)
views = [
    dict(name='front', aim='body', cam=[0, -2.95, 0.15], lens=50, size=[400, 720], wire=0.0042),
    dict(name='back', aim='body', cam=[0, 2.95, 0.15], lens=50, size=[400, 720], wire=0.0042),
    dict(name='side', aim='body', cam=[2.95, 0, 0.15], lens=50, size=[400, 720], wire=0.0042),
    # RE4's over-the-shoulder play camera: behind and right of Leon, looking ahead (Leon on the left of the frame)
    dict(name='game', relative=False, aim=[0.40, -3.0, 1.30], cam=[0.50, 1.05, 1.74], lens=30, size=[640, 480], wire=0.0026),
    dict(name='hair', aim='head', aim_offset=[0, 0, 0.07], cam=[0.42, 0.62, 0.10], lens=50, size=[480, 480], wire=0.0012, hide_roles=[2]),
    dict(name='face', aim='head', aim_offset=[0, 0, 0.07], cam=[-0.22, -0.70, 0.04], lens=50, size=[480, 480], wire=0.0012, hide_roles=[2]),
]

NS = ls.PRIV / 'architect-review-20261003/tools/supervisor-20261003/native-scene/pl08'
ROLE = {0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 7, 6: 0, 7: 5, 8: 6}
TILES = json.loads((NS / 'blender/asset-report.json').read_text())['source_uv_tiles']
TILE = {k.replace('SourceTex_', ''): t for k, t in TILES.items()}
HAIR = {'ac381b1a-3ade84b1': 1, '7a9de1fd-0e415f15': 2}


def atlas_uv(key, u, v):
    t = TILE[key]
    return [(t['x'] + 2 + u * t['inner_width']) / 512.0, 1.0 - (t['y'] + 2 + (1.0 - v) * t['inner_height']) / 512.0]


def renumber(mesh):
    out = dict(mesh)
    out['triangles'] = [dict(t, source_info=ROLE[t['source_info']]) for t in mesh['triangles']]
    return out


def gc_mesh(src):
    pos, wts, tris = [], [], []
    for info, I in enumerate(src['infos']):
        b = len(pos)
        for i, p in enumerate(I['positions']):
            pos.append(p); wts.append(I['weights'][I['palette_ids'][i]])
        uv = {int(k): v for k, v in I['uv'].items()}
        for part in I['parts']:
            key = part['texture']
            for t in part['triangles']:
                cs = []
                for c in t:
                    u, v = uv[c[2]]
                    d = dict(vertex=b + c[0], normal=I['normals'][c[1]], uv=atlas_uv(key, u, v))
                    if key in HAIR:
                        d['src_uv'] = [u, v]
                    cs.append(d)
                tt = dict(source_info=info, corners=cs)
                if key in HAIR:
                    tt['material'] = HAIR[key]
                tris.append(tt)
    return dict(schema='re4dc-approved-render-mesh-1', mesh='Leon_pl08_GC_Source', positions_mm=pos, weights=wts,
                bones=src['bones'], triangles=tris)


def main():
    arm, work = Path(sys.argv[1]), Path(sys.argv[2])
    md = work / 'render-meshes'; md.mkdir(parents=True, exist_ok=True)
    src = json.loads((NS / 'source/pl08-source.json').read_text())
    meshes = {'GC': gc_mesh(src), 'today': json.loads((NS / 'mesh.json').read_text()), 'PS2': json.loads(arm.read_text())}
    models = []
    for label, m in meshes.items():
        p = md / ('pl08-%s.json' % label)
        p.write_text(json.dumps(renumber(m), separators=(',', ':')))
        models.append(dict(label=label, mesh=str(p)))
        print(label, len(m['triangles']), 'triangles')
    job = dict(models=models, atlas=str(NS / 'blender/pl08-4k-diffuse-512.png'),
               hair={'1': str(CB / 'fc24a99c-03d13534.png'), '2': str(CB / '9cf7f055-d40aae38.png')},
               tiles=TILES, modes=['flat', 'clay'], views=views, out=str(work / 'renders'))
    (work / 'renders-job.json').write_text(json.dumps(job, indent=1))


if __name__ == '__main__':
    main()
