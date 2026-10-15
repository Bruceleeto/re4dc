"""morton.py mesh sidecar ex,ey,ez yaw pitch : offline estimate (lane objs 10-15) of re-chunking each LOD cluster's
level-0 strips into meshlets in Morton (Z-order) order of the strip centroids, against the stored meshlets, with and
without PS2_STRIP_GROUPS-style groups (kd split, G=4). MODELLED cost: transform 40 cyc/vertex, walk 80 cyc/strip,
meshlet test 100 cyc, group test 100 cyc, 200 MHz. Meshlet / group frustum tests as the runtime (25 m, 4:3, 50 deg).
A Morton meshlet takes the cluster's own meshlet limits (max corners and strips of its stored meshlets); a corner shared
by strips of two new meshlets is duplicated (counted)."""
import sys, os, math
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
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
def cls(lo, hi):
    """0 outside, 1 crossing, 2 inside"""
    c = np.array([[hi[0] if b & 1 else lo[0], hi[1] if b & 2 else lo[1], hi[2] if b & 4 else lo[2]] for b in range(8)])
    x, y, z = clip(c)
    if z.max() < NEAR or z.min() > FAR: return 0
    if np.all(x > z) or np.all(x < -z) or np.all(y > z) or np.all(y < -z): return 0
    return 2 if (z.min() > NEAR and z.max() < FAR and np.all(np.abs(x) < z) and np.all(np.abs(y) < z)) else 1
def morton(q):
    def spread(v):
        v = int(v) & 0x3ff; r = 0
        for b in range(10): r |= ((v >> b) & 1) << (3 * b)
        return r
    return spread(q[0]) | spread(q[1]) << 1 | spread(q[2]) << 2
def cost(meshlets, G):
    """meshlets: list of (W corners world, strips as index lists). -> (vertices, strips, tests)"""
    tv = ts = tests = 0
    for w, st in meshlets:
        tests += 1
        k = cls(w.min(0), w.max(0))
        if k == 0: continue
        if k == 2 or G == 1: tv += len(w); ts += len(st); continue
        ext = w.max(0) - w.min(0); ax = int(np.argmax(ext))
        order = sorted(st, key=lambda i: w[i][:, ax].mean())
        n = max(1, math.ceil(len(order) / G)); groups = [order[i:i + n] for i in range(0, len(order), n)]
        tests += len(groups); rank = {}
        for g in groups:
            for i in g:
                for v in i: rank.setdefault(v, len(rank))
        vis = [g for g in groups if cls(np.min([w[i].min(0) for i in g], 0), np.max([w[i].max(0) for i in g], 0))]
        if vis:
            rs = [rank[v] for g in vis for i in g for v in i]
            tv += max(rs) - min(rs) + 1; ts += sum(len(g) for g in vis)
    return tv, ts, tests
orig = []; mort = []; dup = [0, 0]
for pi, part, c, ps, cull, lo, hi in p.iter_clusters():
    if not cls(lo, hi): continue
    M = p.wq(p.placements[pi]); cl = p.clusters[c]; fm, mc, _ = p.levels[cl['first_level']]
    pool = []; vmax = smax = 0
    for li in range(fm, fm + mc):
        L = p.lets[li]; fs = p.o_strip + L['first_strip']
        if L['sc'] & 0x8000:
            off = np.frombuffer(p.m, dtype='<u2', count=L['vc'], offset=fs); cn = p.verts[L['first_vertex'] + off.astype(np.int64)]; s = fs + 2 * L['vc']
        else:
            cn = p.verts[L['first_vertex']:L['first_vertex'] + L['vc']]; s = fs
        w = cn[:, :3].astype(np.float64) @ M[:, :3].T + M[:, 3]
        end = s + L['strip_bytes']; strips = []
        while s < end:
            n = p.m[s]; idx = list(p.m[s + 1:s + 1 + n]); s += 1 + n; strips.append(idx)
        orig.append((w, strips)); vmax = max(vmax, len(cn)); smax = max(smax, len(strips))
        for idx in strips:
            pool.append(([tuple(cn[i]) for i in idx], [w[i] for i in idx], cn[idx, :3].astype(np.float64).mean(0)))
        dup[0] += len(cn)
    if not pool: continue
    cs = np.array([q[2] for q in pool]); lo3 = cs.min(0); sc = np.maximum(cs.max(0) - lo3, 1e-6)
    keyed = sorted(pool, key=lambda q: morton((q[2] - lo3) / sc * 1023))
    cur_keys = {}; cur_w = []; cur_st = []
    def flush():
        global cur_keys, cur_w, cur_st
        if cur_st: mort.append((np.array(cur_w), cur_st)); dup[1] += len(cur_w)
        cur_keys = {}; cur_w = []; cur_st = []
    for keys, ws, _ in keyed:
        new = len(set(k for k in keys if k not in cur_keys))
        if cur_st and (len(cur_keys) + new > vmax or len(cur_st) + 1 > smax): flush()
        idx = []
        for k, wv in zip(keys, ws):
            if k not in cur_keys: cur_keys[k] = len(cur_w); cur_w.append(wv)
            idx.append(cur_keys[k])
        cur_st.append(idx)
    flush()
print('clusters in view: stored meshlets %d (corners %d), Morton meshlets %d (corners %d)' % (len(orig), dup[0], len(mort), dup[1]))
for name, ms in (('stored', orig), ('morton', mort)):
    for G in (1, 4):
        tv, ts, tests = cost(ms, G)
        print('%s %s: transformed %d walked %d tests %d -> model %.2f ms' % (
            name, 'no groups' if G == 1 else 'G=4', tv, ts, tests, (tv * 40 + ts * 80 + tests * 100) / 200e3))
