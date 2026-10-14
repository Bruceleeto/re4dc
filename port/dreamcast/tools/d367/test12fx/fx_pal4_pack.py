#!/usr/bin/env python3
"""fx_pal4_pack.py <in tex.pak> <out tex.pak> <keys.txt> [--report out.json]: the effect flipbook data-layout fix
(test 12 fx lane, 10-14). Every listed key (crc-fnv, one per line: the effect textures a benchmark run reloads) whose
native package is a base-level twiddled ARGB4444 picture is rewritten as an exact PAL4 package: lossless (every texel
word is kept), a quarter of the VRAM, 16 palette words appended (convert_tpl.package_exact_pal4_argb4444's layout).
Pictures are grouped so each group's texel words fit one 16-entry palette (a flipbook's frames share their GameCube
CLUT), and every picture of a group carries the group's palette: identical palettes share one PVR palette bank at run
time (room/texture_package.cpp, TEX_PAL4_ALPHA=1), so 64 banks hold the whole set. Unlisted packages and pictures with
more than 16 words stay byte-identical. Prints converted / skipped counts, groups (= banks) and VRAM saved."""
import json, struct, sys, zlib
from pathlib import Path
here = Path(__file__).resolve().parent
sys.path.insert(0, str(here.parent))
sys.path.insert(0, str(here.parent.parent))
import texpack  # noqa: E402
import convert_tpl as C  # noqa: E402


def read_pak(blob):
    magic, version, count, index_off, data_off, _crc = struct.unpack_from('<8sIIIII', blob, 0)
    assert magic == b'RE4PAK1\0' and version == 1, 'not a tex.pak'
    out = {}
    for i in range(count):
        crc, fnv, off, size = struct.unpack_from('<IIII', blob, index_off + 16 * i)
        out[(crc, fnv)] = blob[off:off + size]
    return out


def words_of(native):
    """The texel words of a canonical one-descriptor ARGB4444 twiddled package (ValueError otherwise)."""
    C.package_exact_pal4_argb4444(native)   # its checks (shape, CRC, format); result unused
    h = C.HEADER.unpack_from(native)
    t = C.TEXTURE.unpack_from(native, h[5])
    return struct.unpack_from('<%dH' % (t[1] * t[2]), native, t[4])


def pal4(native, palette):
    """package_exact_pal4_argb4444 with a given (shared) palette that holds every texel word."""
    h = list(C.HEADER.unpack_from(native))
    t = list(C.TEXTURE.unpack_from(native, h[5]))
    _, w, hh, fmt, off, size, flags, layout, reserved = t
    words = struct.unpack_from('<%dH' % (w * hh), native, off)
    d = {word: i for i, word in enumerate(palette)}
    indices = bytes(d[words[i]] | d[words[i + 1]] << 4 for i in range(0, len(words), 2))
    payload = indices + struct.pack('<16H', *(list(palette) + [0] * (16 - len(palette))))
    t[3], t[5] = C.FORMAT_PAL4_ARGB4444, len(payload)
    body = C.TEXTURE.pack(*t) + payload
    h[7], h[8] = len(payload), zlib.crc32(body) & 0xffffffff
    return C.HEADER.pack(*h) + body, size - len(payload)


def main():
    a = sys.argv[1:]
    rep = None
    if '--report' in a:
        i = a.index('--report'); rep = a[i + 1]; del a[i:i + 2]
    src, dst, keyfile = a
    pkgs = read_pak(Path(src).read_bytes())
    keys = []
    for line in Path(keyfile).read_text().split():
        c, f = line.split('-')
        keys.append((int(c, 16), int(f, 16)))
    skipped, cand = {}, []
    for k in keys:
        if k not in pkgs:
            skipped['not in pack'] = skipped.get('not in pack', 0) + 1
            continue
        try:
            ws = words_of(pkgs[k])
        except ValueError as e:
            skipped[str(e)] = skipped.get(str(e), 0) + 1
            continue
        cand.append((k, set(ws)))
    # greedy grouping, biggest word sets first: a picture joins the first group whose union stays <= 16 words
    groups = []
    for k, ws in sorted(cand, key=lambda x: (-len(x[1]), x[0])):
        if len(ws) > 16:
            skipped['more than 16 distinct ARGB4444 words'] = skipped.get('more than 16 distinct ARGB4444 words', 0) + 1
            continue
        for g in groups:
            if len(g['words'] | ws) <= 16:
                g['words'] |= ws; g['keys'].append(k); break
        else:
            groups.append({'words': set(ws), 'keys': [k]})
    done, saved = [], 0
    for gi, g in enumerate(groups):
        palette = sorted(g['words'])
        for k in g['keys']:
            pkgs[k], s = pal4(pkgs[k], palette)
            saved += s
            done.append({'key': '%08x-%08x' % k, 'group': gi, 'saved_bytes': s})
    blob, _count = texpack.build(pkgs)
    texpack.verify(blob)
    Path(dst).write_bytes(blob)
    print('fx_pal4_pack: %d converted in %d palette groups (banks), %d KB VRAM saved; skipped %s' %
          (len(done), len(groups), saved // 1024, json.dumps(skipped)))
    if rep:
        Path(rep).write_text(json.dumps({'converted': done, 'groups': [sorted('%08x-%08x' % k for k in g['keys'])
                                          for g in groups], 'skipped': skipped, 'saved_bytes': saved}, indent=1))


if __name__ == '__main__':
    main()
