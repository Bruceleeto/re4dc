#!/usr/bin/env python3
"""ps2_load_indicator.py <PS2 USA iso> <out dir>: the PS2 version's room-loading indicator for LOAD_INDICATOR=1.

The PS2 gameRoomInit (SLUS_211.34 0x217ee0) shows id class 0x2D from its option archive (pG->pOption, SS/<lang>/
option.dat = BIO4DAT.AFS entry "option.dat") entry 0x3C for the whole room set-up, with the textures of entry 0x10
(IdTexDataLoad owner 10), and kills / releases them at the end. The GameCube option archive has no such entries.
This tool converts the two units and the one texture they use (id 0x24, "Loading...", 128x16 PSMT4) into the port's
in-memory (le_mirror) layouts, so no game code decodes PS2 data:

  <out>/dc/loadind.dat   header 0x20 ("R4LI", version 1, total bytes, tex block offset, id block offset, tex id),
                         tex block = id texture data version 0xB (id_tex.cpp IdTexDataLoad: one id, a GameCube CI4 TPL
                         with an RGB5A3 palette, the PS2 TexAnm record), id block = an id table version 2.00 (id_sys.h
                         IdData2, 0x8C bytes per unit) with its Hermite colour curves. Little-endian fields; TPL texels
                         and palette in GameCube order (the fmt_tpl contract).
  <out>/dc/tex/<h>/<crc>-<fnv>.re4tex
                         the native texture, keyed by the TPL image identity the runtime hashes (native_ui.cpp
                         image_key: an ordinary resident image), built from the exact PS2 RGBA (source_pixels), not
                         from the 3-bit-alpha CI4 key carrier.
  <out>/loadind.png      the texture (x4) on dark grey; <out>/loadind-report.json: inputs, sha256s, the unit fields.

PS2 IdData2 (0xA0 per unit, header 0x10) -> GameCube IdData2 (0x8C, header 8), mapped from option.dat entries
0x14/0x18/0x1C of both versions (same units, same values): bytes 0x00..0x0F as they are (the u32 at 0 holds the flags
byte), pos / vtx[4] / rot as Vec4 -> Vec, sizeX/Y 0x60, col0/col1 0x68, blend 0x80, trans 0x82, mask 0x83, flags_7F
0x84, transSub 0x85, ofs[6] 0x88 (re-based). Hermite1 curves have the same layout on both (s32 num, {t, v, out, in}).
Colours use the same 0..255 scale (entry 0x18 matches byte for byte).

Deterministic: the same ISO gives the same bytes. Standard library only (+ the repo's convert_tpl / prepare_native_ui).
"""
import hashlib, json, os, struct, sys, zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent)]
import convert_tpl  # noqa: E402

PS2_OPTION_SHA256 = '72326415fdeb42ffdabebb4c52d66c7a5b9f3556fb2c6a7c82046691fd9fc4ee'  # USA SLUS-21134, eng
TEX_ID = 0x24
ID_ENTRY = 0x3C   # pOption offset table entry of the loading id table
TEX_ENTRY = 0x10  # pOption offset table entry of the id textures


def iso_file(iso, path):
    """(byte offset, size) of an ISO9660 path, e.g. /DATA/BIO4DAT.AFS."""
    iso.seek(16 * 2048)
    pvd = iso.read(2048)
    if pvd[1:6] != b'CD001':
        raise SystemExit('not an ISO9660 image')
    lba, size = struct.unpack_from('<I', pvd, 156 + 2)[0], struct.unpack_from('<I', pvd, 156 + 10)[0]
    for part in path.strip('/').split('/'):
        iso.seek(lba * 2048)
        d = iso.read(size)
        o, found = 0, None
        while o < len(d):
            n = d[o]
            if n == 0:
                o = (o // 2048 + 1) * 2048
                continue
            name = d[o + 33:o + 33 + d[o + 32]].decode('latin1').split(';')[0]
            if name.upper() == part.upper():
                found = struct.unpack_from('<I', d, o + 2)[0], struct.unpack_from('<I', d, o + 10)[0]
                break
            o += n
        if not found:
            raise SystemExit('%s: %s not found' % (path, part))
        lba, size = found
    return lba * 2048, size


def ps2_option(iso_path):
    with open(iso_path, 'rb') as iso:
        base, _ = iso_file(iso, '/DATA/BIO4DAT.AFS')
        iso.seek(base)
        head = iso.read(8)
        if head[:4] != b'AFS\0':
            raise SystemExit('BIO4DAT.AFS: no AFS header')
        count = struct.unpack_from('<I', head, 4)[0]
        toc = iso.read(8 * count + 8)
        ents = [struct.unpack_from('<II', toc, 8 * i) for i in range(count)]
        name_off, _ = struct.unpack_from('<II', toc, 8 * count)
        iso.seek(base + name_off)
        names = iso.read(0x30 * count)
        for i, (off, size) in enumerate(ents):
            name = names[0x30 * i:0x30 * i + 32].split(b'\0')[0].decode('latin1')
            if name == 'option.dat' and size:
                iso.seek(base + off)
                data = iso.read(size)
                if hashlib.sha256(data).hexdigest() == PS2_OPTION_SHA256:
                    return data, i
        raise SystemExit('BIO4DAT.AFS: no option.dat with sha256 %s (a USA disc is expected)' % PS2_OPTION_SHA256)


def ps2_tpl_rgba(tpl):
    """PS2 TPL (magic 0x1000) entry 0, PSMT4 unswizzled: (w, h, indices, clut rgba 0..255)."""
    magic, count, start = struct.unpack_from('<III', tpl, 0)
    if magic != 0x1000 or count != 1:
        raise SystemExit('unexpected PS2 TPL')
    w, h, bitdepth, interlace = struct.unpack_from('<HHHH', tpl, start)
    index_off, palette_off = struct.unpack_from('<II', tpl, start + 0x20)
    if bitdepth != 8 or interlace & 2:
        raise SystemExit('expected a linear PSMT4 texture (bitdepth %d interlace %d)' % (bitdepth, interlace))
    raw = tpl[index_off:index_off + w * h // 2]
    idx = bytearray()
    for b in raw:
        idx += bytes((b & 15, b >> 4))
    clut = []
    for i in range(16):  # 16 colours: 0-7 at +0, 8-15 at +0x40 (8x2 CLUT in a 16-wide buffer)
        o = palette_off + (i if i < 8 else 0x40 // 4 + i - 8) * 4
        r, g, b, a = tpl[o:o + 4]
        clut.append((r, g, b, 255 if a >= 128 else a * 255 // 128))
    return w, h, idx, clut


def rgb5a3(c):
    r, g, b, a = c
    if a >= 0xE0:
        return 0x8000 | (r >> 3) << 10 | (g >> 3) << 5 | b >> 3
    return (a >> 5) << 12 | (r >> 4) << 8 | (g >> 4) << 4 | b >> 4


def gc_ci4(w, h, idx):
    out = bytearray()
    for ty in range(0, h, 8):
        for tx in range(0, w, 8):
            for y in range(ty, ty + 8):
                for x in range(tx, tx + 8, 2):
                    out.append(idx[y * w + x] << 4 | idx[y * w + x + 1])
    return bytes(out)


def tpl_blobs(w, h, pixels, pal_be):
    """(big-endian TPL for convert_tpl.parse_tpl, little-endian mirrored TPL the game reads)."""
    def build(e):
        hdr = struct.pack(e + 'III', 0x0020AF30, 1, 0xC) + struct.pack(e + 'II', 0x14, 0x38)
        tex = struct.pack(e + 'HHII', h, w, 8, 0x80) + struct.pack(e + 'IIIIf', 0, 0, 1, 1, 0.0) + bytes(4)
        clut = struct.pack(e + 'HBBII', 16, 0, 0, 2, 0x60)
        body = hdr + tex + clut
        body += bytes(0x60 - len(body)) + pal_be
        body += bytes(0x80 - len(body)) + pixels
        return body
    return build('>'), build('<')


def convert_units(ps2_tbl):
    """PS2 id table (header 0x10, 0xA0 units) -> GameCube 2.00 table (header 8, 0x8C units) + curves, LE."""
    if ps2_tbl[:5] != b'2.00\0':
        raise SystemExit('PS2 id table version %r' % ps2_tbl[:5])
    n = ps2_tbl[5]
    units = [ps2_tbl[0x10 + 0xA0 * i:0x10 + 0xA0 * (i + 1)] for i in range(n)]
    curves, out_units, fields = {}, [], []
    tail = bytearray()
    base = 8 + 0x8C * n
    for u in units:
        ofs = list(struct.unpack_from('<6I', u, 0x88))
        new = []
        for k, r in enumerate(ofs):
            if not r:
                new.append(0)
                continue
            if k < 2:
                raise SystemExit('path data in the loading id is not converted')
            if r not in curves:
                num = struct.unpack_from('<i', ps2_tbl, r)[0]
                blob = ps2_tbl[r:r + 4 + 16 * num]
                curves[r] = base + len(tail)
                tail += blob
            new.append(curves[r])
        g = bytearray(0x8C)
        g[3] = struct.unpack_from('<I', u, 0)[0] & 0xFF
        g[4:0x10] = u[4:0x10]
        g[0x10] = u[0x81]
        g[0x14:0x20] = u[0x10:0x1C]
        for i in range(4):
            g[0x20 + 12 * i:0x2C + 12 * i] = u[0x20 + 16 * i:0x2C + 16 * i]
        g[0x50:0x60] = u[0x60:0x70]
        g[0x60:0x6C] = u[0x70:0x7C]
        g[0x6C], g[0x6D], g[0x6E], g[0x6F], g[0x70] = u[0x80], u[0x82], u[0x83], u[0x84], u[0x85]
        struct.pack_into('<6I', g, 0x74, *new)
        out_units.append(bytes(g))
        fields.append(dict(no=u[5], texId=u[0xB], loop=u[0xD], scaleType=u[0xE], pos=struct.unpack_from('<3f', u, 0x10),
                           size=struct.unpack_from('<2f', u, 0x60), col0=u[0x68:0x6C].hex(), col1=u[0x6C:0x70].hex(),
                           blend=u[0x80], trans=u[0x82], curves=new))
    return b'2.00\0' + bytes((n, 0, 0)) + b''.join(out_units) + bytes(tail), fields


def align(b, n):
    return b + bytes(-len(b) % n)


def write_png(path, w, h, rgba):
    raw = b''.join(b'\0' + bytes(rgba[y * w * 4:(y + 1) * w * 4]) for y in range(h))
    def chunk(t, d):
        return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    path.write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0)) +
                     chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b''))


def main():
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    iso, out = sys.argv[1], Path(sys.argv[2])
    opt, afs_index = ps2_option(iso)
    table = struct.unpack_from('<13I', opt, 0x10)
    ends = sorted(set(table)) + [len(opt)]
    def entry(ofs):
        a = table[(ofs - 0x10) // 4]
        return opt[a:ends[ends.index(a) + 1]]
    tex = entry(TEX_ENTRY)
    ids = entry(ID_ENTRY)
    # the PS2 id texture data (version 0xB): find texture 0x24's TPL and TexAnm record
    ver, ofs_id = struct.unpack_from('<II', tex, 0)
    ofs_tpl, ofs_anm = struct.unpack_from('<II', tex, 0x18)
    n = struct.unpack_from('<I', tex, ofs_id)[0]
    tex_ids = [struct.unpack_from('<H', tex, ofs_id + 4 + 8 * i)[0] for i in range(n)]
    if ver != 0xB or TEX_ID not in tex_ids:
        raise SystemExit('PS2 id textures: version %#x ids %s' % (ver, tex_ids))
    k = tex_ids.index(TEX_ID)
    tpl_ofs = [ofs_tpl + struct.unpack_from('<I', tex, ofs_tpl + 4 + 4 * i)[0] for i in range(n)]
    anm = tex[ofs_anm + struct.unpack_from('<I', tex, ofs_anm + 4 + 4 * k)[0]:][:16]
    nxt = sorted(o for o in tpl_ofs + [ofs_anm] if o > tpl_ofs[k])[0]
    w, h, idx, clut = ps2_tpl_rgba(tex[tpl_ofs[k]:nxt])
    rgba = [clut[i] for i in idx]
    pal_be = b''.join(struct.pack('>H', rgb5a3(c)) for c in clut)
    pixels = gc_ci4(w, h, idx)
    tpl_be, tpl_le = tpl_blobs(w, h, pixels, pal_be)
    image = convert_tpl.parse_tpl(tpl_be)[0]
    import prepare_native_ui as pnu
    key, _ = pnu.image_identity(image)
    package, meta = convert_tpl.build_package([image], [convert_tpl.MaterialBinding('source', 0, None)], twiddle=True,
                                              pad_to_power_of_two=True, source_intensity_alpha=True,
                                              source_pixels={0: rgba})
    # tex block: id texture data version 0xB (12-word header), one id
    hdr = 0x30
    idtbl = struct.pack('<IHHI', 1, TEX_ID, 0, 0)
    tpltbl_at = hdr + len(idtbl)
    anmtbl_at = tpltbl_at + 8
    anm_at = anmtbl_at + 8
    tpl_at = (anm_at + 16 + 31) & ~31
    texblk = struct.pack('<12I', 0xB, hdr, 0, 0, 0, 0, tpltbl_at, anmtbl_at, 0, 0, 0, 0) + idtbl
    texblk += struct.pack('<II', 1, tpl_at - tpltbl_at) + struct.pack('<II', 1, anm_at - anmtbl_at) + anm
    texblk = texblk + bytes(tpl_at - len(texblk)) + tpl_le
    idblk, fields = convert_units(ids)
    tex_at = 0x20
    id_at = tex_at + len(align(texblk, 32))
    total = id_at + len(align(idblk, 32))
    blob = struct.pack('<4sIIIII8x', b'R4LI', 1, total, tex_at, id_at, TEX_ID) + align(texblk, 32) + align(idblk, 32)
    assert len(blob) == total
    (out / 'dc' / 'tex' / key[0]).mkdir(parents=True, exist_ok=True)
    (out / 'dc' / 'loadind.dat').write_bytes(blob)
    tex_path = out / 'dc' / 'tex' / key[0] / (key + '.re4tex')
    tex_path.write_bytes(package)
    big = []
    for y in range(h * 4):
        for x in range(w * 4):
            r, g, b, a = rgba[(y // 4) * w + x // 4]
            big.append(tuple((c * a + 40 * (255 - a)) // 255 for c in (r, g, b)) + (255,))
    write_png(out / 'loadind.png', w * 4, h * 4, bytes(v for p in big for v in p))
    rep = dict(iso=os.path.basename(iso), afs='BIO4DAT.AFS', afs_index=afs_index, option_sha256=PS2_OPTION_SHA256,
               id_entry=hex(ID_ENTRY), tex_entry=hex(TEX_ENTRY), tex_id=hex(TEX_ID), texture=dict(width=w, height=h, key=key),
               units=fields, loadind_dat=dict(bytes=len(blob), sha256=hashlib.sha256(blob).hexdigest(), tex_at=tex_at,
               id_at=id_at), re4tex=dict(path=str(tex_path.relative_to(out)), bytes=len(package),
               sha256=hashlib.sha256(package).hexdigest(), native=meta))
    (out / 'loadind-report.json').write_text(json.dumps(rep, indent=1, default=str) + '\n')
    print('loadind.dat %d bytes sha256 %s; texture %s (%d bytes)' % (len(blob), rep['loadind_dat']['sha256'][:16], key,
                                                                    len(package)))


if __name__ == '__main__':
    main()
