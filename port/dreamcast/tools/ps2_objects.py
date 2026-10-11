#!/usr/bin/env python3
"""ps2_objects.py: PS2 geometry for the room objects the source model path draws (Phase 2 lane B item B1).

Room-code set pieces (loose room-archive BINs: SetObjSmd / ModInfoMgr / EvtMgr.SetBin) and etc models (ETM BINs) are
GameCube ModelData drawn by the recovered game through the generic model path. This tool keeps that path and every
source identity and only swaps the geometry: it writes a GameCube-format ModelData whose positions, normals, UVs and
GX primitive streams come from the PS2 BIN of the same object, with the GC header, joints, weight palette layout,
part (material) headers, colour table, nTex and the blend / flip joint tables unchanged. The GC TPL stays the texture
(the PS2 UVs index the same texture space; the PS2 TPL images are reduced copies), so dc/tex.pak keys do not change.
The result is disc data only: the executable is byte-identical; the knob is the staging (PS2_OBJECTS=1 fixtures).

What the game can observe besides drawing: part count and order (kept: a part with no PS2 triangle keeps its header
and gets an empty 32-byte stream), joint table (kept), material headers (kept), nVtx / nNrm and array sizes (smaller:
less memory, the purpose). Collision never comes from ModelData (SAT/EAT/ETS stay GC).

PS2 triangle -> GC part: among the GC parts that sample the same TPL image as the PS2 material, the part of the
nearest GC triangle (centroid distance). Corner colour index: the nearest GC draw vertex of that part. Weights:
the PS2 corner's bone weights as a GC palette entry (reused when equal, appended otherwise). Winding: each PS2
triangle is oriented so its face normal agrees with its corner normals in the same sense as the GC source's.

  ps2_objects.py bin <gc.bin> <ps2.bin> <out.bin> [--json out.json]        (big-endian GC BIN -> big-endian GC BIN)
  ps2_objects.py room --dar <native .dar> --room rNNN --pairs 1d:1b,1f:1d [--etm all|name,...] --out <new .dar>
                 [--json report.json] [--gc-iso ISO] [--ps2-iso ISO]
     replaces the payload's BIN entries (GC arc : PS2 arc, archive indices as the game numbers them) and/or ETM
     BINs (paired by name) with le_mirror-converted rebuilt BINs; every other byte of the payload is kept.
  ps2_objects.py selftest <gc.bin>   (rebuild with the GC geometry itself as the "PS2" input; layout check)
"""
import argparse
import hashlib
import json
import math
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parents[2] / 'tools')]
import convert_character as cc  # noqa: E402
import convert_room_bins as crb  # noqa: E402
import le_mirror as lm  # noqa: E402
import ps2_bin as pb  # noqa: E402
import room_smd as rs  # noqa: E402

PS2_ISO = '/mnt/c/Game Dev/Emulators/re4_helpers/Resident Evil 4 (USA)/Resident Evil 4 (USA).iso'
GC_ISO = '/mnt/c/Game Dev/Emulators/Resident Evil 4 Debug (Disc 1)/Resident Evil 4 Debug (Disc 1).iso'
VERSIONS = (0x20010801, 0x20030818)


def al(n, a=32):
    return (n + a - 1) & ~(a - 1)


def sha(b):
    return hashlib.sha256(b).hexdigest()


# ------------------------------------------------------------------------------------------ GC side


class GcModel:
    def __init__(self, d):
        self.d = d
        u32 = lambda o: struct.unpack_from('>I', d, o)[0]
        u16 = lambda o: struct.unpack_from('>H', d, o)[0]
        self.version = u32(0x3C)
        if self.version not in VERSIONS:
            raise ValueError('unsupported ModelData version %#x' % self.version)
        self.head, self.clr, self.tex, self.wgt = u32(0), u32(0x0C), u32(0x10), u32(0x14)
        self.nw, self.nj, self.nd = d[0x18], d[0x19], u16(0x1A)
        self.parts_off, self.flags, self.ntex = u32(0x1C), u32(0x20), u32(0x24)
        self.shift, self.ext, self.shape = d[0x28], u16(0x2A), u32(0x2C)
        self.vtx, self.nrm, self.nv, self.nn = u32(0x30), u32(0x34), u16(0x38), u16(0x3A)
        self.blend, self.flip = (u32(0x40), u32(0x44)) if self.version == 0x20030818 else (0, 0)
        if self.shape:
            raise ValueError('shape (morph) model: not converted')
        if self.ext > 0xFF:
            raise ValueError('extended weights: not converted')
        self.stride = 8 if self.flags & 0x80000000 else 6
        self.nstride = 4 if self.flags & 0x20000000 else 8
        self.scale = 1.0 / (1 << self.shift)
        self.pos = [struct.unpack_from('>4h', d, self.vtx + 8 * i) for i in range(self.nv)]
        if self.nstride == 4:
            self.nrms = [struct.unpack_from('>3bB', d, self.nrm + 4 * i) for i in range(self.nn)]
        else:
            self.nrms = [struct.unpack_from('>3hH', d, self.nrm + 8 * i) for i in range(self.nn)]
        self.weights = []
        for i in range(self.nw):
            o = self.wgt + 8 * i
            n = d[o + 3]
            self.weights.append((tuple(d[o:o + n]), tuple(d[o + 4:o + 4 + n])))
        # parts
        self.parts = []
        cur = self.parts_off
        for k in range(self.nd):
            hdr = d[cur:cur + 0x20]
            size = struct.unpack_from('>I', hdr, 0x18)[0]
            tris, s, end = [], cur + 0x20, cur + 0x20 + size
            while s < end:
                op = d[s]; s += 1
                if op == 0:
                    continue
                if op not in (0x80, 0x90, 0x98):
                    raise ValueError('part %d opcode %#x' % (k, op))
                n = struct.unpack_from('>H', d, s)[0]; s += 2
                recs = [struct.unpack_from('>%dH' % (self.stride // 2), d, s + self.stride * j) for j in range(n)]
                s += n * self.stride
                tris += list(cc.triangulate(op, recs))
            self.parts.append(dict(hdr=bytes(hdr), tris=tris, stat=struct.unpack_from('>I', hdr, 0x1C)[0]))
            cur = end
        self.parts_end = cur
        self.uvs_count = 1 + max((r[-1] for p in self.parts for t in p['tris'] for r in t), default=-1)
        # sections must be in the source order this writer reproduces
        order = [self.vtx, self.nrm] + ([self.clr] if self.clr else []) + [self.tex, self.wgt, self.parts_off]
        if order != sorted(order) or self.head >= self.vtx:
            raise ValueError('unexpected section order %s' % [hex(x) for x in order])
        for t in (self.blend, self.flip):
            if t and t < self.parts_end:
                raise ValueError('joint table before the parts')

    def uv(self, i):
        if self.flags & 0x80000000:
            u, v = struct.unpack_from('>2h', self.d, self.tex + 4 * i)
            return u / 256.0, v / 256.0
        u, v = struct.unpack_from('>2H', self.d, self.tex + 4 * i)
        return u / 32768.0, v / 32768.0

    def p(self, i):
        x, y, z, _ = self.pos[i]
        return x * self.scale, y * self.scale, z * self.scale

    def normal_unit(self):
        """Length of a unit normal in this model's normal format (median of the source normals)."""
        ls = sorted(math.sqrt(a * a + b * b + c * c) for a, b, c, _ in self.nrms)
        return ls[len(ls) // 2] if ls else (64.0 if self.nstride == 4 else 16384.0)

    def table(self, off):
        """bytes of a blend / flip joint table (u32 count + payload)."""
        n = struct.unpack_from('>I', self.d, off)[0]
        size = 4 + n * (8 if off == self.blend else 2)
        return self.d[off:off + size]


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


class Grid:
    """Nearest point over a uniform hash grid (pure Python)."""
    def __init__(self, pts, cell=200.0):
        self.pts, self.cell, self.g = pts, cell, {}
        for i, p in enumerate(pts):
            self.g.setdefault(self.key(p), []).append(i)

    def key(self, p):
        c = self.cell
        return (int(math.floor(p[0] / c)), int(math.floor(p[1] / c)), int(math.floor(p[2] / c)))

    def nearest(self, p, ok=None):
        kx, ky, kz = self.key(p)
        best, bi = None, -1
        for r in range(0, 64):
            for dx in range(-r, r + 1):
                for dy in range(-r, r + 1):
                    for dz in range(-r, r + 1):
                        if max(abs(dx), abs(dy), abs(dz)) != r:
                            continue
                        for i in self.g.get((kx + dx, ky + dy, kz + dz), ()):
                            if ok is not None and not ok(i):
                                continue
                            q = self.pts[i]
                            d = (q[0] - p[0]) ** 2 + (q[1] - p[1]) ** 2 + (q[2] - p[2]) ** 2
                            if best is None or d < best:
                                best, bi = d, i
            if best is not None and math.sqrt(best) < r * self.cell:
                return bi, math.sqrt(best)
        if best is None:
            return -1, float('inf')
        return bi, math.sqrt(best)


# ------------------------------------------------------------------------------------------ rebuild


def gc_winding_sense(m):
    """+1 when GC face normals (cross(b-a, c-a)) agree with the corner normals, -1 when opposed."""
    agree = 0
    for part in m.parts:
        for t in part['tris']:
            a, b, c = (m.p(r[0]) for r in t)
            f = cross(sub(b, a), sub(c, a))
            n = [m.nrms[r[1]][:3] for r in t]
            s = dot(f, (n[0][0] + n[1][0] + n[2][0], n[0][1] + n[1][1] + n[2][1], n[0][2] + n[1][2] + n[2][2]))
            agree += 1 if s > 0 else -1 if s < 0 else 0
    return 1 if agree >= 0 else -1


def rebuild(gc_bytes, ps2_bytes, gc_tris_from=None):
    """-> (new big-endian GC BIN, stats). gc_tris_from: selftest geometry list instead of the PS2 BIN."""
    m = GcModel(gc_bytes)
    sense = gc_winding_sense(m)
    unit = m.normal_unit()
    # GC triangles for part assignment: centroid + part + texture image
    cent, cpart = [], []
    for k, part in enumerate(m.parts):
        for t in part['tris']:
            a, b, c = (m.p(r[0]) for r in t)
            cent.append(((a[0] + b[0] + c[0]) / 3, (a[1] + b[1] + c[1]) / 3, (a[2] + b[2] + c[2]) / 3))
            cpart.append(k)
    grid = Grid(cent)
    part_tex = [p['hdr'][0x0C] for p in m.parts]
    # corner colour: nearest GC draw vertex of the chosen part
    vgrid_pts, vgrid_rec, vgrid_part = [], [], []
    for k, part in enumerate(m.parts):
        for t in part['tris']:
            for r in t:
                vgrid_pts.append(m.p(r[0])); vgrid_rec.append(r); vgrid_part.append(k)
    vgrid = Grid(vgrid_pts)

    if gc_tris_from is None:
        pm = pb.parse_bin(ps2_bytes)
        ptex = [x['diffuse'] for x in pm.materials]
        ps2 = []
        for t, cs in pb.triangles(pm):
            ps2.append((ptex[t], [(c['p'], c['n'], c['uv'], tuple(c['w'])) for c in cs]))
    else:
        ps2 = gc_tris_from(m)
    stats = dict(gc_tris=sum(len(p['tris']) for p in m.parts), ps2_tris=len(ps2), gc_parts=m.nd,
                 gc_vertices=m.nv, gc_normals=m.nn, gc_bytes=len(gc_bytes), no_tex_part=0, flipped=0,
                 weight_mismatch=0, degenerate=0, appended_weights=0)

    pal = list(m.weights)
    pal_index = {w: i for i, w in reversed(list(enumerate(pal)))}

    def palette(w):
        if not w:
            w = ((0, 1.0),)
        w = sorted(((int(b), float(f)) for b, f in w if f > 0.0005), key=lambda x: -x[1])[:3]
        tot = sum(f for b, f in w) or 1.0
        vals = [int(round(100 * f / tot)) for b, f in w]
        vals[0] += 100 - sum(vals)
        key = (tuple(b for b, f in w), tuple(vals))
        if key not in pal_index:
            pal_index[key] = len(pal); pal.append(key); stats['appended_weights'] += 1
        return pal_index[key]

    verts, vmap, nrms, nmap, uvs, umap = [], {}, [], {}, [], {}
    part_tris = [[] for _ in m.parts]
    lim = 32767
    for tex, cs in ps2:
        P = [c[0] for c in cs]
        if len(set(P)) < 3:
            stats['degenerate'] += 1
            continue
        cen = tuple(sum(p[i] for p in P) / 3 for i in range(3))
        ti, _ = grid.nearest(cen, lambda i: part_tex[cpart[i]] == tex)
        if ti < 0:
            stats['no_tex_part'] += 1
            ti, _ = grid.nearest(cen)
        k = cpart[ti]
        f = cross(sub(P[1], P[0]), sub(P[2], P[0]))
        ns = [c[1] for c in cs]
        s = dot(f, (ns[0][0] + ns[1][0] + ns[2][0], ns[0][1] + ns[1][1] + ns[2][1], ns[0][2] + ns[1][2] + ns[2][2]))
        if (s > 0 and sense < 0) or (s < 0 and sense > 0):
            cs = [cs[0], cs[2], cs[1]]; stats['flipped'] += 1
        tri = []
        for p, n, uv, w in cs:
            wi = palette(w)
            vi_near, _ = vgrid.nearest(p, lambda i: vgrid_part[i] == k)
            rec = vgrid_rec[vi_near]
            if pal[wi][0] != m.weights[m.pos[rec[0]][3]][0]:
                stats['weight_mismatch'] += 1
            q = [int(round(x / m.scale)) for x in p]
            if max(abs(x) for x in q) > lim:
                raise ValueError('position outside the s16 range at shift %d' % m.shift)
            vk = (q[0], q[1], q[2], wi)
            if vk not in vmap:
                vmap[vk] = len(verts); verts.append(vk)
            ln = math.sqrt(dot(n, n)) or 1.0
            if m.nstride == 4:
                nq = tuple(max(-127, min(127, int(round(x / ln * unit)))) for x in n)
            else:
                nq = tuple(max(-32767, min(32767, int(round(x / ln * unit)))) for x in n)
            nk = nq + (wi,)
            if nk not in nmap:
                nmap[nk] = len(nrms); nrms.append(nk)
            if m.flags & 0x80000000:
                uq = (max(-32768, min(32767, int(round(uv[0] * 256)))), max(-32768, min(32767, int(round(uv[1] * 256)))))
            else:
                uq = (max(0, min(65535, int(round(uv[0] * 32768)))), max(0, min(65535, int(round(uv[1] * 32768)))))
            if uq not in umap:
                umap[uq] = len(uvs); uvs.append(uq)
            corner = (vmap[vk], nmap[nk]) + ((rec[2],) if m.stride == 8 else ()) + (umap[uq],)
            tri.append(corner)
        part_tris[k].append(tuple(tri))
    if len(verts) > 0xFFFF or len(nrms) > 0xFFFF:
        raise ValueError('array too large')
    if len(pal) > 0xFF:
        raise ValueError('weight palette exceeds 255 entries')

    # ---- write (source section order)
    d = gc_bytes
    out = bytearray(d[:m.vtx])
    vtx = len(out)
    for x, y, z, wi in verts:
        out += struct.pack('>4h', x, y, z, wi)
    out += bytes(al(len(out)) - len(out))
    nrm = len(out)
    for nk in nrms:
        out += struct.pack('>3bB' if m.nstride == 4 else '>3hH', *nk)
    out += bytes(al(len(out)) - len(out))
    clr = 0
    if m.clr:
        clr = len(out)
        out += d[m.clr:m.tex]
        out += bytes(al(len(out)) - len(out))
    tex = len(out)
    for uq in uvs:
        out += struct.pack('>2h' if m.flags & 0x80000000 else '>2H', *uq)
    out += bytes(al(len(out)) - len(out))
    wgt = len(out)
    for ids, vals in pal:
        n = len(ids)
        out += bytes(list(ids) + [0] * (3 - n) + [n] + list(vals) + [0] * (4 - n))
    out += bytes(al(len(out)) - len(out))
    parts_off = len(out)
    stream_stats = dict(strips=0, triangles=0)
    for k, part in enumerate(m.parts):
        body = bytearray()
        tris = part_tris[k]
        if tris:
            # stripify over corner tuples (vertex identity = the whole record), GX strip order
            ids, back = {}, []
            for t in tris:
                for c in t:
                    if c not in ids:
                        ids[c] = len(back); back.append(c)
            for strip in crb.stripify([tuple(ids[c] for c in t) for t in tris]):
                for chunk in crb.split_strip(strip) if len(strip) > 0xFFFF else [strip]:
                    if len(chunk) == 3:
                        continue  # emitted below as one triangle list
                    body += struct.pack('>BH', 0x98, len(chunk))
                    for i in chunk:
                        body += struct.pack('>%dH' % (m.stride // 2), *back[i])
                    stream_stats['strips'] += 1
            singles = [s for s in crb.stripify([tuple(ids[c] for c in t) for t in tris]) if len(s) == 3]
            if singles:
                body += struct.pack('>BH', 0x90, 3 * len(singles))
                for s in singles:
                    for i in s:
                        body += struct.pack('>%dH' % (m.stride // 2), *back[i])
                stream_stats['triangles'] += len(singles)
        body += bytes(max(32, al(len(body))) - len(body))
        hdr = bytearray(part['hdr'])
        struct.pack_into('>I', hdr, 0x18, len(body))
        struct.pack_into('>I', hdr, 0x1C, len(tris) if part['stat'] == len(part['tris']) else part['stat'])
        out += hdr + body
    tables = {}
    for name, off in (('blend', m.blend), ('flip', m.flip)):
        if off:
            out += bytes(al(len(out)) - len(out))
            tables[name] = len(out)
            out += m.table(off)
    out += bytes(al(len(out)) - len(out))
    # file tail beyond the last section in the source (kept as padding size)
    hdr_put = lambda o, fmt, v: struct.pack_into(fmt, out, o, v)
    hdr_put(0x0C, '>I', clr); hdr_put(0x10, '>I', tex); hdr_put(0x14, '>I', wgt)
    out[0x18] = len(pal)
    hdr_put(0x1C, '>I', parts_off)
    if m.ext == m.nw:
        hdr_put(0x2A, '>H', len(pal))
    hdr_put(0x30, '>I', vtx); hdr_put(0x34, '>I', nrm)
    hdr_put(0x38, '>H', len(verts)); hdr_put(0x3A, '>H', len(nrms))
    if m.version == 0x20030818:
        hdr_put(0x40, '>I', tables.get('blend', 0)); hdr_put(0x44, '>I', tables.get('flip', 0))
    new = bytes(out)
    # parse back with the converter's reader (exactness of the written layout)
    r = cc.parse_geometry(new)
    stats.update(out_tris=len(r[9]) // 3, out_vertices=len(verts), out_normals=len(nrms), out_uvs=len(uvs),
                 out_weights=len(pal), out_bytes=len(new), **stream_stats,
                 empty_parts=sum(1 for t in part_tris if not t))
    if stats['out_tris'] != sum(len(t) for t in part_tris):
        raise ValueError('triangle count changed in the round trip')
    return new, stats


def to_le(be_bin, label='bin'):
    """le_mirror's ModelData conversion of one BIN (the native room payload form)."""
    sw = lm.Swapper(bytearray(be_bin), label)
    with sw.bounded(0, len(be_bin)):
        lm.fmt_bin(sw, 0, len(be_bin), {})
    return bytes(sw.data)


def selftest_geometry(m):
    out = []
    for part in m.parts:
        for t in part['tris']:
            cs = []
            for r in t:
                n = m.nrms[r[1]][:3]
                ids, vals = m.weights[m.pos[r[0]][3]]
                cs.append((m.p(r[0]), n, m.uv(r[-1]), tuple((b, v / 100.0) for b, v in zip(ids, vals))))
            out.append((part['hdr'][0x0C], cs))
    return out


# ------------------------------------------------------------------------------------------ archives


def etm_entries(b, en):
    """ETM: u32 count, 0x20 header, entries {u32 size, ... name @0x20, data @0x40} -> [(name, data off, data end)]"""
    n = struct.unpack_from(en + 'I', b, 0)[0]
    o, out = 0x20, []
    for _ in range(n):
        sz = struct.unpack_from(en + 'I', b, o)[0]
        nm = b[o + 0x20:o + 0x40].split(b'\0')[0].decode('latin-1')
        out.append((nm, o, o + sz if sz else len(b)))
        if not sz:
            break
        o += sz
    return out


def rebuild_tagged(data, en, replace):
    """Tagged archive with entries replaced ({index: bytes}); offsets recomputed in the source entry order,
    32-byte aligned; every other entry byte-identical."""
    n = struct.unpack_from(en + 'I', data, 0)[0]
    ents = rs.tagged_entries(data, en)
    offs = struct.unpack_from(en + '%dI' % n, data, 0x10)
    order = sorted((o, i) for i, o in enumerate(offs) if o)
    out = bytearray(data[:order[0][0]])
    new_offs = list(offs)
    for o, i in order:
        tag, s, e = ents[i]
        body = replace.get(i, data[s:e])
        out += bytes(al(len(out)) - len(out))
        new_offs[i] = len(out)
        out += body
    out += bytes(al(len(out)) - len(out))
    struct.pack_into(en + '%dI' % n, out, 0x10, *new_offs)
    return bytes(out)


NATIVE_TABLES = {b'ESQ\0': b'R4ESQTBL', b'NTR\0': None}


def remap_native_tables(old, new):
    """The native room payload's prepared tables (ESQ effect sequences, NTR texture identities: header
    magic, version, count, 12, crc32(table), word24, word28 + count 12-byte rows of payload offsets) name
    absolute payload offsets and the payload size (native_effect.cpp bind_archive, native_ui.cpp adopt).
    Rebase every offset by its owning entry's move and the size words to the new payload bytes."""
    import zlib
    n = struct.unpack_from('<I', old, 0)[0]
    oe, ne = rs.tagged_entries(old, '<'), rs.tagged_entries(new, '<')
    spans = sorted((s, e, ne[i][1]) for i, (t, s, e) in enumerate(oe))

    def mapped(x):
        for s, e, s2 in spans:
            if s <= x < e:
                return x - s + s2
        raise ValueError('table offset %#x outside every entry' % x)
    out = bytearray(new)
    report = {}
    for i, (tag, s, e) in enumerate(ne):
        if tag not in NATIVE_TABLES:
            continue
        magic, ver, cnt, row, crc, w24, w28 = struct.unpack_from('<8s6I', out, s)
        if row != 12 or ver != 1 or zlib.crc32(out[s + 32:s + 32 + 12 * cnt]) & 0xffffffff != crc:
            raise ValueError('%s table header not understood' % tag)
        for r in range(cnt):
            o = s + 32 + 12 * r
            a, b, c = struct.unpack_from('<3I', out, o)
            if tag == b'ESQ\0':
                struct.pack_into('<I', out, o, mapped(a))
            else:
                struct.pack_into('<3I', out, o, mapped(a), mapped(b), mapped(c))
        if tag == b'ESQ\0':
            if w24 != len(old) or w28:
                raise ValueError('ESQ size word')
            w24 = len(new)
        else:
            if w28 != len(old):
                raise ValueError('NTR size word')
            w28 = len(new)
        crc = zlib.crc32(out[s + 32:s + 32 + 12 * cnt]) & 0xffffffff
        struct.pack_into('<8s6I', out, s, magic, ver, cnt, row, crc, w24, w28)
        report[tag.rstrip(b'\0').decode()] = cnt
    return bytes(out), report


def room(args):
    from assetpipe.rooms import GcIso
    dar = Path(args.dar).read_bytes()
    kind, size, dest, off = struct.unpack_from('<4I', dar, 0x20)
    if kind != 0 or off + size > len(dar):
        raise ValueError('dar: first entry is not the room payload')
    for pos in range(0x40, 0x400, 0x20):
        k2, s2, d2, o2 = struct.unpack_from('<4I', dar, pos)
        if k2 == 0xFFFFFFFF:
            break
        if o2 + s2 > off:
            raise ValueError('dar: an entry lies after the payload; not rewritten in place')
    pay = dar[off:off + size]
    g = GcIso(args.gc_iso)
    key = next((k for rr, k in g.rooms() if rr == args.room), None)
    gd = g.read(key)
    if gd[:32] == rs.CONTAINER_MAGIC:
        gd = rs.decode_das(gd)
    ge = rs.tagged_entries(gd, '>')
    pe = {i + 4: (t, b) for i, t, b in pb.dat_entries(pb.afs_read(args.ps2_iso, args.room + '.dat', pb.afs_index(args.ps2_iso)))}
    le = rs.tagged_entries(pay, '<')
    rep, report = {}, dict(room=args.room, dar_in=args.dar, dar_in_sha256=sha(dar), payload_in_bytes=len(pay), objects=[])
    for pair in [x for x in (args.pairs or '').split(',') if x]:
        ga, pa = (int(x, 16) for x in pair.split(':'))
        i = ga - 4
        tag, s, e = ge[i]
        if tag.rstrip(b'\0') != b'BIN' or le[i][0].rstrip(b'\0') != b'BIN' or pe[pa][0] != 'BIN':
            raise ValueError('pair %s: not BIN entries' % pair)
        gbin = gd[s:e]
        cur = pay[le[i][1]:le[i][2]]
        src_le = to_le(gbin, pair)
        if cur.rstrip(b'\0') != src_le.rstrip(b'\0'):
            raise ValueError('pair %s: the payload BIN is not le_mirror(GC BIN); refusing to replace modified data' % pair)
        new, st = rebuild(gbin, pe[pa][1])
        rep[i] = to_le(new, pair)
        st.update(kind='room BIN', gc_arc=hex(ga), ps2_arc=hex(pa), le_bytes_before=len(cur), le_bytes_after=len(rep[i]))
        report['objects'].append(st)
    if args.etm:
        ei = next(i for i, (t, s, e) in enumerate(ge) if t.rstrip(b'\0') == b'ETM')
        gb = gd[ge[ei][1]:ge[ei][2]]
        lb = bytearray(pay[le[ei][1]:le[ei][2]])
        pbm = next(b for t, b in pe.values() if t == 'ETM')
        gents = etm_entries(gb, '>'); lents = etm_entries(bytes(lb), '<')
        pents = {nm: pbm[s + 0x40:e] for nm, s, e in etm_entries(pbm, '<')}
        want = None if args.etm == 'all' else set(args.etm.split(','))
        pieces = []
        for (nm, s, e), (lnm, ls, le_) in zip(gents, lents):
            if nm != lnm:
                raise ValueError('ETM order differs')
            body = bytes(lb[ls:le_])
            if nm.lower().endswith('.bin') and nm in pents and (want is None or nm in want):
                gbin = gb[s + 0x40:e]
                try:
                    src_le = to_le(gbin, nm)
                    if body[0x40:].rstrip(b'\0') != src_le.rstrip(b'\0'):
                        raise ValueError('ETM %s is not le_mirror(GC)' % nm)
                    new, st = rebuild(gbin, pents[nm])
                    if st['out_tris'] >= st['gc_tris']:
                        st.update(kind='etc', name=nm, skipped='PS2 not smaller')
                        report['objects'].append(st)
                    else:
                        nl = to_le(new, nm)
                        h = bytearray(body[:0x40])
                        size = al(0x40 + len(nl))
                        struct.pack_into('<I', h, 0, size if struct.unpack_from('<I', h, 0)[0] else 0)
                        nb = bytes(h) + nl + bytes(size - 0x40 - len(nl))
                        st.update(kind='etc', name=nm, le_bytes_before=len(body), le_bytes_after=len(nb))
                        report['objects'].append(st)
                        body = nb
                except ValueError as ex:
                    report['objects'].append(dict(kind='etc', name=nm, skipped=str(ex)))
            pieces.append(body)
        newetm = bytearray(lb[:0x20])
        for b in pieces:
            newetm += b
        newetm += bytes(al(len(newetm)) - len(newetm))
        rep[ei] = bytes(newetm)
    newpay, report['native_tables'] = remap_native_tables(pay, rebuild_tagged(pay, '<', rep))
    out = bytearray(dar[:off]) + newpay
    out += bytes(al(len(out), 2048) - len(out))
    struct.pack_into('<4I', out, 0x20, 0, len(newpay), 0, off)
    Path(args.out).write_bytes(bytes(out))
    report.update(payload_out_bytes=len(newpay), payload_saved=len(pay) - len(newpay), dar_out=args.out,
                  dar_out_sha256=sha(bytes(out)), tool_sha256=sha(Path(__file__).read_bytes()))
    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=1))
    for o in report['objects']:
        print('%-10s %-14s tris %s -> %s  bytes %s -> %s %s' % (o.get('kind'), o.get('name', o.get('gc_arc', '')), o.get('gc_tris'),
              o.get('out_tris'), o.get('le_bytes_before'), o.get('le_bytes_after'), o.get('skipped', '')))
    print('payload %d -> %d (saved %d)' % (len(pay), len(newpay), len(pay) - len(newpay)))


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest='cmd', required=True)
    a = sp.add_parser('bin'); a.add_argument('gc'); a.add_argument('ps2'); a.add_argument('out'); a.add_argument('--json')
    a = sp.add_parser('selftest'); a.add_argument('gc')
    a = sp.add_parser('room')
    a.add_argument('--dar', required=True); a.add_argument('--room', required=True); a.add_argument('--pairs')
    a.add_argument('--etm'); a.add_argument('--out', required=True); a.add_argument('--json')
    a.add_argument('--gc-iso', default=GC_ISO); a.add_argument('--ps2-iso', default=PS2_ISO)
    args = ap.parse_args()
    if args.cmd == 'bin':
        new, st = rebuild(Path(args.gc).read_bytes(), Path(args.ps2).read_bytes())
        Path(args.out).write_bytes(new)
        if args.json:
            Path(args.json).write_text(json.dumps(st, indent=1))
        print(json.dumps(st))
    elif args.cmd == 'selftest':
        g = Path(args.gc).read_bytes()
        new, st = rebuild(g, None, selftest_geometry)
        to_le(new)
        print(json.dumps(st))
    else:
        room(args)


if __name__ == '__main__':
    main()
