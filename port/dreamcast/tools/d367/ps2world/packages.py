"""Read-only R4IM v3 and R4PW parsers for offline diagnostics.

The record layouts and corner traversal are extracted from the world LOD and
spatial batching tools. This module has no conversion or asset-writing path.
"""
import struct
import zlib
from pathlib import Path

HEADER = struct.Struct('<4s19I')
LOD_HEADER = struct.Struct('<8I')
MESH = struct.Struct('<HBBHHIII12f')
PART = struct.Struct('<IIBBBBII4f')
MESHLET = struct.Struct('<IIIHH6H')
VERTEX = struct.Struct('<6H')
PART_LOD = struct.Struct('<II')
CLUSTER = struct.Struct('<6HII')
LEVEL = struct.Struct('<IIf')
INDEXED = 0x8000


def read(blob):
    h = HEADER.unpack_from(blob)
    magic, version, nbytes, crc, nmesh, npart, nlet, nvert, nstrip, npal, o_mesh, o_part, o_let, o_vert, o_strip, o_pal = h[:16]
    assert magic == b'R4IM' and version == 3 and nbytes == len(blob), 'R4IM header'
    assert h[16:] == (2, 0, 0, 0), 'prelit R4IM v3 required'
    lod = LOD_HEADER.unpack_from(blob, 80)
    ncl, nlv, o_plod, o_cl, o_lv, o_class, o_rule, o_res = lod
    assert (o_class, o_rule, o_res) == (0, 0, 0), 'unsupported LOD extension'
    assert zlib.crc32(blob[80:]) == crc, 'R4IM CRC'
    for offset, count, stride in ((o_mesh, nmesh, MESH.size), (o_part, npart, PART.size),
                                  (o_let, nlet, MESHLET.size), (o_vert, nvert, VERTEX.size),
                                  (o_strip, nstrip, 1), (o_pal, npal, 4),
                                  (o_plod, npart, PART_LOD.size), (o_cl, ncl, CLUSTER.size),
                                  (o_lv, nlv, LEVEL.size)):
        assert offset >= 112 and offset % 4 == 0 and offset + count * stride <= len(blob), 'R4IM range'
    return dict(
        meshes=[list(MESH.unpack_from(blob, o_mesh + MESH.size * i)) for i in range(nmesh)],
        parts=[list(PART.unpack_from(blob, o_part + PART.size * i)) for i in range(npart)],
        lets=[list(MESHLET.unpack_from(blob, o_let + MESHLET.size * i)) for i in range(nlet)],
        verts=[VERTEX.unpack_from(blob, o_vert + VERTEX.size * i) for i in range(nvert)],
        strip=bytes(blob[o_strip:o_strip + nstrip]),
        pal=[struct.unpack_from('<I', blob, o_pal + 4 * i)[0] for i in range(npal)],
        plods=[list(PART_LOD.unpack_from(blob, o_plod + PART_LOD.size * i)) for i in range(npart)],
        clusters=[list(CLUSTER.unpack_from(blob, o_cl + CLUSTER.size * i)) for i in range(ncl)],
        levels=[list(LEVEL.unpack_from(blob, o_lv + LEVEL.size * i)) for i in range(nlv)])


def let_corners(package, meshlet):
    first_vertex, first_strip, strip_bytes, nv, sc = meshlet[:5]
    strips = package['strip']
    assert 0 < nv <= 256 and first_strip <= len(strips), 'meshlet range'
    if sc & INDEXED:
        table = struct.unpack_from('<%dH' % nv, strips, first_strip)
        corners = [first_vertex + offset for offset in table]
        at = first_strip + 2 * nv
    else:
        corners = [first_vertex + k for k in range(nv)]
        at = first_strip
    end = at + strip_bytes
    assert end <= len(strips), 'strip range'
    result = []
    while at < end:
        n = strips[at]
        assert n >= 3 and at + 1 + n <= end, 'strip length'
        result.append(list(strips[at + 1:at + 1 + n]))
        at += 1 + n
    assert len(result) == (sc & (INDEXED - 1)), 'strip count'
    return corners, result


def side_read(path, mesh):
    blob = Path(path).read_bytes()
    h = struct.unpack_from('<4s7I', blob)
    assert h[:2] == (b'R4PW', 1) and h[3:5] == (len(mesh['parts']), len(mesh['meshes'])), 'R4PW header'
    assert len(blob) == 32 + h[3] * 16 + h[2] * 52 and zlib.crc32(blob[32:]) == h[5], 'R4PW size/CRC'
    meta = [struct.unpack_from('<IIHH4B', blob, 32 + 16 * i) for i in range(h[3])]
    places = [struct.unpack_from('<HH12f', blob, 32 + 16 * h[3] + 52 * i) for i in range(h[2])]
    return h, meta, places
