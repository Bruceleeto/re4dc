#!/usr/bin/env python3
"""regionlist.py MESH SIDECAR WALK L2.json x0,z0,x1,z1: clusters overlapping the xz box: bin, mesh, size, y range,
corners, and whether the L2 report replaced them (worldtest16 landmark diagnosis)."""
import sys, json, argparse, importlib.util
T = '/root/probe/codex-cpu-t15-20261016/tree/port/dreamcast/tools'
sys.path.insert(0, T)
spec = importlib.util.spec_from_file_location('lad', T + '/ps2_world_vert_ladder.py')
lad = importlib.util.module_from_spec(spec); spec.loader.exec_module(lad)
mesh, side, walk, rep, box = sys.argv[1:6]
x0, z0, x1, z1 = [float(v) for v in box.split(',')]
a = argparse.Namespace(mesh=mesh, sidecar=side, walk=walk, per_vertex=False, eye='0,0,0', protect_bins='', baked=0,
                       protect_last=0, view_mm=25000.0)
L = lad.Ladder(a)
R = json.load(open(rep))
done = {(r['part'], r['src_cluster']): r['decision'] for r in R['clusters']}
nm = len(L.src['meshes'])
for (pi, n), inf in sorted(L.info.items()):
    for wl, wh in inf['box']:
        if wl[0] <= x1 and wh[0] >= x0 and wl[2] <= z1 and wh[2] >= z0:
            ci = L.plan[pi][n][1]
            print('part %3d cl %d src_cluster %4d bin 0x%-3x mesh %3d%s  x %6d..%-6d y %6d..%-6d z %6d..%-6d size %6d corners %5d  %s' % (
                pi, n, ci, inf['bin'], inf['mesh'], ' (last14)' if inf['mesh'] >= nm - 14 else '', wl[0], wh[0], wl[1], wh[1], wl[2], wh[2],
                max(wh[0] - wl[0], wh[2] - wl[2]), inf['corners'], done.get((pi, ci), '-')))
