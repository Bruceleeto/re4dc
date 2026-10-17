"""fs_eyes.py <room> <rtp> <work dir> [extra x,y,z ...] [--lake STEP]: reachable eye positions (game mm) -> eyes.npy.
Eyes = the PS2 enemy route graph (PTR2, walkable ground) + 1.6 m, plus named extra points (warps), plus with --lake a
grid over the room's large flat translucent triangles (the r10b lake surface the boat moves on) at boat eye height."""
import struct, sys
from pathlib import Path
import numpy as np

room, rtp, work = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
args = sys.argv[4:]
lake = None
dens = None
if "--densify" in args:   # --densify STEP MAXLEN: extra eyes every STEP mm between each route node and its 4 nearest
    i = args.index("--densify")   # neighbours closer than MAXLEN (the player walks between the nodes, not on them)
    dens = (float(args[i + 1]), float(args[i + 2]))
    args = args[:i] + args[i + 3:]
if "--lake" in args:
    i = args.index("--lake")
    lake = float(args[i + 1])
    args = args[:i] + args[i + 2:]
d = rtp.read_bytes()
assert d[:4] == b"PTR2"
n = struct.unpack_from("<H", d, 6)[0]
pts = [np.array(struct.unpack_from("<3f", d, 0x20 + 32 * i)) + (0, 1600, 0) for i in range(n)]
for a in args:
    pts.append(np.array([float(x) for x in a.split(",")]) + (0, 1600, 0))
if lake:
    W = np.load(work / "world.npz")
    Q = W["P"][W["pass_"] == 2]
    nn = np.cross(Q[:, 1] - Q[:, 0], Q[:, 2] - Q[:, 0])
    area = np.linalg.norm(nn, axis=1) / 2
    flat = (np.abs(nn[:, 1]) / np.maximum(np.linalg.norm(nn, axis=1), 1e-9) > 0.99) & (area > 50e6)
    T = Q[flat]
    ys = np.round(T[..., 1].mean(1), -1)
    a2 = area[flat]
    y = max(set(ys.tolist()), key=lambda v: a2[ys == v].sum())   # the water level with the largest area
    T = T[np.abs(T[..., 1].mean(1) - y) < 100]
    lo, hi = T.reshape(-1, 3).min(0), T.reshape(-1, 3).max(0)
    xs, zs = np.meshgrid(np.arange(lo[0], hi[0], lake), np.arange(lo[2], hi[2], lake))
    g = np.stack([xs.ravel(), zs.ravel()], -1)
    inside = np.zeros(len(g), bool)
    for t in T:
        a, b, c = t[0, [0, 2]], t[1, [0, 2]], t[2, [0, 2]]
        def side(p, q, r):
            return (q[0] - p[0]) * (r[:, 1] - p[1]) - (q[1] - p[1]) * (r[:, 0] - p[0])
        s1, s2, s3 = side(a, b, g), side(b, c, g), side(c, a, g)
        inside |= ((s1 >= 0) & (s2 >= 0) & (s3 >= 0)) | ((s1 <= 0) & (s2 <= 0) & (s3 <= 0))
    for x, z in g[inside]:
        pts.append(np.array([x, y + 1600, z]))
    print("lake eyes", int(inside.sum()), "water y", y)
if dens:
    R = np.array(pts)
    D = np.sqrt(((R[:, None] - R[None]) ** 2).sum(-1))
    np.fill_diagonal(D, 1e18)
    add = []
    for a in range(len(R)):
        for b in np.argsort(D[a])[:4]:
            if b > a or a not in np.argsort(D[b])[:4]:
                if D[a, b] < dens[1]:
                    n = int(D[a, b] // dens[0])
                    for t in range(1, n + 1):
                        add.append(R[a] + (R[b] - R[a]) * t / (n + 1))
    pts += add
    print("densified eyes", len(add))
E = np.array(pts)
np.save(work / "eyes.npy", E)
print(room, "eyes", len(E))
