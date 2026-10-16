"""fs_uvaffine.py <work dir> [max stretch] [max angle deg] [--cell mm]: shared shell UVs by one planar mapping per
(texture, 12 m cell, dominant axis) (lane farshell16 vertex cut, 10-16).

fs_blender.py gives every shell triangle the UV plane of the one source triangle under it, so neighbours almost never
agree at a shared corner (r101: 14k corners for 6k triangles). Here the triangles of one texture in one cell that face
the same way (dominant normal axis) share one affine map uv = J p + c, fitted to their own mappings' edge vectors (phase
free: integer tile offsets and per-triangle UV offsets do not matter). A triangle takes the shared map only when it
keeps its own texture scale and direction: every edge's texel vector within `max stretch` in length and `max angle`
in direction of its own mapping (the tile's phase may move, which repeat-wrapped tiling textures hide); otherwise it
keeps its own UVs. Corners of triangles on the same shared map merge in fs_pack.py.
Writes shell.npz (original kept as shell-own.npz) and uvaffine.json."""
import json, shutil, sys
from pathlib import Path
import numpy as np

args = sys.argv[1:]
CELL = 12000.0
if "--cell" in args:
    i = args.index("--cell"); CELL = float(args[i + 1]); args = args[:i] + args[i + 2:]
work = Path(args[0])
MS = float(args[1]) if len(args) > 1 else 1.25   # 0 = every triangle takes its group map (forced)
MA = np.radians(float(args[2]) if len(args) > 2 else 15.0)
if not (work / "shell-own.npz").exists():
    shutil.copy(work / "shell.npz", work / "shell-own.npz")
S = dict(np.load(work / "shell-own.npz"))
tex = json.loads((work / "extract.json").read_text())["textures"]
pos, tri, uv, key = S["pos"], S["tri"], S["uv"], S["key"]
nf = len(tri)
P = pos[tri]                                   # (nf, 3, 3) mm
size = np.array([[tex["%08x-%08x" % (int(k[0]), int(k[1]))]["w"], tex["%08x-%08x" % (int(k[0]), int(k[1]))]["h"]]
                 for k in key], float)
n = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0])
axis = np.abs(n).argmax(1)
cen = P.mean(1)
cxz = np.floor(cen[:, [0, 2]] / CELL).astype(int)
groups = {}
for f in range(nf):
    groups.setdefault((int(key[f, 0]), int(key[f, 1]), int(cxz[f, 0]), int(cxz[f, 1]), int(axis[f])), []).append(f)
new = uv.copy()
took = 0
nmaps = 0
for g, F in groups.items():
    F = np.array(F)
    # edges (3 per triangle): position deltas E (m, 3) and own UV deltas D (m, 2)
    E = np.concatenate([P[F, (k + 1) % 3] - P[F, k] for k in range(3)])
    D = np.concatenate([uv[F, (k + 1) % 3] - uv[F, k] for k in range(3)])
    # least squares J (2 x 3) with J E^T ~ D^T; the dropped axis has no extent on these faces, so regularise it
    A = E.T @ E + np.eye(3) * 1e-3 * np.trace(E.T @ E) / 3
    J = np.linalg.solve(A, E.T @ D).T
    ok = np.zeros(len(F), bool)
    for i, f in enumerate(F):
        e = np.array([P[f, (k + 1) % 3] - P[f, k] for k in range(3)])
        do = np.array([uv[f, (k + 1) % 3] - uv[f, k] for k in range(3)]) * size[f]
        dj = (e @ J.T) * size[f]
        lo_, lj = np.linalg.norm(do, axis=1), np.linalg.norm(dj, axis=1)
        if np.any(lo_ < 1e-6):
            continue
        r = lj / lo_
        cosang = (do * dj).sum(1) / np.maximum(lo_ * lj, 1e-9)
        ok[i] = MS == 0 or bool(np.all((r <= MS) & (r >= 1 / MS) & (cosang >= np.cos(MA))))
    if not ok.any():
        continue
    nmaps += 1
    f0 = F[ok][0]
    c = uv[f0, 0] - J @ P[f0, 0]                # phase from one member (the tile phase is free)
    for f in F[ok]:
        new[f] = P[f] @ J.T + c
    took += int(ok.sum())
S["uv"] = new
np.savez_compressed(work / "shell.npz", **S)
rep = dict(max_stretch=MS, max_angle_deg=float(np.degrees(MA)), cell=CELL, triangles=int(nf), shared_triangles=took,
           maps=nmaps, groups=len(groups))
(work / "uvaffine.json").write_text(json.dumps(rep, indent=1))
print(json.dumps(rep))
