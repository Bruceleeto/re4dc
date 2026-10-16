#!/usr/bin/env python3
"""diffverts.py SRC.re4mesh L2.re4mesh SIDECAR EYE_X,EYE_Z,YAW [maxdist]: world positions of level-0 vertices that the
ladder output no longer has (per mesh, model-space set difference), in front of a camera, binned on a 1 m xz grid with
their height range and the screen angle from the view axis (worldtest16 landmark search)."""
import sys, math, importlib.util, collections
T = '/root/probe/codex-cpu-t15-20261016/tree/port/dreamcast/tools'
sys.path.insert(0, T)
spec = importlib.util.spec_from_file_location('F', T + '/ps2_world_far_lod.py')
F = importlib.util.module_from_spec(spec); spec.loader.exec_module(F)
src = F.read(open(sys.argv[1], 'rb').read()); out = F.read(open(sys.argv[2], 'rb').read())
_, pls = F.read_sidecar(sys.argv[3], len(src['parts']))
ex, ez, yaw = [float(v) for v in sys.argv[4].split(',')]
far = float(sys.argv[5]) if len(sys.argv) > 5 else 30000.0
fx, fz = math.sin(yaw), math.cos(yaw)


def mesh_verts(m, mi):
    mesh = m['meshes'][mi]; s = set(); step, origin = mesh[11:14], mesh[8:11]
    for pi in range(mesh[6], mesh[6] + mesh[7]):
        c0, cn = m['plods'][pi][0], m['plods'][pi][1]
        for ci in range(c0, c0 + cn):
            lv = m['levels'][m['clusters'][ci][6]]
            for li in range(lv[0], lv[0] + lv[1]):
                for c in F.let_corners(m, m['lets'][li])[0]:
                    v = m['verts'][c]
                    s.add(tuple(round(origin[k] + step[k] * v[k]) for k in range(3)))
    return s


bymesh = collections.defaultdict(list)
for mi, aff in pls:
    bymesh[mi].append(aff)
grid = collections.defaultdict(lambda: [0, 1e9, -1e9, set()])
for mi in range(len(src['meshes'])):
    gone = mesh_verts(src, mi) - mesh_verts(out, mi)
    for p in gone:
        for aff in bymesh.get(mi, []):
            w = [aff[r][0] * p[0] + aff[r][1] * p[1] + aff[r][2] * p[2] + aff[r][3] for r in range(3)]
            dx, dz = w[0] - ex, w[2] - ez
            fwd = dx * fx + dz * fz
            if fwd <= 0 or math.hypot(dx, dz) > far:
                continue
            ang = math.degrees(math.atan2(dx * fz - dz * fx, fwd))
            if abs(ang) > 35:
                continue
            if w[1] > float(__import__('os').environ.get('YMAX', '1e9')):
                continue
            g = grid[(int(w[0] // 1000), int(w[2] // 1000))]
            g[0] += 1; g[1] = min(g[1], w[1]); g[2] = max(g[2], w[1]); g[3].add(src['meshes'][mi][0])
for (gx, gz), (n, y0, y1, bins) in sorted(grid.items(), key=lambda t: -t[1][0])[:int(__import__('os').environ.get('TOP', '60'))]:
    dx, dz = gx * 1000 + 500 - ex, gz * 1000 + 500 - ez
    print('cell x %6d z %6d  dist %5.1f m  ang %+5.1f  removed %4d  y %5d..%-5d bins %s' % (
        gx * 1000, gz * 1000, math.hypot(dx, dz) / 1000, math.degrees(math.atan2(dx * fz - dz * fx, dx * fx + dz * fz)),
        n, y0, y1, ','.join(hex(b) for b in sorted(bins))))
