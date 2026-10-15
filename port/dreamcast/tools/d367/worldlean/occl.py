"""Offline r101 world occlusion / backface estimate for one eye (lane objs, 2026-10-14).
usage: occl.py mesh sidecar ex,ey,ez yaw_deg pitch_deg [W H]
Rasterizes every opaque (pass 0) level-0 triangle within 25 m into a coarse z-buffer (one-sided parts: front faces only),
then classifies each level-0 meshlet in the frustum (25 m) as: visible / hidden (its AABB's nearest depth is behind the
z-buffer everywhere in its screen rect) / backfacing (one-sided part, every triangle faces away from the eye).
Counts meshlets and their vertices (the transform work)."""
import sys, math
import numpy as np
import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from r4im_pkg import Pkg

p = Pkg(sys.argv[1], sys.argv[2])
eye = np.array([float(x) for x in sys.argv[3].split(',')])
yaw, pitch = math.radians(float(sys.argv[4])), math.radians(float(sys.argv[5]))
W, H = (int(sys.argv[6]), int(sys.argv[7])) if len(sys.argv) > 7 else (160, 120)
EXACT = True
FAR, NEAR, FOVY = 25000.0, 100.0, math.radians(50)
fwd = np.array([math.sin(yaw) * math.cos(pitch), math.sin(pitch), math.cos(yaw) * math.cos(pitch)])
right = np.cross(fwd, [0, 1, 0]); right /= np.linalg.norm(right); up = np.cross(right, fwd)
f = 1 / math.tan(FOVY / 2); asp = W / H


def proj(P):
    d = P - eye
    x, y, z = d @ right, d @ up, d @ fwd
    return x, y, z


def to_screen(x, y, z):
    zs = np.maximum(z, NEAR)
    return (x * f / asp / zs * 0.5 + 0.5) * W, (0.5 - y * f / zs * 0.5) * H


zb = np.full((H, W), np.inf)
lets = []  # (meshlet index, vertices, aabb lo, hi, tris world, one-sided)
for pi, part, c, ps, cull, lo, hi in p.iter_clusters():
    # frustum + 25 m test on the cluster box (conservative: 8 corners)
    corners = np.array([[hi[0] if b & 1 else lo[0], hi[1] if b & 2 else lo[1], hi[2] if b & 4 else lo[2]] for b in range(8)])
    x, y, z = proj(corners)
    if z.max() < NEAR or z.min() > FAR:
        continue
    zc = np.maximum(z, NEAR)
    sx, sy = x * f / asp / zc, y * f / zc
    if sx.max() < -1 or sx.min() > 1 or sy.max() < -1 or sy.min() > 1:
        if z.min() > NEAR:
            continue
    pl = p.placements[pi]; M = p.wq(pl); cl = p.clusters[c]
    fm, mc, _ = p.levels[cl['first_level']]
    for li in range(fm, fm + mc):
        cn, tris = p.let_tris(li)
        w = cn[:, :3].astype(np.float64) @ M[:, :3].T + M[:, 3]
        T = w[np.array(tris)] if tris else np.zeros((0, 3, 3))
        lets.append((li, p.lets[li]["vc"], w.min(0), w.max(0), T, cull != 0, ps, pi))

print('meshlets in 25 m frustum (cluster test):', len(lets), 'vertices', sum(l[1] for l in lets))

# raster opaque occluders
nt = 0
for li, vc, lo, hi, T, one, ps, pi in lets:
    if ps != 0 or not len(T):
        continue
    for t in T:
        n = np.cross(t[1] - t[0], t[2] - t[0])
        if one and np.dot(n, eye - t[0]) <= 0:
            continue
        x, y, z = proj(t)
        if z.min() < NEAR or z.min() > FAR:
            continue  # skip near-clipped triangles (conservative: they do not occlude)
        sx, sy = to_screen(x, y, z)
        x0, x1 = max(int(math.floor(sx.min())), 0), min(int(math.ceil(sx.max())), W - 1)
        y0, y1 = max(int(math.floor(sy.min())), 0), min(int(math.ceil(sy.max())), H - 1)
        if x0 > x1 or y0 > y1:
            continue
        X, Y = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        (ax, bx, cx), (ay, by, cy) = sx, sy
        den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(den) < 1e-9:
            continue
        l1 = ((by - cy) * (X - cx) + (cx - bx) * (Y - cy)) / den
        l2 = ((cy - ay) * (X - cx) + (ax - cx) * (Y - cy)) / den
        l3 = 1 - l1 - l2
        inside = (l1 >= 0) & (l2 >= 0) & (l3 >= 0)
        if not inside.any():
            continue
        zz = 1.0 / (l1 / z[0] + l2 / z[1] + l3 / z[2]) if EXACT else np.full(l1.shape, np.max(z))
        sub = zb[y0:y1 + 1, x0:x1 + 1]
        sub[inside] = np.minimum(sub[inside], zz[inside] * 1.02 + 50)
        nt += 1
print('occluder triangles rasterized', nt, 'covered px %.0f%%' % (100 * np.isfinite(zb).mean()))

vis = hid = back = 0; vv = hv = bv = 0; offs = 0; ov = 0
for li, vc, lo, hi, T, one, ps, pi in lets:
    corners = np.array([[hi[0] if b & 1 else lo[0], hi[1] if b & 2 else lo[1], hi[2] if b & 4 else lo[2]] for b in range(8)])
    x, y, z = proj(corners)
    if z.max() < NEAR or z.min() > FAR:
        offs += 1; ov += vc; continue
    zc = np.maximum(z, NEAR)
    sxn, syn = x * f / asp / zc, y * f / zc
    if z.min() > NEAR and (sxn.max() < -1 or sxn.min() > 1 or syn.max() < -1 or syn.min() > 1):
        offs += 1; ov += vc; continue
    if one and len(T):
        n = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
        if np.all(np.einsum('ij,ij->i', n, eye - T[:, 0]) <= 0):
            back += 1; bv += vc; continue
    if z.min() > NEAR:
        sx, sy = to_screen(x, y, z)
        x0, x1 = max(int(math.floor(sx.min())), 0), min(int(math.ceil(sx.max())), W - 1)
        y0, y1 = max(int(math.floor(sy.min())), 0), min(int(math.ceil(sy.max())), H - 1)
        if x0 <= x1 and y0 <= y1 and np.all(zb[y0:y1 + 1, x0:x1 + 1] < z.min()):
            hid += 1; hv += vc; continue
    vis += 1; vv += vc
tot = vis + hid + back
print('meshlets past the per-meshlet frustum test: %d (vertices %d); off-frustum %d (%d v)' % (tot, vv + hv + bv, offs, ov))
print('  visible %d (%d v), hidden by z-buffer %d (%d v, %.0f%%), all-backfacing %d (%d v, %.0f%%)' % (
    vis, vv, hid, hv, 100 * hv / max(vv + hv + bv, 1), back, bv, 100 * bv / max(vv + hv + bv, 1)))
# placement level: a placement is hidden only if every one of its frustum meshlets is hidden (z-buffer) or off-frustum
import collections
st = collections.defaultdict(lambda: [0, 0])  # pi -> [visible vertices, hidden vertices]
for li, vc, lo, hi, T, one, ps, pi in lets:
    corners = np.array([[hi[0] if b & 1 else lo[0], hi[1] if b & 2 else lo[1], hi[2] if b & 4 else lo[2]] for b in range(8)])
    x, y, z = proj(corners)
    if z.max() < NEAR or z.min() > FAR: continue
    zc = np.maximum(z, NEAR); sxn, syn = x * f / asp / zc, y * f / zc
    if z.min() > NEAR and (sxn.max() < -1 or sxn.min() > 1 or syn.max() < -1 or syn.min() > 1): continue
    hidden = False
    if z.min() > NEAR:
        sx, sy = to_screen(x, y, z)
        x0, x1 = max(int(math.floor(sx.min())), 0), min(int(math.ceil(sx.max())), W - 1)
        y0, y1 = max(int(math.floor(sy.min())), 0), min(int(math.ceil(sy.max())), H - 1)
        hidden = x0 <= x1 and y0 <= y1 and np.all(zb[y0:y1 + 1, x0:x1 + 1] < z.min())
    st[pi][1 if hidden else 0] += vc
hv = sum(h for v, h in st.values() if v == 0); tv = sum(v + h for v, h in st.values())
print('placement-level: hidden placements %d of %d, vertices %d of %d (%.1f%%)' % (sum(1 for v, h in st.values() if v == 0 and h), len(st), hv, tv, 100 * hv / max(tv, 1)))
