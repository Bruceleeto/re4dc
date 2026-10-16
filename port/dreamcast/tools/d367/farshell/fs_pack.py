"""fs_pack.py <work dir> <room hex, e.g. 101> <out far-shell.fsh>: shell.npz (fs_blender.py material mode) -> FSH1.

FSH1 (little endian; runtime platform/far_shell.inc):
  header 32: 'FSH1', u32 version 1, groups, materials, vertices, strip_bytes, crc32(everything after the header), room
  materials x16: u32 crc, fnv; u16 width, height; u32 0            (the world texture keys; pass 0 = opaque header)
  groups x64: f32 lo[3], hi[3] (world mm box), origin[3], scale (position = origin + i16 x scale), ub, vb (uv base);
              u32 first_vertex; u16 vcount (<= 256), material; u32 first_strip, strip_bytes   (sorted by material)
  vertices x12: i16 x, y, z; u16 rgb565 (prelit colour); i16 u, v (uv = base + i / 2048)
  strips: per group, [n][n vertex indices (u8, group-local)]...  (n >= 3, triangle strips, culling off)
Groups = (material, XZ cell) split so that no group has more than 256 vertices.
"""
import json, struct, sys, zlib
from pathlib import Path
import numpy as np

work, room, out = Path(sys.argv[1]), int(sys.argv[2], 16), Path(sys.argv[3])
UV_TOL = float(sys.argv[4]) if len(sys.argv) > 4 else 0.03
S = np.load(work / "shell.npz")
tex = json.loads((work / "extract.json").read_text())["textures"]
pos, tri, uv, col, key, piece = S["pos"], S["tri"], S["uv"], S["col"], S["key"], S["piece"]
mkeys = sorted({(int(k[0]), int(k[1])) for k in key})
midx = {k: i for i, k in enumerate(mkeys)}
fmat = np.array([midx[(int(k[0]), int(k[1]))] for k in key])


def rgb565(c):
    c = np.clip(np.rint(np.asarray(c) * 255), 0, 255).astype(int)
    return ((c[0] * 31 + 127) // 255) << 11 | ((c[1] * 63 + 127) // 255) << 5 | ((c[2] * 31 + 127) // 255)


def stripify(tris):
    """Greedy strips over triangles given as corner-id triples; returns [[corner ids]] (winding free: culling off)."""
    edge = {}
    for t, (a, b, c) in enumerate(tris):
        for e in ((a, b), (b, c), (c, a)):
            edge.setdefault(frozenset(e), []).append(t)
    used = [False] * len(tris)
    strips = []
    for t0 in range(len(tris)):
        if used[t0]:
            continue
        used[t0] = True
        a, b, c = tris[t0]
        s = [a, b, c]
        while True:   # extend over the edge (s[-2], s[-1])
            nxt = None
            for t in edge.get(frozenset((s[-2], s[-1])), []):
                if not used[t]:
                    nxt = t
                    break
            if nxt is None or len(s) >= 250:
                break
            used[nxt] = True
            third = [x for x in tris[nxt] if x not in (s[-2], s[-1])]
            if len(third) != 1:
                break
            s.append(third[0])
        strips.append(s)
    return strips


groups, verts, strip_bytes = [], [], bytearray()
order = sorted(set(zip(fmat.tolist(), piece.tolist())))
for m, pc in order:
    faces = np.where((fmat == m) & (piece == pc))[0]
    # split into chunks of <= 256 unique corners
    chunk, corners = [], {}
    chunks = []
    bypos = {}
    for f in faces:
        ids = []
        for k in range(3):
            # a corner joins an existing one of the same position when its UV is within UV_TOL (consistent mapping
            # across the shared edge): strips can then share it
            pid_ = int(tri[f, k])
            u_, v_ = float(uv[f, k, 0]), float(uv[f, k, 1])
            ck = None
            for c in bypos.get(pid_, []):
                if abs(c[1] - u_) < UV_TOL and abs(c[2] - v_) < UV_TOL:
                    ck = c
                    break
            if ck is None:
                ck = (pid_, round(u_, 4), round(v_, 4), rgb565(col[f, k]))
                bypos.setdefault(pid_, []).append(ck)
            ids.append(ck)
        new = [c for c in ids if c not in corners]
        if len(corners) + len(set(new)) > 256:
            chunks.append((chunk, corners))
            chunk, corners = [], {}
        for c in ids:
            if c not in corners:
                corners[c] = len(corners)
        chunk.append(tuple(corners[c] for c in ids))
    if chunk:
        chunks.append((chunk, corners))
    for ctris, cmap in chunks:
        clist = sorted(cmap, key=lambda c: cmap[c])
        P = pos[[c[0] for c in clist]]
        U = np.array([[c[1], c[2]] for c in clist])
        lo, hi = P.min(0), P.max(0)
        ext = float((hi - lo).max())
        scale = max(ext / 32767.0, 1e-3)
        q = np.rint((P - lo) / scale).astype(int)
        assert q.max() <= 32767
        base = np.floor(U.mean(0))
        uq = np.rint((U - base) * 2048).astype(int)
        uq = np.clip(uq, -32768, 32767)
        first = len(verts)
        for i, c in enumerate(clist):
            verts.append(struct.pack("<3hH2h", *q[i], c[3], *uq[i]))
        s0 = len(strip_bytes)
        for s in stripify(ctris):
            strip_bytes += bytes([len(s)] + s)
        groups.append(struct.pack("<12fIHHII", *lo, *hi, *lo, scale, *base, first, len(clist), m,
                                  s0, len(strip_bytes) - s0))
mats = b"".join(struct.pack("<2I2HI", k[0], k[1], tex["%08x-%08x" % k]["w"], tex["%08x-%08x" % k]["h"], 0) for k in mkeys)
body = mats + b"".join(groups) + b"".join(verts) + bytes(strip_bytes)
head = struct.pack("<4s7I", b"FSH1", 1, len(groups), len(mkeys), len(verts), len(strip_bytes), zlib.crc32(body), room)
out.write_bytes(head + body)
rep = dict(room="r%03x" % room, bytes=len(head) + len(body), groups=len(groups), materials=len(mkeys), vertices=len(verts),
           strip_bytes=len(strip_bytes), triangles=int(len(tri)))
(work / "pack.json").write_text(json.dumps(rep, indent=1))
print(json.dumps(rep))
