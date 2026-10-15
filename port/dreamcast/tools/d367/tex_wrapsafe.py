#!/usr/bin/env python3
"""tex_wrapsafe.py <in tex.pak> <out tex.pak> [--keys k1,k2]  (lane crowd12, 2026-10-14; ledger G5)

Marks the texture packages whose texels are all one value (a uniform colour) as wrap-safe: header flags bit 30
(0x40000000). With TEX_WRAP_SAFE=1 (game30.mk) native_ui.cpp then draws a wrapping part whose image the converter
padded to a larger power of two (normally refused: "Repeating a padded image would repeat its border"). For a
uniform texture every sample is that colour whatever the wrap, padding or UV scale, so drawing it is exact.
Found in r101: cEmWindow id 0x46 type 3 (8-vertex glass part, 2x2 CMPR image padded to 8x8, key d3bab4c3-80a172d5,
every texel ARGB4444 0x3fff) was refused twice a frame in view (wrap) and its actor part once (resource): the asset
ledger's r101 14,464 wrap / 7,337 resource rejects.

Only single-texture packages with 16-bit texels (RGB565 / ARGB1555 / ARGB4444; linear or twiddled payload) are
checked; PAL4, VQ and mipmapped packages are left alone. The pack index (offsets, sizes, index CRC) is unchanged: the
header flags sit outside every CRC (payload_crc32 covers the bytes after the header). Prints each marked key.
--keys limits the marking to the listed keys (crc-fnv). Deterministic.
"""
import struct
import sys

FLAG_WRAP_SAFE = 0x40000000
HDR = struct.Struct('<8s10I')        # magic, version, header_size, texture_stride, texture_count, texture_offset,
                                     # data_offset, data_size, payload_crc32, source_image_count, flags
TEX = struct.Struct('<64s8I')        # material, width, height, format, data_offset, data_size, flags, payload, reserved


def main():
    args = sys.argv[1:]
    keys = None
    if '--keys' in args:
        i = args.index('--keys')
        keys = {tuple(int(x, 16) for x in k.split('-')) for k in args[i + 1].split(',')}
        del args[i:i + 2]
    src, dst = args
    blob = bytearray(open(src, 'rb').read())
    assert blob[:8] == b'RE4PAK1\x00', 'not a tex.pak'
    _, count, index_offset, _, _ = struct.unpack_from('<5I', blob, 8)
    marked = 0
    for i in range(count):
        crc, fnv, off, size = struct.unpack_from('<4I', blob, index_offset + 16 * i)
        if keys is not None and (crc, fnv) not in keys:
            continue
        h = HDR.unpack_from(blob, off)
        magic, version, hsize, tstride, tcount, toff = h[:6]
        flags = h[10]
        if magic != b'RE4DCTX\x00' or tcount != 1 or flags & FLAG_WRAP_SAFE:
            continue
        t = TEX.unpack_from(blob, off + toff)
        width, height, fmt, doff, dsize, tflags, payload = t[1:8]
        if fmt not in (0, 1, 2) or payload not in (0, 1) or tflags & 4 or dsize < 2 or doff + dsize > size:
            continue
        px = blob[off + doff:off + doff + dsize]
        if px != px[:2] * (dsize // 2):
            continue
        struct.pack_into('<I', blob, off + 44, flags | FLAG_WRAP_SAFE)
        marked += 1
        print('wrap-safe %08x-%08x %ux%u fmt %u texel %02x%02x' % (crc, fnv, width, height, fmt, px[1], px[0]))
    open(dst, 'wb').write(blob)
    print('%d of %d packages marked wrap-safe -> %s' % (marked, count, dst))


if __name__ == '__main__':
    main()
