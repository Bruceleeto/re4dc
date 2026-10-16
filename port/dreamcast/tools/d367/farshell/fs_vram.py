"""fs_vram.py <work dir> <tex.pak> [cut mm] [loose tex dir]: VRAM of the room's world textures by how close the player
can get to them (lane farshell16). For every texture key: the minimum distance from any reachable eye (eyes.npy) to
any of its world triangles (sampled at corners, edge midpoints, centroid and 6 interior points). Keys whose every
triangle stays beyond the cut are "far-only": Short draws them only through the far shell, so they are the textures a
far-shell proxy (small VQ / palettised stand-in) could replace. Size = the re4tex payload (what the PVR holds).
Also lists the shell's materials (shell.npz keys) and which of them are far-only."""
import json, struct, sys
from pathlib import Path
import numpy as np
import fs_common as fc

work, pak = Path(sys.argv[1]), sys.argv[2]
cut = float(sys.argv[3]) if len(sys.argv) > 3 else 12500.0
P = fc.TexPak(pak)
if len(sys.argv) > 4:
    P.loose = sys.argv[4]
W = np.load(work / "world.npz")
E = np.load(work / "eyes.npy")
T = W["P"]
bary = np.array([[1, 0, 0], [0, 1, 0], [0, 0, 1], [.5, .5, 0], [0, .5, .5], [.5, 0, .5], [1 / 3, 1 / 3, 1 / 3],
                 [.6, .2, .2], [.2, .6, .2], [.2, .2, .6], [.4, .4, .2], [.2, .4, .4], [.4, .2, .4]])
pts = np.einsum("sk,nkd->nsd", bary, T)
flat = pts.reshape(-1, 3)
d = np.empty(len(flat))
e2 = (E * E).sum(1)
for i in range(0, len(flat), 20000):   # nearest eye per sample point (numpy, chunked)
    q = flat[i:i + 20000]
    d[i:i + 20000] = np.sqrt(np.maximum((q * q).sum(1)[:, None] - 2 * q @ E.T + e2[None], 0).min(1))
dmin = d.reshape(len(T), -1).min(1)
keys = [tuple(int(x) for x in k) for k in W["key"]]
best = {}
for k, dm in zip(keys, dmin):
    best[k] = min(best.get(k, 1e18), float(dm))


def size(k):
    try:
        b = P.get(k)
    except KeyError:
        return 0
    return len(b)


S = np.load(work / "shell.npz")
shell = {(int(k[0]), int(k[1])) for k in S["key"]}
rep = dict(cut=cut, keys=len(best), bytes_all=0, far_only=0, far_only_bytes=0, shell_keys=len(shell),
           shell_bytes=0, shell_far_only=0, shell_far_only_bytes=0, far_only_list=[])
for k, dm in sorted(best.items(), key=lambda x: -x[1]):
    s = size(k)
    rep["bytes_all"] += s
    if k in shell:
        rep["shell_bytes"] += s
    if dm > cut:
        rep["far_only"] += 1
        rep["far_only_bytes"] += s
        rep["far_only_list"].append(["%08x-%08x" % k, round(dm), s, k in shell])
        if k in shell:
            rep["shell_far_only"] += 1
            rep["shell_far_only_bytes"] += s
(work / "vram.json").write_text(json.dumps(rep, indent=1))
print(json.dumps({k: v for k, v in rep.items() if k != "far_only_list"}))
for row in rep["far_only_list"][:40]:
    print(row)
