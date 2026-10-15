"""stripcull.py mesh sidecar ex,ey,ez yaw pitch : offline estimate (lane objs 10-15) of rejecting strips BEFORE the
transform. For every level-0 meshlet that passes the runtime's cluster + meshlet frustum tests (25 m, 4:3, 50 deg),
classify each strip as the runtime does after transforming (all corners outside one screen edge or all behind near
-> culled). Report:
  wasted: vertices transformed only for culled strips; strips walked only to be culled.
  G-group variants: the meshlet's strips split (in stored order, or re-sorted spatially offline) into G groups with
  their own boxes; a straddling meshlet tests each group box, transforms the contiguous vertex range covering the
  visible groups' corners (vertices re-numbered by first use in group order, an offline reorder) and walks only the
  visible groups' strips.
Cost model (hw-model per-unit, MODELLED from bench-r101 V3): transform 40 cyc / vertex, walk 80 cyc / strip,
group box test 100 cyc, 200 MHz."""
import sys, math, os
import numpy as np
import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from r4im_pkg import Pkg
p = Pkg(sys.argv[1], sys.argv[2])
eye = np.array([float(x) for x in sys.argv[3].split(',')])
yaw, pitch = math.radians(float(sys.argv[4])), math.radians(float(sys.argv[5]))
FAR, NEAR, FOVY, asp = 25000.0, 100.0, math.radians(50), 4 / 3
fwd = np.array([math.sin(yaw) * math.cos(pitch), math.sin(pitch), math.cos(yaw) * math.cos(pitch)])
right = np.cross(fwd, [0, 1, 0]); right /= np.linalg.norm(right); up = np.cross(right, fwd)
f = 1 / math.tan(FOVY / 2)
def clip(P):
    d = P - eye; return (d @ right) * f / asp, (d @ up) * f, d @ fwd
def box_vis(lo, hi):
    c = np.array([[hi[0] if b & 1 else lo[0], hi[1] if b & 2 else lo[1], hi[2] if b & 4 else lo[2]] for b in range(8)])
    x, y, z = clip(c)
    if z.max() < NEAR or z.min() > FAR: return False
    if np.all(x > z) or np.all(x < -z) or np.all(y > z) or np.all(y < -z): return False
    return True
def box_inside(lo, hi):
    c = np.array([[hi[0] if b & 1 else lo[0], hi[1] if b & 2 else lo[1], hi[2] if b & 4 else lo[2]] for b in range(8)])
    x, y, z = clip(c)
    return z.min() > NEAR and z.max() < FAR and np.all(np.abs(x) < z) and np.all(np.abs(y) < z)
def strip_culled(w):
    x, y, z = clip(w)
    return bool(np.all(z < NEAR) or np.all(x > z) or np.all(x < -z) or np.all(y > z) or np.all(y < -z))
lets = []
for pi, part, c, ps, cull, lo, hi in p.iter_clusters():
    if not box_vis(lo, hi): continue
    M = p.wq(p.placements[pi]); cl = p.clusters[c]; fm, mc, _ = p.levels[cl['first_level']]
    for li in range(fm, fm + mc):
        L = p.lets[li]; fs = p.o_strip + L['first_strip']
        if L['sc'] & 0x8000:
            off = np.frombuffer(p.m, dtype='<u2', count=L['vc'], offset=fs); cn = p.verts[L['first_vertex'] + off.astype(np.int64)]; s = fs + 2 * L['vc']
        else:
            cn = p.verts[L['first_vertex']:L['first_vertex'] + L['vc']]; s = fs
        w = cn[:, :3].astype(np.float64) @ M[:, :3].T + M[:, 3]
        if not box_vis(w.min(0), w.max(0)): continue
        end = s + L['strip_bytes']; strips = []
        while s < end:
            n = p.m[s]; idx = list(p.m[s + 1:s + 1 + n]); s += 1 + n
            strips.append(idx)
        lets.append((w, strips, box_inside(w.min(0), w.max(0))))
V = sum(len(w) for w, _, _ in lets); S = sum(len(st) for _, st, _ in lets)
wasted_v = wasted_s = 0
for w, st, ins in lets:
    cul = [strip_culled(w[i]) for i in st]
    used = set(); [used.update(i) for i, c in zip(st, cul) if not c]
    wasted_v += len(w) - len(used); wasted_s += sum(cul)
print('meshlets %d (inside %d) vertices %d strips %d; culled strips %d (%.0f%%); vertices only in culled strips %d (%.0f%%)' % (
    len(lets), sum(1 for l in lets if l[2]), V, S, wasted_s, 100 * wasted_s / S, wasted_v, 100 * wasted_v / V))
base = (V * 40 + S * 80) / 200e3
print('base model: transform+walk %.2f ms' % base)
for SORT in (False, True):
    for G in (2, 4, 8):
        tv = ts = tests = 0
        for w, st, ins in lets:
            if ins:  # wholly inside: no group tests, everything drawn
                tv += len(w); ts += len(st); continue
            order = st
            if SORT:  # offline: sort strips by centroid along the meshlet's longest axis, then chunk
                ext = w.max(0) - w.min(0); ax = int(np.argmax(ext))
                order = sorted(st, key=lambda i: w[i][:, ax].mean())
            k = max(1, math.ceil(len(order) / G)); groups = [order[i:i + k] for i in range(0, len(order), k)]
            tests += len(groups)
            # offline vertex renumbering by first use in group order
            rank = {}
            for g in groups:
                for i in g:
                    for v in i:
                        rank.setdefault(v, len(rank))
            vis = [g for g in groups if box_vis(np.min([w[i].min(0) for i in g], 0), np.max([w[i].max(0) for i in g], 0))]
            if vis:
                rs = [rank[v] for g in vis for i in g for v in i]
                tv += max(rs) - min(rs) + 1
                ts += sum(len(g) for g in vis)
        ms = (tv * 40 + ts * 80 + tests * 100) / 200e3
        print('%s G=%d: transformed %d (%.0f%%) walked %d (%.0f%%) group tests %d -> model %.2f ms (saves %.2f)' % (
            'sorted' if SORT else 'stored', G, tv, 100 * tv / V, ts, 100 * ts / S, tests, ms, base - ms))
