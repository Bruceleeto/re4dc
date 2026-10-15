"""sgsim.py mesh sidecar r4sg ex,ey,ez yaw pitch: bench-view estimate of PS2_STRIP_GROUPS with the real group records
(MODELLED: transform 40 cyc/vertex, walk 80 cyc/strip, group test 100 cyc; meshlet frustum as the runtime)."""
import sys, math, struct
import numpy as np
import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from r4im_pkg import Pkg
p = Pkg(sys.argv[1], sys.argv[2]); g = open(sys.argv[3], 'rb').read()
_, _, n, G, _, _, _, _ = struct.unpack_from('<4s7I', g, 0)
eye = np.array([float(x) for x in sys.argv[4].split(',')])
yaw, pitch = math.radians(float(sys.argv[5])), math.radians(float(sys.argv[6]))
FAR, NEAR, FOVY, asp = 25000.0, 100.0, math.radians(50), 4 / 3
fwd = np.array([math.sin(yaw) * math.cos(pitch), math.sin(pitch), math.cos(yaw) * math.cos(pitch)])
right = np.cross(fwd, [0, 1, 0]); right /= np.linalg.norm(right); up = np.cross(right, fwd)
f = 1 / math.tan(FOVY / 2)
def clip(P):
    d = P - eye; return (d @ right) * f / asp, (d @ up) * f, d @ fwd
def corners(lo, hi):
    return np.array([[hi[0] if b & 1 else lo[0], hi[1] if b & 2 else lo[1], hi[2] if b & 4 else lo[2]] for b in range(8)])
def vis(P, far=FAR):
    x, y, z = clip(P)
    if z.max() < NEAR or z.min() > far: return False
    return not (np.all(x > z) or np.all(x < -z) or np.all(y > z) or np.all(y < -z))
def inside(P):
    x, y, z = clip(P)
    return z.min() > NEAR and z.max() < FAR and np.all(np.abs(x) < z) and np.all(np.abs(y) < z)
V0 = S0 = V1 = S1 = T = 0
for pi, part, c, ps, cull, lo, hi in p.iter_clusters():
    if not vis(corners(lo, hi)): continue
    M = p.wq(p.placements[pi]); cl = p.clusters[c]; fm, mc, _ = p.levels[cl['first_level']]
    for li in range(fm, fm + mc):
        L = p.lets[li]
        gb = lambda q: M[:, :3] @ np.array(q, float) + M[:, 3]
        lw = np.array([gb(q) for q in corners(L['bmin'], L['bmax'])])
        if not vis(lw): continue
        V0 += L['vc']; S0 += L['sc'] & 0x7fff
        if inside(lw):
            V1 += L['vc']; S1 += L['sc'] & 0x7fff; continue
        cn, _ = p.let_tris(li)
        fs = p.o_strip + L['first_strip'] + (2 * L['vc'] if L['sc'] & 0x8000 else 0)
        prev = 0; vmin = 999; vmax = -1
        for k in range(G):
            r = struct.unpack_from('<6HHBB', g, 32 + 16 * (li * G + k))
            send, v0, v1 = r[6], r[7], r[8]
            if send == prev: continue
            T += 1
            gw = np.array([gb(q) for q in corners(r[0:3], r[3:6])])
            if vis(gw, 1e9):
                s = fs + prev
                while s < fs + send:
                    nn = p.m[s]; s += 1 + nn; S1 += 1
                vmin = min(vmin, v0); vmax = max(vmax, v1)
            prev = send
        if vmax >= vmin: V1 += vmax - vmin + 1
base = (V0 * 40 + S0 * 80) / 200e3; new = (V1 * 40 + S1 * 80 + T * 100) / 200e3
print('vertices %d -> %d (%.0f%%), strips %d -> %d (%.0f%%), group tests %d; model transform+walk %.2f -> %.2f ms (saves %.2f)' % (
    V0, V1, 100 * V1 / V0, S0, S1, 100 * S1 / S0, T, base, new, base - new))
