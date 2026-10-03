#!/usr/bin/env python3
"""texpack.py <staged disc.bin | dc/tex directory> <out tex.pak>: every dc/tex/<n>/<crc>-<fnv>.re4tex in one file.
texpack.py --verify <tex.pak>: the runtime's checks (texpack_index.inc) plus every package's magic; exit 1 if invalid.

TEX_PACK (game30.mk, native_ui.cpp texpack::) reads it instead of opening one file per texture (IO_PROBE, r100 room
entry: 130 opens were 3.9 of 6.5 s, 234 directory-sector reads). Layout, little-endian:
  [0, 2048)            header: "RE4PAK1\\0", u32 version 1, u32 count, u32 index_offset (2048), u32 data_offset,
                       u32 index_crc32 (zlib.crc32 of the index bytes), zero padding
  [2048, data_offset)  index sorted by (crc, fnv) as unsigned: {u32 crc, u32 fnv, u32 offset, u32 size}, zero padded
                       to 2048 (128 entries per sector; the runtime keeps the first key of each sector)
  [data_offset, end)   each package byte for byte at a 2048-byte boundary, in index order
At most MAX_COUNT (8,192) packages: the runtime keeps the first key of at most 64 index sectors and rejects a larger
count (texpack_index.inc). Two copies of one key must be byte-identical (a dc/tex key in two directories); different
bytes under one key are refused instead of one silently replacing the other.
Deterministic: the same packages give the same bytes. route/pack-fixture.sh stages a fixture, packs its disc and
derives the fixture that ships dc/tex.pak without the packed loose files (texlow/ and the media overlay's dc/tex
files stay loose).
"""
import hashlib, re, struct, sys, zlib
from pathlib import Path

NAME = re.compile(r'^([0-9a-f]{8})-([0-9a-f]{8})\.re4tex$')
MAX_COUNT = 64 * 128   # the runtime's index capacity (texpack_index.inc kMaxSectors * 128)


def add(out, key, data, where):
    old = out.get(key)
    if old is not None and old != data:
        raise SystemExit('texpack: %08x-%08x has two different packages (%s)' % (key[0], key[1], where))
    out[key] = data


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
            add(out, (int(m.group(1), 16), int(m.group(2), 16)), buf.getvalue(), root + '/' + f)
    iso.close()
    return out


def from_dir(d):
    out = {}
    for p in sorted(Path(d).rglob('*.re4tex')):
        m = NAME.match(p.name.lower())
        if m:
            add(out, (int(m.group(1), 16), int(m.group(2), 16)), p.read_bytes(), str(p))
    return out


def build(pkgs):
    keys = sorted(pkgs)
    count = len(keys)
    if not 1 <= count <= MAX_COUNT:
        raise SystemExit('texpack: %d packages; the runtime index takes 1..%d' % (count, MAX_COUNT))
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


def verify(blob):
    """The checks the runtime makes before it uses a pack (texpack_index.inc), plus each package's magic.
    Returns (count, index_crc32); raises SystemExit naming the first problem."""
    def bad(why):
        raise SystemExit('texpack: invalid pack: ' + why)
    if len(blob) < 2048 or blob[:8] != b'RE4PAK1\x00':
        bad('magic')
    ver, count, index_at, data_at, crc = struct.unpack_from('<5I', blob, 8)
    if ver != 1:
        bad('version %d' % ver)
    if not 1 <= count <= MAX_COUNT:
        bad('count %d' % count)
    if index_at != 2048:
        bad('index offset %d' % index_at)
    sectors = (count * 16 + 2047) // 2048
    index_end = 2048 + 2048 * sectors
    if data_at < index_end or data_at % 2048 or data_at > len(blob):
        bad('data offset %d' % data_at)
    if zlib.crc32(blob[2048:index_end]) != crc:
        bad('index crc')
    prev = None
    for i in range(count):
        k0, k1, off, size = struct.unpack_from('<4I', blob, 2048 + 16 * i)
        if prev is not None and not prev < (k0, k1):
            bad('key order at entry %d' % i)
        if not size or off % 2048 or off < data_at or off + size > len(blob):
            bad('entry %d extent %d+%d' % (i, off, size))
        if blob[off:off + 8] != b'RE4DCTX\x00':
            bad('entry %d is not a texture package' % i)
        prev = (k0, k1)
    return count, crc


def main():
    if len(sys.argv) == 3 and sys.argv[1] == '--verify':
        blob = Path(sys.argv[2]).read_bytes()
        count, crc = verify(blob)
        print('texpack: valid, %d packages, %d bytes, index crc %08x, sha256 %s' % (
            count, len(blob), crc, hashlib.sha256(blob).hexdigest()))
        return
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
