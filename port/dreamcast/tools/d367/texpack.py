#!/usr/bin/env python3
"""texpack.py <staged disc.bin | dc/tex directory> <out tex.pak>: every dc/tex/<n>/<crc>-<fnv>.re4tex in one file.

TEX_PACK (game30.mk, native_ui.cpp texpack::) reads it instead of opening one file per texture (IO_PROBE, r100 room
entry: 130 opens were 3.9 of 6.5 s, 234 directory-sector reads). Layout, little-endian:
  [0, 2048)            header: "RE4PAK1\\0", u32 version 1, u32 count, u32 index_offset (2048), u32 data_offset,
                       u32 index_crc32 (zlib.crc32 of the index bytes), zero padding
  [2048, data_offset)  index sorted by (crc, fnv) as unsigned: {u32 crc, u32 fnv, u32 offset, u32 size}, zero padded
                       to 2048 (128 entries per sector; the runtime keeps the first key of each sector)
  [data_offset, end)   each package byte for byte at a 2048-byte boundary, in index order
Deterministic: the same packages give the same bytes. route/pack-fixture.sh stages a fixture, packs its disc and
derives the fixture that ships dc/tex.pak without the packed loose files (texlow/ and the media overlay's dc/tex
files stay loose).
"""
import hashlib, re, struct, sys, zlib
from pathlib import Path

NAME = re.compile(r'^([0-9a-f]{8})-([0-9a-f]{8})\.re4tex$')


def from_disc(disc):
    import pycdlib
    from io import BytesIO
    iso = pycdlib.PyCdlib()
    iso.open(str(disc))
    out = {}
    for root, _dirs, files in iso.walk(joliet_path='/dc/tex'):
        for f in files:
            m = NAME.match(f.lower())
            if not m:
                continue
            buf = BytesIO()
            iso.get_file_from_iso_fp(buf, joliet_path=root.rstrip('/') + '/' + f)
            out[(int(m.group(1), 16), int(m.group(2), 16))] = buf.getvalue()
    iso.close()
    return out


def from_dir(d):
    out = {}
    for p in sorted(Path(d).rglob('*.re4tex')):
        m = NAME.match(p.name.lower())
        if m:
            out[(int(m.group(1), 16), int(m.group(2), 16))] = p.read_bytes()
    return out


def build(pkgs):
    keys = sorted(pkgs)
    count = len(keys)
    index_bytes = (count * 16 + 2047) // 2048 * 2048
    data_offset = 2048 + index_bytes
    index, data, off = bytearray(), bytearray(), data_offset
    for k in keys:
        b = pkgs[k]
        if b[:8] != b'RE4DCTX\x00':
            raise SystemExit('not a texture package: %08x-%08x' % k)
        index += struct.pack('<4I', k[0], k[1], off, len(b))
        pad = (-len(b)) % 2048
        data += b + bytes(pad)
        off += len(b) + pad
    index += bytes(index_bytes - len(index))
    head = b'RE4PAK1\x00' + struct.pack('<5I', 1, count, 2048, data_offset, zlib.crc32(bytes(index)))
    head += bytes(2048 - len(head))
    return bytes(head) + bytes(index) + bytes(data), count


def main():
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    src, out = Path(sys.argv[1]), Path(sys.argv[2])
    pkgs = from_dir(src) if src.is_dir() else from_disc(src)
    if not pkgs:
        raise SystemExit('no dc/tex packages in %s' % src)
    blob, count = build(pkgs)
    out.write_bytes(blob)
    print('texpack: %d packages, %d bytes (payload %d), sha256 %s' % (
        count, len(blob), sum(len(b) for b in pkgs.values()), hashlib.sha256(blob).hexdigest()))


if __name__ == '__main__':
    main()
