"""PS2 RE4 character data readers (pure Python, no numpy): the disc's ISO9660 tree, BIO4DAT.AFS, the
UDAS/DAT entry tables of an enemy archive (emXX.dat) and the skinned PS2 model BIN.

The BIN layout follows JADERLINK's RE4-PS2-BIN-TOOL (SHARED_PS2_BIN/EXTRACT/BINdecoder.cs and
OutputFiles.cs, research by HardRain and JADERLINK):
  header 0x50: u16 magic 0x0030, u16 tex_count, u32 bones_off, u8 vertex_scale, u8 bone_count,
    u16 material_count, u32 material_off, 2 x u32 0xCDCDCDCD, u32 version, u32 bonepair_off, u32 0,
    u32 bin_flags, u32 bbox_off, u32 0, 7 x f32 bbox, u32 pad;
  bones: bone_count x 16 bytes {u8 id, u8 parent (0xFF root), u16, 3 x f32 rest translation vs the parent};
  materials: material_count x 16 bytes {u8 flag, u8 diffuse_map (TPL image), u8 bump, u8 opacity, ...,
    u32 node_off @12}; one node (a VIF packet) per material:
  node: u16 total, u8 segments-1, u8 bone_count, bone ids (padded so 4 + n is a multiple of 16), then
    segments: [weight map header (0x10) + weight map (hdr[0] x 16 bytes, 32 per line {3 x u32 bone slot*4,
    i32 count, 3 x f32 weight})] + 3 VIF headers (0x10 each; the second holds the f32 position factor at
    +0x0C and the vertex count at +0x00, the third the 16-byte-unit payload size at +0x00), the vertex
    lines (24 bytes: s16 x,y,z, u16 weight map index*2, s16 nx,ny,nz, u16 strip flag, s16 u,v, u16, u16),
    and (every segment but the first) a 0x10 end tag.
  A vertex line with strip flag 0 at position >= 2 closes the triangle (i-2, i-1, i); the winding
  alternates within a run and resets when the flag is not 0.
Positions are s16 x factor in the game's units (the GC's millimetres); UV = s16 / 255 (JADERLINK).
"""
import struct

SECTOR = 2048


# ------------------------------------------------------------------------------------------ disc / AFS


def iso_find(iso_path, name):
    """(byte offset, size) of a file anywhere in an ISO9660 image's tree (breadth first; the name is
    matched case-insensitively, ';1' ignored)."""
    with open(iso_path, 'rb') as f:
        f.seek(16 * SECTOR)
        pvd = f.read(SECTOR)
        assert pvd[1:6] == b'CD001', 'not an ISO9660 image'
        root = pvd[156:156 + 34]
        todo = [(struct.unpack_from('<I', root, 2)[0], struct.unpack_from('<I', root, 10)[0])]
        seen = set()
        while todo:
            lba, size = todo.pop(0)
            if lba in seen:
                continue
            seen.add(lba)
            f.seek(lba * SECTOR)
            d = f.read(size)
            i = 0
            while i < len(d):
                n = d[i]
                if n == 0:
                    i = (i // SECTOR + 1) * SECTOR
                    continue
                rec = d[i:i + n]
                flen = rec[32]
                raw = rec[33:33 + flen]
                sub = (struct.unpack_from('<I', rec, 2)[0], struct.unpack_from('<I', rec, 10)[0])
                if rec[25] & 2:
                    if raw not in (b'\0', b'\1'):
                        todo.append(sub)
                elif raw.decode('ascii', 'replace').split(';')[0].upper() == name.upper():
                    return sub[0] * SECTOR, sub[1]
                i += n
    raise FileNotFoundError(name)


def afs_index(iso_path, afs_name='BIO4DAT.AFS'):
    """{name: (absolute byte offset, size)} of the AFS archive's entries."""
    base, _ = iso_find(iso_path, afs_name)
    with open(iso_path, 'rb') as f:
        f.seek(base)
        head = f.read(8)
        assert head[:3] == b'AFS', 'not an AFS archive'
        n = struct.unpack_from('<I', head, 4)[0]
        table = f.read(n * 8 + 8)
        entries = [struct.unpack_from('<II', table, 8 * i) for i in range(n)]
        no, ns = struct.unpack_from('<II', table, 8 * n)
        f.seek(base + no)
        names = f.read(ns)
    out = {}
    for i, (o, s) in enumerate(entries):
        nm = names[i * 48:i * 48 + 32].split(b'\0')[0].decode('ascii', 'replace')
        if s and nm:
            out[nm] = (base + o, s)
    return out


def afs_read(iso_path, name, index=None):
    index = index or afs_index(iso_path)
    off, size = index[name]
    with open(iso_path, 'rb') as f:
        f.seek(off)
        return f.read(size)


def dat_entries(b):
    """[(index, tag, bytes)] of an RE4 DAT/archive body: u32 count, 12 bytes, count x u32 offsets,
    count x 4-byte tags. Empty slots are skipped; an entry runs to the next larger offset. The index is
    the entry index (the game's PL_ARC number is index + 4, tools/motion/archive.py)."""
    n = struct.unpack_from('<I', b, 0)[0]
    offs = struct.unpack_from('<%dI' % n, b, 16)
    out = []
    for i, o in enumerate(offs):
        tag = b[16 + 4 * n + 4 * i:20 + 4 * n + 4 * i].rstrip(b'\0').decode('ascii', 'replace')
        if not o or not tag:
            continue
        end = min([v for v in offs if v > o] + [len(b)])
        out.append((i, tag, b[o:end]))
    return out


# ------------------------------------------------------------------------------------------ BIN


class Ps2Bin:
    pass


def parse_bin(d):
    m = Ps2Bin()
    (m.magic, m.tex_count, bones_off, m.vertex_scale, nb, nmat, mat_off, pad1, pad2, m.version, bp_off, _u1,
     m.flags, bbox_off, _u2) = struct.unpack_from('<HHIBBHIIIIIIIII', d, 0)
    m.bbox = struct.unpack_from('<7f', d, 0x30)
    if m.magic != 0x0030 and pad1 != 0xCDCDCDCD:
        raise ValueError('not a PS2 BIN')
    m.bone_pairs = []
    if bp_off:
        cnt = struct.unpack_from('<I', d, bp_off)[0]
        m.bone_pairs = [struct.unpack_from('<4H', d, bp_off + 4 + 8 * i) for i in range(cnt)]
    m.bones = []
    for i in range(nb):
        bid, par = d[bones_off + 16 * i], d[bones_off + 16 * i + 1]
        m.bones.append(dict(id=bid, parent=-1 if par == 0xFF else par,
                            pos=struct.unpack_from('<3f', d, bones_off + 16 * i + 4)))
    m.materials, m.nodes = [], []
    for i in range(nmat):
        line = d[mat_off + 16 * i:mat_off + 16 * i + 16]
        m.materials.append(dict(flag=line[0], diffuse=line[1], bump=line[2], opacity=line[3], spec_map=line[4],
                                spec_rgb=tuple(line[5:8]), unk8=line[8], unk9=line[9], spec_scale=line[10],
                                custom_spec=line[11], raw=line.hex()))
        p = struct.unpack_from('<I', line, 12)[0]
        total, nseg1, nbid = struct.unpack_from('<HBB', d, p)
        list_len = ((4 + nbid + 15) // 16) * 16 - 4
        node = dict(bone_ids=list(d[p + 4:p + 4 + nbid]), segments=[])
        q = p + 4 + list_len
        for s in range(nseg1 + 1):
            seg = dict(weights=None)
            h1 = d[q:q + 16]; q += 16
            if h1[12] == 0 and h1[14] > 1:
                nbytes = h1[0] * 16
                lines = []
                for k in range(nbytes // 32):
                    b1, b2, b3, cnt = struct.unpack_from('<IIIi', d, q + 32 * k)
                    w = struct.unpack_from('<3f', d, q + 32 * k + 16)
                    lines.append((cnt, (b1 // 4, b2 // 4, b3 // 4), w))
                seg['weights'] = lines
                q += nbytes
                h1 = d[q:q + 16]; q += 16
            h2 = d[q:q + 16]; q += 16
            h3 = d[q:q + 16]; q += 16
            seg['factor'] = struct.unpack_from('<f', h2, 12)[0]
            nv = h2[0]
            chunk = h3[0] * 16
            verts = []
            for k in range(nv):
                if seg['weights'] is None:  # scenario (colour) layout
                    x, y, z, idx, u, v, _a, flag, r, g, b, a = struct.unpack_from('<3hH2hHH3hH', d, q + 24 * k)
                    verts.append(dict(p=(x, y, z), n=(r, g, b), uv=(u, v), w=None, flag=flag, color=(r, g, b, a)))
                else:
                    x, y, z, wi, nx, ny, nz, flag, u, v, _a, idx = struct.unpack_from('<3hH3hH2hHH', d, q + 24 * k)
                    verts.append(dict(p=(x, y, z), n=(nx, ny, nz), uv=(u, v), w=wi // 2, flag=flag))
            q += chunk
            seg['verts'] = verts
            if s > 0:
                q += 16
            node['segments'].append(seg)
        m.nodes.append(node)
    return m


def triangles(m):
    """[(material, [corner x3])], corner = dict(p=(x,y,z) game units, n=(nx,ny,nz) unit, uv=(u,v),
    w=[(bone id, weight), ...]); winding as JADERLINK's OBJ export (a, b, c then c, b, a alternating)."""
    out = []
    for t, node in enumerate(m.nodes):
        bone_list = node['bone_ids']
        for seg in node['segments']:
            f = seg['factor']
            wt = seg['weights']
            corners = []
            for v in seg['verts']:
                nx, ny, nz = v['n']
                ln = (nx * nx + ny * ny + nz * nz) ** 0.5 or 1.0
                w = []
                if wt is not None and v['w'] < len(wt):
                    cnt, slots, vals = wt[v['w']]
                    for k in range(max(0, min(cnt, 3))):
                        w.append((bone_list[slots[k]] if slots[k] < len(bone_list) else 0, vals[k]))
                corners.append(dict(p=(v['p'][0] * f, v['p'][1] * f, v['p'][2] * f), n=(nx / ln, ny / ln, nz / ln),
                                    uv=(v['uv'][0] / 255.0, v['uv'][1] / 255.0), w=w, raw=v))
            inv = False
            for i, v in enumerate(seg['verts']):
                if i >= 2 and v['flag'] == 0:
                    a, b, c = corners[i - 2], corners[i - 1], corners[i]
                    out.append((t, [c, b, a] if inv else [a, b, c]))
                    inv = not inv
                else:
                    inv = False
    return out
