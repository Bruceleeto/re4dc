"""Synthetic contracts for tools/ps2_objects.py (lane p2b, PS2 room objects): the rebuilt ModelData keeps the
header, joints, part headers, colour table and weight layout; parses with the converter's reader and le_mirror's
fmt_bin; tagged archives rebuild byte-identically when nothing is replaced."""
import pathlib
import struct
import sys
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent / 'tools'), str(HERE.parents[2] / 'tools')]
import ps2_objects as po  # noqa: E402
import convert_character as cc  # noqa: E402


def gc_bin(parts=2):
    """Big-endian ModelData 0x20010801: 1 joint, 4 vertices (a 100 mm quad at y=0, shift 3), s8 normals,
    s16 UVs, 1 colour, one quad per part (two triangles, GX order), parts sampling texture 0 and 1."""
    out = bytearray(0x40)
    head = len(out); out += bytes(16)                       # joint 0
    vtx = len(out)
    quad = [(0, 0, 0), (800, 0, 0), (800, 0, 800), (0, 0, 800)]
    for x, y, z in quad:
        out += struct.pack('>4h', x, y, z, 0)
    out += bytes(po.al(len(out)) - len(out))
    nrm = len(out); out += struct.pack('>3bB', 0, 64, 0, 0)
    out += bytes(po.al(len(out)) - len(out))
    clr = len(out); out += bytes([255, 255, 255, 255])
    out += bytes(po.al(len(out)) - len(out))
    tex = len(out)
    for u, v in ((0, 0), (256, 0), (256, 256), (0, 256)):
        out += struct.pack('>2h', u, v)
    out += bytes(po.al(len(out)) - len(out))
    wgt = len(out); out += bytes([0, 0, 0, 1, 100, 0, 0, 0])
    out += bytes(po.al(len(out)) - len(out))
    parts_off = len(out)
    for k in range(parts):
        body = bytearray(struct.pack('>BH', 0x90, 6))
        for i in (0, 2, 1, 0, 3, 2):   # +y faces with the normal for (a, c, b) in this synthetic winding
            body += struct.pack('>4H', i, 0, 0, i)
        body += bytes(po.al(len(body)) - len(body))
        hdr = bytearray(0x20); hdr[0x0C] = k; hdr[0x0D:0x10] = b'\xff\xff\xff'
        struct.pack_into('>II', hdr, 0x18, len(body), 2)
        out += hdr + body
    struct.pack_into('>I', out, 0, head)
    struct.pack_into('>III', out, 0x0C, clr, tex, wgt)
    out[0x18] = 1; out[0x19] = 1
    struct.pack_into('>HI', out, 0x1A, parts, parts_off)
    struct.pack_into('>II', out, 0x20, 0xA0000000, 2)
    out[0x28] = 3
    struct.pack_into('>HI', out, 0x2A, 1, 0)
    struct.pack_into('>IIHHI', out, 0x30, vtx, nrm, 4, 1, 0x20010801)
    return bytes(out)


class Ps2ObjectsTests(unittest.TestCase):
    def test_selftest_roundtrip(self):
        g = gc_bin()
        new, st = po.rebuild(g, None, po.selftest_geometry)
        self.assertEqual(st['out_tris'], 4)
        self.assertEqual(st['gc_tris'], 4)
        self.assertEqual(new[0x3C:0x40], g[0x3C:0x40])
        self.assertEqual(new[0x40:0x50], g[0x40:0x50])     # joints kept
        m0, m1 = po.GcModel(g), po.GcModel(new)
        self.assertEqual([p['hdr'][:0x18] for p in m0.parts], [p['hdr'][:0x18] for p in m1.parts])
        self.assertEqual(m1.nd, m0.nd)
        po.to_le(new)                                        # le_mirror fmt_bin accepts the layout
        self.assertEqual(len(cc.parse_geometry(new)[9]) // 3, 4)

    def test_replacement_geometry_goes_to_texture_part(self):
        g = gc_bin()

        def geo(m):
            # a smaller triangle on texture 1 only, corners as (pos, normal, uv, weights)
            cs = [((10.0, 0.0, 10.0), (0, 1, 0), (0.1, 0.1), ((0, 1.0),)),
                  ((10.0, 0.0, 50.0), (0, 1, 0), (0.1, 0.5), ((0, 1.0),)),
                  ((50.0, 0.0, 50.0), (0, 1, 0), (0.5, 0.5), ((0, 1.0),))]
            return [(1, cs)]
        new, st = po.rebuild(g, None, geo)
        m = po.GcModel(new)
        self.assertEqual([len(p['tris']) for p in m.parts], [0, 1])
        self.assertEqual(st['empty_parts'], 1)
        t = m.parts[1]['tris'][0]
        a, b, c = (m.p(r[0]) for r in t)
        f = po.cross(po.sub(b, a), po.sub(c, a))
        self.assertEqual(f[1] > 0, po.gc_winding_sense(po.GcModel(g)) > 0)

    def test_empty_geometry_keeps_layout(self):
        # world-owned objects (lane objs): no triangles, every part header kept, one unused vertex
        g = gc_bin()
        with self.assertRaises(ValueError):
            po.rebuild(g, None, lambda m: [])         # a placeholder is refused unless allowed
        new, st = po.rebuild(g, None, lambda m: [], allow_empty=True)
        m0, m1 = po.GcModel(g), po.GcModel(new)
        self.assertEqual(st['out_tris'], 0)
        self.assertEqual(st['empty_parts'], m0.nd)
        self.assertEqual(m1.nd, m0.nd)
        self.assertEqual([p['hdr'][:0x18] for p in m0.parts], [p['hdr'][:0x18] for p in m1.parts])
        self.assertEqual((m1.nv, m1.nn), (1, 1))
        self.assertEqual(new[0x40:0x50], g[0x40:0x50])     # joints kept
        po.to_le(new)

    def test_tagged_identity(self):
        n = 3
        hdr = bytearray(0x10 + 8 * n)
        struct.pack_into('<I', hdr, 0, n)
        offs, body = [], bytearray()
        base = po.al(len(hdr))
        for i in range(n):
            offs.append(base + len(body)); body += bytes([i + 1]) * 64
        struct.pack_into('<3I', hdr, 0x10, *offs)
        hdr[0x10 + 4 * n:] = b'BIN\0TPL\0BIN\0'
        data = bytes(hdr) + bytes(base - len(hdr)) + bytes(body)
        self.assertEqual(po.rebuild_tagged(data, '<', {}), data)
        new = po.rebuild_tagged(data, '<', {0: bytes([9]) * 32})
        self.assertEqual(len(new), len(data) - 32)
        self.assertEqual(new[-64:], data[-64:])


if __name__ == '__main__':
    unittest.main()
