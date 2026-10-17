"""FAR_SHELL offline tools: shared readers (Windows Python, numpy + PIL).

- PS2 world package (R4IM v3 level 0 + R4PW sidecar) -> world-space triangle soup with UV, prelit colour, texture key.
- tex.pak / RE4DCTX texture decode (RGB565 / ARGB1555 / ARGB4444 / PAL4, linear / twiddled / VQ) -> RGBA.
"""
import struct
from pathlib import Path
import sys
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "assetpipe"))   # repo tools/assetpipe/r4im.py
import r4im

HEADER = struct.Struct("<8s10I")
TEXTURE = struct.Struct("<64s8I")


def untwiddle_index(w, h):
    m = min(w, h)

    def spread(v):
        r = np.zeros_like(v)
        for b in range(11):
            r |= (v & (1 << b)) << b
        return r
    y, x = np.mgrid[0:h, 0:w]
    return (spread(y & (m - 1)) | (spread(x & (m - 1)) << 1)) + (x // m) * m * m + (y // m) * m * m


def px16(t, fmt):
    t = t.astype(np.uint32)
    if fmt == 0:
        r, g, b = (t >> 11) & 31, (t >> 5) & 63, t & 31
        return np.stack([r * 255 // 31, g * 255 // 63, b * 255 // 31, np.full_like(r, 255)], -1).astype(np.uint8)
    if fmt == 1:
        a, r, g, b = t >> 15, (t >> 10) & 31, (t >> 5) & 31, t & 31
        return np.stack([r * 255 // 31, g * 255 // 31, b * 255 // 31, a * 255], -1).astype(np.uint8)
    a, r, g, b = t >> 12, (t >> 8) & 15, (t >> 4) & 15, t & 15
    return np.stack([r * 17, g * 17, b * 17, a * 17], -1).astype(np.uint8)


def decode_re4tex(b):
    magic, ver, hsize, tsize, count, toff, doff, dlen, crc, nimg, _ = HEADER.unpack_from(b, 0)
    assert magic == b"RE4DCTX\0", magic
    name, w, h, fmt, off, size, flags, payload, _ = TEXTURE.unpack_from(b, toff)
    raw = b[off:off + size]
    if fmt == 4:   # PAL4 ARGB4444, twiddled, palette at the end
        pal = np.frombuffer(raw[len(raw) - 32:], dtype="<u2")
        nib = np.frombuffer(raw[:w * h // 2], dtype=np.uint8)
        idx = np.empty(w * h, np.uint8)
        idx[0::2] = nib & 15
        idx[1::2] = nib >> 4
        t = pal[idx[untwiddle_index(w, h)]]
        return px16(t, 2), dict(w=w, h=h, fmt=fmt, payload=payload)
    if payload == 2:
        cb = np.frombuffer(raw[:2048], dtype="<u2").reshape(256, 4)
        idx = np.frombuffer(raw[2048:2048 + (w // 2) * (h // 2)], dtype=np.uint8)
        blocks = cb[idx[untwiddle_index(w // 2, h // 2)]]
        t = np.zeros((h, w), dtype=np.uint16)
        t[0::2, 0::2] = blocks[..., 0]; t[1::2, 0::2] = blocks[..., 1]
        t[0::2, 1::2] = blocks[..., 2]; t[1::2, 1::2] = blocks[..., 3]
    else:
        t = np.frombuffer(raw, dtype="<u2")[:w * h]
        if payload == 1:
            t = t[untwiddle_index(w, h)]
        t = t.reshape(h, w)
    return px16(t, fmt), dict(w=w, h=h, fmt=fmt, payload=payload)


class TexPak:
    def __init__(self, path):
        self.f = open(path, "rb")
        head = self.f.read(2048)
        assert head[:8] == b"RE4PAK1\0"
        ver, count, ioff, doff, icrc = struct.unpack_from("<5I", head, 8)
        self.f.seek(ioff)
        idx = self.f.read(16 * count)
        self.index = {}
        for i in range(count):
            crc, fnv, off, size = struct.unpack_from("<4I", idx, 16 * i)
            self.index[(crc, fnv)] = (off, size)

    loose = None   # optional dc/tex dir: <n>/<crc>-<fnv>.re4tex files not in the pak

    def get(self, key):
        if key not in self.index and self.loose:
            name = "%08x-%08x.re4tex" % key
            for q in Path(self.loose).glob("*/" + name):
                return q.read_bytes()
        off, size = self.index[key]
        self.f.seek(off)
        return self.f.read(size)


def world_tris(pkg_dir):
    """-> dict(P (n,3,3) world mm, UV (n,3,2), C (n,3,4) 0..1 rgba, key (n,2), pass (n), cull (n), placement (n),
    part (n)) at LOD level 0 (what Full draws near the camera)."""
    pkg_dir = Path(pkg_dir)
    pk = r4im.load(pkg_dir / "ps2-world.re4mesh")
    side = (pkg_dir / "ps2-world.r4pw").read_bytes()
    magic, ver, npl, npa, nme = struct.unpack_from("<4s4I", side)
    assert magic == b"R4PW"
    parts_meta = [struct.unpack_from("<IIHHBBBB", side, 32 + 16 * i) for i in range(npa)]
    off = 32 + 16 * npa
    placements = [struct.unpack_from("<HH12f", side, off + 52 * i) for i in range(npl)]
    per_mesh = {}
    for k in range(len(pk.meshes)):
        out = []
        for p in pk.mesh_parts(k):
            part = pk.parts[p]
            ulo, vlo, us, vs = part[8:12]
            crc, h2, w, h, pas, cull, _, _ = parts_meta[p]
            P, UV, C = [], [], []
            for cl in pk.part_levels(p):
                for let in cl["levels"][0][1]:
                    for s in pk.meshlet_strips(let):
                        vv = [pk.vertex(v) for v in s]
                        for j in range(len(s) - 2):
                            a, b, c = (vv[j + 1], vv[j], vv[j + 2]) if j & 1 else (vv[j], vv[j + 1], vv[j + 2])
                            pa, pb, pc = (pk.world(k, *x[:3]) for x in (a, b, c))
                            if pa == pb or pb == pc or pa == pc:
                                continue
                            P.append((pa, pb, pc))
                            UV.append([(ulo + x[3] * us, vlo + x[4] * vs) for x in (a, b, c)])
                            C.append([((x[5] >> 10 & 31) / 31, (x[5] >> 5 & 31) / 31, (x[5] & 31) / 31,
                                       1.0 if x[5] & 0x8000 else 0.0) for x in (a, b, c)])
            if P:
                out.append((np.array(P), np.array(UV), np.array(C), (crc, h2), pas, cull, p))
        per_mesh[k] = out
    rows = dict(P=[], UV=[], C=[], key=[], pass_=[], cull=[], placement=[], part=[])
    for pi, (mi, gi, *aff) in enumerate(placements):
        M = np.array(aff, np.float64).reshape(3, 4)
        for P, UV, C, key, pas, cull, p in per_mesh[mi]:
            n = len(P)
            rows["P"].append(P @ M[:, :3].T + M[:, 3])
            rows["UV"].append(UV)
            rows["C"].append(C)
            rows["key"].append(np.tile(np.array(key, np.uint32), (n, 1)))
            rows["pass_"].append(np.full(n, pas, np.uint8))
            rows["cull"].append(np.full(n, cull, np.uint8))
            rows["placement"].append(np.full(n, gi, np.uint16))
            rows["part"].append(np.full(n, p, np.uint32))
    return {k: np.concatenate(v) for k, v in rows.items()}, dict(placements=npl, parts=npa, meshes=nme)
