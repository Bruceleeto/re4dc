#!/usr/bin/env python3
"""ps2tex_census.py <tex.pak> <ps2_world_data.inc> [run-output.txt ...]: every PS2 world texture key (ps2_textures[])
with its package format in the pak (payload linear/twiddled/VQ, 16-bit format, flags, VRAM bytes), and how often a
run loaded it. Lane vram12 (2026-10-14), read only."""
import re, struct, sys
sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[2]))
import convert_tpl as tpl

PAK_MAGIC = b'RE4PAK1' + bytes(1)


def pak_index(pak):
    magic, ver, count, ioff, doff = struct.unpack_from('<8s4I', pak, 0)
    assert magic == PAK_MAGIC, magic
    out = {}
    for i in range(count):
        c, f, o, n = struct.unpack_from('<4I', pak, ioff + 16 * i)
        out[(c, f)] = (o, n)
    return out


def main():
    pak = open(sys.argv[1], 'rb').read()
    idx = pak_index(pak)
    inc = open(sys.argv[2]).read()
    keys = [(int(a, 16), int(b, 16), int(w), int(h), int(al))
            for a, b, w, h, al in re.findall(r'\{0x([0-9a-f]{8})u,0x([0-9a-f]{8})u,(\d+),(\d+),(\d)', inc)]
    loads = {}
    for log in sys.argv[3:]:
        for m in re.finditer(r'native UI: load \S*/([0-9a-f]{8}-[0-9a-f]{8})\.re4tex', open(log, errors='replace').read()):
            loads[m.group(1)] = loads.get(m.group(1), 0) + 1
    tot16 = totvq = 0
    for crc, fnv, w, h, al in keys:
        name = '%08x-%08x' % (crc, fnv)
        if (crc, fnv) not in idx:
            print(name, 'NOT-IN-PAK')
            continue
        o, n = idx[(crc, fnv)]
        blob = pak[o:o + n]
        hdr = tpl.HEADER.unpack_from(blob)
        count, toff = hdr[4], hdr[5]
        _, tw, th, fmt, doff, dsize, flags, payload, _ = tpl.TEXTURE.unpack_from(blob, toff)
        kind = {0: 'linear', 1: 'twiddled', 2: 'VQ'}.get(payload, str(payload))
        if payload == 2:
            totvq += dsize
        else:
            tot16 += dsize
        print('%s %4dx%-4d alpha=%d fmt=%d %-8s flags=%#06x count=%d bytes=%d loads=%d' % (
            name, tw, th, al, fmt, kind, flags, count, dsize, loads.get(name, 0)))
    print('keys', len(keys), '16-bit bytes', tot16, 'VQ bytes', totvq)


if __name__ == '__main__':
    main()
