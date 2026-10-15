#!/usr/bin/env python3
"""tex_size_check.py: offline gate for swapped pictures (lane objs, 2026-10-15; a standing gate in the
re4-dreamcast-testing checklist).

Runtime rule it models (game/platform/native_ui.cpp re4dc_model_packet_reserve): a model part that wraps S (T) is
dropped silently, counted as `native model rejection: ... wrap=N`, when its package's width (height) differs from the
image's TPL header width (height), unless the package says WRAP_SAFE (header flags bit 30). The objs13 look check found
four objects hidden this way (r104 gate, r10b / r11b island, r119 tree) while TEX_CHECK=2, LEON-GC and pair-missing
passed. FX_PS2_PACK packages may be smaller than their image on purpose (COVER: flags bit 31, cover size in bits 0-21);
the sprite path maps UVs through the cover size, the model wrap check does not, so COVER is reported separately.

Checks:
 1. every R4NREF / R4PREF texture record (magic, crc @8, fnv @12, width @16, height @20, format @24; NTR rows and
    TEX_REF_SELFKEY records alike) in the given containers (.dar payloads, .das, .drs, any file: scanned at 4-byte
    steps) against the package of its key: pak(s) first, then loose --texdir packages (the runtime's kNotInPack order).
      OK        package texture 0 has the record's width x height
      WRAPSAFE  sizes differ, package flags bit 30 (allowed by the runtime)
      COVER     sizes differ, package flags bit 31 (FX_PS2_PACK cover size; sprite path only)
      PAD       package = the record size padded to powers of two (the converters' NPOT rule; a wrapping part
                drops it unless WRAP_SAFE: tools/d367/tex_wrapsafe.py territory, the same in GC-texture builds)
      MISMATCH  sizes differ otherwise (e.g. a smaller or reordered PS2 picture): a wrapping model part using it
                is not drawn  -> FAIL
      MISSING   no package for the key (TEX_CHECK territory; listed, not a failure here)
    R4PW world part tables (.r4pw, PS2 world meshes) too: the world packet refuses any size difference, so there
    every non-OK, non-MISSING part is a MISMATCH ("world" classes).
 2. --keys TSV (key, width, height columns, e.g. ps2lib effects-tex/KEYS.tsv): the same classes per row.
 3. --objects-report ps2_objects_tex.py tex.json files: an image whose PS2 picture has another size than the GC image
    while another PS2 image of the TPL has the GC size (`order_suspect`) and the model has no ps2_objects.TEX_MAPS
    entry -> ORDER FAIL (the PS2 TPL lists the images in another order).

    tex_size_check.py [--pak P]... [--texdir D]... [--keys TSV]... [--objects-report JSON]... [file|dir]...
Exit 1 on any MISMATCH or ORDER failure."""
import argparse, json, struct, sys
from pathlib import Path

MAGICS = (b'R4NREF\0\0', b'R4PREF\0\0')
EXTS = ('.dar', '.das', '.drs', '.dat', '.re4nmr', '.bin', '.arc', '.r4pw')


def pkg_info(b):
    """RE4DCTX v2 -> (width, height, flags) of texture 0, or None."""
    if len(b) < 0x50 or b[:8] != b'RE4DCTX\0':
        return None
    flags = struct.unpack_from('<I', b, 44)[0]
    toff = struct.unpack_from('<I', b, 24)[0]
    if toff + 72 > len(b):
        return None
    w, h = struct.unpack_from("<2I", b, toff + 64)  # Texture: char name[64], then width, height, ...
    return w, h, flags


def read_pak(path):
    b = Path(path).read_bytes()
    ver, count, index_at, data_at, crc = struct.unpack_from('<5I', b, 8)
    out = {}
    for i in range(count):
        k0, k1, off, size = struct.unpack_from('<4I', b, 2048 + 16 * i)
        info = pkg_info(b[off:off + size])
        if info:
            out['%08x-%08x' % (k0, k1)] = info
    return out


def read_dir(d):
    out = {}
    for p in Path(d).rglob('*.re4tex'):
        info = pkg_info(p.read_bytes())
        if info:
            out[p.stem.lower()] = info
    return out


def records(b):
    for m in MAGICS:
        i = b.find(m)
        while i >= 0:
            if i % 4 == 0 and i + 28 <= len(b):
                crc, fnv, w, h, fmt = struct.unpack_from('<5I', b, i + 8)
                if 0 < w <= 1024 and 0 < h <= 1024 and fmt <= 15:
                    yield i, '%08x-%08x' % (crc, fnv), w, h, fmt, m[:6].decode()
            i = b.find(m, i + 4)


def classify(key, w, h, pak, loose):
    info = pak.get(key) or loose.get(key)
    if info is None:
        return 'MISSING', None
    pw, ph, fl = info
    if (pw, ph) == (w, h):
        return 'OK', info
    if fl >> 30 & 1:
        return 'WRAPSAFE', info
    if fl >> 31 & 1:
        return 'COVER', info
    if (pw, ph) == (pow2(w), pow2(h)):
        return 'PAD', info
    return 'MISMATCH', info


def pow2(n):
    p = 8
    while p < n:
        p *= 2
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pak', action='append', default=[]); ap.add_argument('--texdir', action='append', default=[])
    ap.add_argument('--keys', action='append', default=[]); ap.add_argument('--objects-report', action='append', default=[])
    ap.add_argument('--label', default=''); ap.add_argument('--verbose', action='store_true')
    ap.add_argument('inputs', nargs='*')
    a = ap.parse_args()
    pak, loose = {}, {}
    for p in a.pak:
        for k, v in read_pak(p).items():
            pak.setdefault(k, v)
    for d in a.texdir:
        loose.update(read_dir(d))
    files = []
    for x in a.inputs:
        p = Path(x)
        files += sorted(q for q in p.rglob('*') if q.is_file() and q.suffix.lower() in EXTS) if p.is_dir() else [p]
    tot = {}
    bad = []
    seen = set()
    for f in files:
        b = f.read_bytes()
        if b[:8] == b'R4DAR\0\0\0' or f.suffix.lower() == '.dar':
            try:
                kind, size, dest, off = struct.unpack_from('<4I', b, 0x20)
                if off + size <= len(b):
                    b = b[off:off + size]
            except struct.error:
                pass
        n = 0
        if b[:4] == b'R4PW':
            # PS2 world part table (tools/ps2_world_r4im.py): {u32 crc, fnv; u16 width, height; u8 pass, cull, tex, 0}
            # per part. re4dc_ps2_world_packet() refuses any size difference (no WRAP_SAFE / pad exemption).
            ver, npl, nparts = struct.unpack_from('<3I', b, 4)
            for i in range(nparts):
                crc, fnv, w, h = struct.unpack_from('<IIHH', b, 32 + 16 * i)
                key = '%08x-%08x' % (crc, fnv)
                n += 1
                if (key, w, h, 'w') in seen:
                    continue
                seen.add((key, w, h, 'w'))
                c, info = classify(key, w, h, pak, loose)
                if c not in ('OK', 'MISSING'):
                    c = 'MISMATCH'
                tot['world ' + c] = tot.get('world ' + c, 0) + 1
                if c == 'MISMATCH' or (a.verbose and c != 'OK'):
                    line = '%s %s %s part %d %dx%d package %s' % (c, key, f.name, i, w, h,
                                                              '%dx%d flags %08x' % info if info else '-')
                    print(line)
                    if c == 'MISMATCH':
                        bad.append(line)
        for off, key, w, h, fmt, mag in records(b):
            n += 1
            if (key, w, h) in seen:
                continue
            seen.add((key, w, h))
            c, info = classify(key, w, h, pak, loose)
            tot[c] = tot.get(c, 0) + 1
            if c == 'MISMATCH' or (a.verbose and c != 'OK'):
                line = '%s %s %s@%#x record %dx%d fmt %d package %s' % (c, key, f.name, off, w, h, fmt,
                                                                       '%dx%d flags %08x' % info if info else '-')
                print(line)
                if c == 'MISMATCH':
                    bad.append(line)
        if a.verbose:
            print('file %s: %d records' % (f, n))
    for t in a.keys:
        rows = [r.split('\t') for r in Path(t).read_text().splitlines()]
        hdr = rows[0]
        ik, iw, ih = hdr.index('key'), hdr.index('width'), hdr.index('height')
        for r in rows[1:]:
            if len(r) <= max(ik, iw, ih):
                continue
            key, w, h = r[ik].lower(), int(r[iw]), int(r[ih])
            if (key, w, h) in seen:
                continue
            seen.add((key, w, h))
            c, info = classify(key, w, h, pak, loose)
            tot['keys ' + c] = tot.get('keys ' + c, 0) + 1
            if c == 'MISMATCH':
                line = 'MISMATCH %s %s row %dx%d package %dx%d flags %08x' % (key, Path(t).name, w, h, *info)
                print(line); bad.append(line)
    for j in a.objects_report:
        rep = json.loads(Path(j).read_text())
        for i in rep.get('images', []):
            p2 = i.get('ps2', {})
            tot['images'] = tot.get('images', 0) + 1
            if 'order_suspect' not in p2:
                tot['images without order data'] = tot.get('images without order data', 0) + 1
                continue
            if p2['order_suspect'] and not p2.get('tex_map'):
                line = 'ORDER %s %s image %d: PS2 image %s is %s, GC %dx%d; PS2 images %s have the GC size: add TEX_MAPS' % (
                    rep.get('room'), i['model'], i['image'], i['ps2_image'], p2.get('ps2_size'), i['gc']['width'],
                    i['gc']['height'], p2['order_suspect'])
                print(line); bad.append(line)
    print('TEXSIZE %s %s: %s; packages pak %d loose %d; files %d' % (
        'FAIL' if bad else 'PASS', a.label, ', '.join('%s %d' % kv for kv in sorted(tot.items())) or 'nothing checked',
        len(pak), len(loose), len(files)))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
