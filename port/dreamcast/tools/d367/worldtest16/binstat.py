#!/usr/bin/env python3
"""binstat.py MESH SIDECAR WALK OUT.json [cam X,Z ...]: per mesh-bin statistics for landmark picking (worldtest16).
For every PS2 mesh bin: world box (union over placements), xz footprint, height, nearest walkable distance, level-0
corners, cluster count, and the horizontal distance to each test camera position. Uses the ladder's own Ladder class
(same walk grid and box rules as the reduction)."""
import sys, json, math, importlib.util, argparse
T = '/root/probe/codex-cpu-t15-20261016/tree/port/dreamcast/tools'
sys.path.insert(0, T)
spec = importlib.util.spec_from_file_location('lad', T + '/ps2_world_vert_ladder.py')
lad = importlib.util.module_from_spec(spec); spec.loader.exec_module(lad)

mesh, side, walk, out = sys.argv[1:5]
cams = [tuple(float(v) for v in c.split(',')) for c in sys.argv[5:]]
a = argparse.Namespace(mesh=mesh, sidecar=side, walk=walk, per_vertex=False, eye='0,0,0', protect_bins='', baked=0,
                       protect_last=0, view_mm=25000.0)
L = lad.Ladder(a)
bins = {}
for key, inf in L.info.items():
    b = bins.setdefault(inf['bin'], dict(lo=[1e18] * 3, hi=[-1e18] * 3, near=1e18, corners=0, clusters=0,
                                          meshes=set(), cam=[1e18] * len(cams), pl={}))
    for pi_, (wl, wh) in enumerate(inf['box']):
        q = b['pl'].setdefault((inf['mesh'], pi_), [list(wl), list(wh)])
        for k in range(3):
            q[0][k] = min(q[0][k], wl[k]); q[1][k] = max(q[1][k], wh[k])
        for k in range(3):
            b['lo'][k] = min(b['lo'][k], wl[k]); b['hi'][k] = max(b['hi'][k], wh[k])
        for i, (x, z) in enumerate(cams):
            d = math.hypot(max(wl[0] - x, 0, x - wh[0]), max(wl[2] - z, 0, z - wh[2]))
            b['cam'][i] = min(b['cam'][i], d)
    b['near'] = min(b['near'], inf['near']); b['corners'] += inf['corners']; b['clusters'] += 1; b['meshes'].add(inf['mesh'])
rows = []
for bn, b in bins.items():
    fx, fz = b['hi'][0] - b['lo'][0], b['hi'][2] - b['lo'][2]
    # largest single placement (instanced props repeat across the room: the union box is not their size)
    one = max((max(q[1][0] - q[0][0], q[1][2] - q[0][2]) for q in b['pl'].values()), default=0)
    oneh = max((q[1][1] - q[0][1] for q in b['pl'].values()), default=0)
    rows.append(dict(bin=bn, x0=round(b['lo'][0]), x1=round(b['hi'][0]), y0=round(b['lo'][1]), y1=round(b['hi'][1]),
                     z0=round(b['lo'][2]), z1=round(b['hi'][2]), fx=round(fx), fz=round(fz), h=round(b['hi'][1] - b['lo'][1]),
                     near=round(b['near']), corners=b['corners'], clusters=b['clusters'], meshes=sorted(b['meshes']),
                     cam=[round(c) for c in b['cam']], one=round(one), oneh=round(oneh), npl=len(b['pl'])))
rows.sort(key=lambda r: r['one'])
json.dump(rows, open(out, 'w'), indent=0)
tot = sum(r['corners'] for r in rows)
print('bins %d corners %d' % (len(rows), tot))
for r in rows:
    print('bin 0x%-4x one %6d h1 %6d npl %3d  union %6dx%-6d y %6d..%-6d corners %6d (%4.1f%%) cl %3d cam %s' % (
        r['bin'], r['one'], r['oneh'], r['npl'], r['fx'], r['fz'], r['y0'], r['y1'], r['corners'], 100.0 * r['corners'] / tot,
        r['clusters'], r['cam']))
