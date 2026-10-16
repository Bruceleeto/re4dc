"""fs_uvfield.py <work dir> [tol texels] [--shift]: continuous shell UVs (lane farshell16, 10-16 vertex cut).

fs_blender.py gives every shell triangle the UV plane of ONE source triangle (the one under it), extended to its
corners, so the corners of one shell vertex usually carry different UVs and fs_pack.py must split them (r101: 14k
corners for 6k triangles; 8.7k distinct (vertex, material, cell)). Here every (vertex, texture) gets ONE UV: the
source UV at the closest point of the source surface with that texture (the world's own mapping, continuous where
the source mesh is). A shell triangle takes the field UVs when they reproduce its own mapping within `tol` texels at
all three corners (the same texels, so the same look); otherwise it keeps its own UVs (and its corners stay split).
--shift also accepts a whole-texture integer offset (repeat-wrapped textures only; off by default).
Writes shell.npz (the original is kept as shell-own.npz) and uvfield.json."""
import json, shutil, sys
from pathlib import Path
import numpy as np

work = Path(sys.argv[1])
tol = float(sys.argv[2]) if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else 2.0
shift = "--shift" in sys.argv
stretch = float(sys.argv[sys.argv.index("--stretch") + 1]) if "--stretch" in sys.argv else 0.0
keepbad = float(sys.argv[sys.argv.index("--keep-bad") + 1]) if "--keep-bad" in sys.argv else 0.0
if not (work / "shell-own.npz").exists():
    shutil.copy(work / "shell.npz", work / "shell-own.npz")
S = dict(np.load(work / "shell-own.npz"))
W = np.load(work / "world.npz")
tex = json.loads((work / "extract.json").read_text())["textures"]
pos, tri, uv, key = S["pos"], S["tri"], S["uv"], S["key"]
P, UV, WK = W["P"], W["UV"], W["key"]


def closest(p, A, B, C):
    """Closest points on triangles (A, B, C: (n,3)) to point p; returns barycentrics (n,3) and distances."""
    ab, ac, ap = B - A, C - A, p - A
    d1, d2 = (ab * ap).sum(1), (ac * ap).sum(1)
    bp = p - B
    d3, d4 = (ab * bp).sum(1), (ac * bp).sum(1)
    cp = p - C
    d5, d6 = (ab * cp).sum(1), (ac * cp).sum(1)
    vc = d1 * d4 - d3 * d2
    vb = d5 * d2 - d1 * d6
    va = d3 * d6 - d5 * d4
    n = len(A)
    bc = np.zeros((n, 3))
    den = va + vb + vc
    den = np.where(np.abs(den) < 1e-12, 1e-12, den)
    v, w = vb / den, vc / den
    bc[:] = np.stack([1 - v - w, v, w], 1)
    # region tests (Ericson 5.1.5), applied in reverse priority so the earlier tests win
    m = (va <= 0) & ((d4 - d3) >= 0) & ((d5 - d6) >= 0)
    t = np.clip((d4 - d3) / np.maximum((d4 - d3) + (d5 - d6), 1e-12), 0, 1)
    bc[m] = np.stack([np.zeros(m.sum()), 1 - t[m], t[m]], 1)
    m = (vb <= 0) & (d2 >= 0) & (d6 <= 0)
    t = d2 / np.where(np.abs(d2 - d6) < 1e-12, 1e-12, d2 - d6)
    bc[m] = np.stack([1 - t[m], np.zeros(m.sum()), t[m]], 1)
    m = (vc <= 0) & (d1 >= 0) & (d3 <= 0)
    t = d1 / np.where(np.abs(d1 - d3) < 1e-12, 1e-12, d1 - d3)
    bc[m] = np.stack([1 - t[m], t[m], np.zeros(m.sum())], 1)
    m = (d6 >= 0) & (d5 <= d6)
    bc[m] = [0, 0, 1]
    m = (d3 >= 0) & (d4 <= d3)
    bc[m] = [0, 1, 0]
    m = (d1 <= 0) & (d2 <= 0)
    bc[m] = [1, 0, 0]
    q = bc[:, :1] * A + bc[:, 1:2] * B + bc[:, 2:] * C
    return bc, np.linalg.norm(q - p, axis=1)


bykey = {}
for i, k in enumerate(WK):
    bykey.setdefault((int(k[0]), int(k[1])), []).append(i)
bykey = {k: np.array(v) for k, v in bykey.items()}
cent = P.mean(1)
field = {}
for f in range(len(tri)):
    k = (int(key[f, 0]), int(key[f, 1]))
    for c in range(3):
        vid = int(tri[f, c])
        if (vid, k) in field:
            continue
        ids = bykey[k]
        p = pos[vid]
        near = ids[np.argsort(((cent[ids] - p) ** 2).sum(1))[:32]]
        bc, dist = closest(p, P[near, 0], P[near, 1], P[near, 2])
        j = int(np.argmin(dist))
        field[(vid, k)] = bc[j] @ UV[near[j]]
size = np.array([[tex["%08x-%08x" % (int(k[0]), int(k[1]))]["w"], tex["%08x-%08x" % (int(k[0]), int(k[1]))]["h"]]
                 for k in key], float)
new = uv.copy()
took = shifted = 0
for f in range(len(tri)):
    k = (int(key[f, 0]), int(key[f, 1]))
    F = np.array([field[(int(tri[f, c]), k)] for c in range(3)])
    d = uv[f] - F
    s = np.round(d.mean(0)) if shift else np.zeros(2)
    res = np.abs((d - s) * size[f]).max()
    ok = res <= tol
    if not ok and stretch:
        # same texture scale and orientation: every edge's texel length within [1/stretch, stretch] of the
        # triangle's own mapping and the same winding in texture space (only the texture's phase moves)
        eo = (np.roll(uv[f], -1, 0) - uv[f]) * size[f]
        ef = (np.roll(F, -1, 0) - F) * size[f]
        lo_, lf = np.linalg.norm(eo, axis=1), np.linalg.norm(ef, axis=1)
        r = lf / np.maximum(lo_, 1e-6)
        ao = eo[0, 0] * eo[1, 1] - eo[0, 1] * eo[1, 0]
        af = ef[0, 0] * ef[1, 1] - ef[0, 1] * ef[1, 0]
        ok = bool(np.all((r >= 1 / stretch) & (r <= stretch)) and ao * af > 0)
    if keepbad:
        eo = (np.roll(uv[f], -1, 0) - uv[f]) * size[f]
        ef = (np.roll(F, -1, 0) - F) * size[f]
        r = np.linalg.norm(ef, axis=1) / np.maximum(np.linalg.norm(eo, axis=1), 1e-6)
        ao = eo[0, 0] * eo[1, 1] - eo[0, 1] * eo[1, 0]
        af = ef[0, 0] * ef[1, 1] - ef[0, 1] * ef[1, 0]
        ok = bool(np.all((r >= 1 / keepbad) & (r <= keepbad)) and ao * af > 0)
    if ok:
        new[f] = F if not s.any() else F + 0   # field UVs: shared corners merge; a shift is absorbed by repeat wrap
        took += 1
        shifted += int(s.any())
S["uv"] = new
np.savez_compressed(work / "shell.npz", **S)
rep = dict(tol_texels=tol, shift=shift, stretch=stretch, keep_bad=keepbad, triangles=int(len(tri)), field_triangles=took, shifted=shifted,
           field_points=len(field))
(work / "uvfield.json").write_text(json.dumps(rep, indent=1))
print(json.dumps(rep))
