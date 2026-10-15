#!/usr/bin/env python3
"""tex_merge.py <base tex.pak> <out tex.pak> <lane tex.pak>...  (lane crowd12, 2026-10-14)

Merges lanes' tex.pak builds that were each made from the same base pack: every key whose package differs from the
base (or that the base lacks) is taken from the lane pack that changed it; untouched keys stay as in the base. Two
lanes changing the same key to different bytes is refused (names the key), so the merge never picks a winner
silently. Deterministic (texpack.build). Prints, per lane, how many keys it contributed.
Example (STACK v3): base tex-t11.pak + fx12 tex-t11-ps2lib.pak (PS2 effect pictures) + vram12 tex-vr12-ps2vq.pak
(r101 world VQ).
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import texpack  # noqa: E402


def read(path):
    blob = open(path, 'rb').read()
    assert blob[:8] == b'RE4PAK1\x00', path
    _, count, index_offset, _, _ = struct.unpack_from('<5I', blob, 8)
    out = {}
    for i in range(count):
        crc, fnv, off, size = struct.unpack_from('<4I', blob, index_offset + 16 * i)
        out[(crc, fnv)] = bytes(blob[off:off + size])
    return out


def main():
    base_path, out_path, *lanes = sys.argv[1:]
    base = read(base_path)
    merged = dict(base)
    owner = {}
    for lane in lanes:
        pk = read(lane)
        n = 0
        for key, data in pk.items():
            if base.get(key) == data:
                continue
            if key in owner and merged[key] != data:
                raise SystemExit('tex_merge: %08x-%08x changed differently by %s and %s' % (key[0], key[1], owner[key], lane))
            merged[key] = data
            owner[key] = lane
            n += 1
        gone = [k for k in base if k not in pk]
        print('%s: %d keys changed or added, %d base keys absent (kept from base)' % (lane, n, len(gone)))
    blob, _ = texpack.build(merged)
    open(out_path, 'wb').write(blob)
    print('merged %d packages -> %s' % (len(merged), out_path))


if __name__ == '__main__':
    main()
