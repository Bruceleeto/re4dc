#!/usr/bin/env python3
"""fx_ps2_pack.py: the PS2-sourced effect pack (test 12 fx lane, 10-14; runtime knob FX_PS2_PACK=1, TEX_PAL4_ALPHA=1).

  fx_ps2_pack.py <in tex.pak> <out tex.pak> <gc source tree> --set GCCTX=PS2DAT:ENTRY[:id,id,...] ... [--report r.json]

For each --set, the GameCube EFF texture table GCCTX (a le_mirror context such as etc/core.das:0#1 or st1/r101.arc#7)
is paired with the EFF block ENTRY of the PS2 .dat file PS2DAT (Core.dat / r101.dat, read from the USA disc's
BIO4DAT.AFS), by EFF texture id. For each selected id present in both, every GameCube picture's package (its key is
prepare_native_ui.image_identity of the source TPL image, so the game's lookup is unchanged) is replaced by the PS2
picture of the same frame: PSMT4 indices, PS2 CLUT alpha 0..0x80 -> 0..255, a transposed PS2 picture (TEX0 flag 1:
the PS2 renderer swaps U and V) turned back to the GameCube orientation. Each id's frames share ONE 16-colour palette
(the PS2 CLUTs differ per frame; a weighted k-means in premultiplied ARGB picks the 16), so an id costs one PVR palette
bank; the package is PAL4 ARGB4444 twiddled, and its header flags record the covered texels (bit 31 | w | h << 11) so
the runtime samples the smaller picture whole (native_ui.cpp RE4DC_COVER_W/H, FX_PS2_PACK=1).

A GameCube id with more frames than the PS2 one (r101 0xf4: 4 vs 1) maps frame i to PS2 frame i % n (the effect's own
frame count, timing and Rnd are the GameCube data, untouched). GameCube-only ids and unselected ids keep their package.
PS2-only ids are not referenced by the GameCube data and are not packed. Only the texture pack changes: no logic.
"""
import json, struct, sys, zlib
from pathlib import Path
here = Path(__file__).resolve().parent
sys.path.insert(0, str(here.parent))
sys.path.insert(0, str(here.parent.parent))
import texpack  # noqa: E402
import convert_tpl as C  # noqa: E402
import le_mirror as mirror  # noqa: E402
from prepare_native_ui import image_identity  # noqa: E402
from fx_pal4_pack import read_pak  # noqa: E402


def dat_entries(blob):
    n = struct.unpack_from('<I', blob, 0)[0]
    offs = struct.unpack_from('<%dI' % n, blob, 0x10)
    types = [blob[0x10 + 4 * n + 4 * i:0x10 + 4 * n + 4 * i + 4].rstrip(b'\0').decode('latin1') for i in range(n)]
    ends = list(offs[1:]) + [len(blob)]
    return [(types[i], offs[i], ends[i]) for i in range(n)]


def ps2_eff_textures(e):
    """{id: [picture]}, picture = (w, h, rgba list) in GameCube orientation, or None when not a linear PSMT4."""
    hdr = struct.unpack_from('<12I', e, 0)
    if hdr[0] != 0xB:
        raise ValueError('PS2 EFF version %#x' % hdr[0])
    o = hdr[1]
    n = struct.unpack_from('<I', e, o)[0]
    ids = [struct.unpack_from('<H', e, o + 4 + 8 * i)[0] for i in range(n)]
    o = hdr[6]
    if struct.unpack_from('<I', e, o)[0] != n:
        raise ValueError('PS2 EFF id / TPL table sizes differ')
    out = {}
    for i, tid in enumerate(ids):
        t = o + struct.unpack_from('<I', e, o + 4 + 4 * i)[0]
        magic, count, start = struct.unpack_from('<III', e, t)
        if magic != 0x1000:
            raise ValueError('PS2 TPL magic %#x' % magic)
        pics = []
        for k in range(count):
            d = t + start + 0x30 * k
            w, h, depth, inter = struct.unpack_from('<HHHH', e, d)
            io, po = struct.unpack_from('<II', e, d + 0x20)
            if depth != 8 or inter & ~1:
                pics.append(None)
                continue
            raw = e[t + io:t + io + w * h // 2]
            idx = []
            for b in raw:
                idx += (b & 15, b >> 4)
            clut = []
            for c in range(16):   # 8x2 CLUT in a 16-wide buffer: 0-7 at +0, 8-15 at +0x40
                q = t + po + (c if c < 8 else 16 + c - 8) * 4
                r, g, b, a = e[q:q + 4]
                clut.append((r, g, b, 255 if a >= 128 else a * 255 // 128))
            px = [clut[v] for v in idx]
            if inter & 1:   # transposed on the PS2: picture (x, y) is stored at (y, x)
                px = [px[x * w + y] for y in range(w) for x in range(h)]
                w, h = h, w
            pics.append((w, h, px))
        out[tid] = pics
    return out


def gc_eff_tables(src, files):
    """{ctx: [id]} and {ctx/tplN: [(key, w, h)]} for the GameCube EFF blocks in files (le_mirror's own traversal)."""
    ids, tpls = {}, {}
    orig = mirror.fmt_eff

    def wrap(sw, off, size, ctx):
        d = sw.data
        if struct.unpack_from('>I', d, off)[0] == 0xB:   # peek (big-endian source) before the block is converted
            o = off + struct.unpack_from('>I', d, off + 4)[0]
            n = struct.unpack_from('>I', d, o)[0]
            ids[ctx] = [struct.unpack_from('>H', d, o + 4 + 8 * i)[0] for i in range(n)]
        return orig(sw, off, size, ctx)

    def obs(file, offset, data, context):
        if len(data) >= 12 and struct.unpack_from('>II', data) == (C.TPL_MAGIC, 0):
            return
        try:
            imgs = C.parse_tpl(data)
        except (ValueError, IndexError, struct.error):
            return
        tpls[context] = [(image_identity(im)[0], im.width, im.height) for im in imgs]

    patched = [(tbl, k) for tbl in vars(mirror).values() if isinstance(tbl, dict) for k, v in tbl.items() if v is orig]
    prev = mirror.TPL_OBSERVER
    mirror.fmt_eff, mirror.TPL_OBSERVER = wrap, obs
    for tbl, k in patched:
        tbl[k] = wrap
    try:
        for f in files:
            data = (Path(src) / f).read_bytes()
            if f.endswith('.das') and f.startswith('st'):
                mirror.prepare_room_archive(f, data)
            else:
                mirror.convert_file(f, bytearray(data))
    finally:
        mirror.fmt_eff, mirror.TPL_OBSERVER = orig, prev
        for tbl, k in patched:
            tbl[k] = orig
    return ids, tpls


def premul(c):
    r, g, b, a = c
    return (r * a / 255.0, g * a / 255.0, b * a / 255.0, float(a))


def palette16(weights):
    """16 ARGB colours for {rgba: pixel count}: weighted k-means in premultiplied space (exact when <= 16 colours)."""
    cols = sorted(weights)
    if len(cols) <= 16:
        return cols
    pts = [premul(c) for c in cols]
    wts = [weights[c] for c in cols]

    def d2(p, q):
        return sum((x - y) ** 2 for x, y in zip(p, q))
    centres = [pts[max(range(len(pts)), key=lambda i: wts[i])]]   # deterministic farthest-point start
    while len(centres) < 16:
        centres.append(pts[max(range(len(pts)), key=lambda i: wts[i] * min(d2(pts[i], c) for c in centres))])
    for _ in range(30):
        acc = [[0.0] * 5 for _ in centres]
        for p, w in zip(pts, wts):
            j = min(range(len(centres)), key=lambda k: d2(p, centres[k]))
            a = acc[j]
            for t in range(4):
                a[t] += p[t] * w
            a[4] += w
        new = [tuple(a[t] / a[4] for t in range(4)) if a[4] else c for a, c in zip(acc, centres)]
        if new == centres:
            break
        centres = new
    out = []
    for r, g, b, a in centres:   # back to straight alpha
        if a < 0.5:
            out.append((0, 0, 0, 0))
        else:
            out.append(tuple(min(255, int(round(v * 255.0 / a))) for v in (r, g, b)) + (min(255, int(round(a))),))
    return out


def package(w, h, px, palette, cover):
    """A PAL4 ARGB4444 twiddled package of px (rgba) with the given palette; header flags = cover marker."""
    words = [C._pack_4444(c) for c in palette] + [0] * (16 - len(palette))
    pp = [premul(c) for c in palette]
    cache = {}

    def nearest(c):
        if c not in cache:
            p = premul(c)
            cache[c] = min(range(len(pp)), key=lambda k: sum((x - y) ** 2 for x, y in zip(p, pp[k])))
        return cache[c]
    idx = C.twiddle_16bpp([nearest(c) for c in px], w, h)
    payload = bytes(idx[i] | idx[i + 1] << 4 for i in range(0, len(idx), 2)) + struct.pack('<16H', *words)
    alphas = [palette[i][3] for i in set(idx)]
    flags = C.FLAG_ALPHA if any(a < 255 for a in alphas) else 0
    if flags and all(a in (0, 255) for a in alphas):
        flags |= C.FLAG_BINARY_ALPHA
    tex_off = C.HEADER.size
    data_off = tex_off + C.TEXTURE.size
    rec = C.TEXTURE.pack(b'ps2-source'.ljust(64, b'\0'), w, h, C.FORMAT_PAL4_ARGB4444, data_off, len(payload),
                         flags, C.PAYLOAD_TWIDDLED, 0)
    body = rec + payload
    hdr = C.HEADER.pack(C.MAGIC, C.VERSION, C.HEADER.size, C.TEXTURE.size, 1, tex_off, data_off, len(payload),
                        zlib.crc32(body) & 0xffffffff, 1, 1 << 31 | cover[0] | cover[1] << 11)
    err = 0.0
    for c in px:
        p, q = premul(c), pp[nearest(c)]
        err += max(abs(x - y) for x, y in zip(p, q))
    return hdr + body, err / len(px)


def main():
    a = sys.argv[1:]
    rep, sets = None, []
    while '--report' in a:
        i = a.index('--report'); rep = a[i + 1]; del a[i:i + 2]
    while '--set' in a:
        i = a.index('--set'); sets.append(a[i + 1]); del a[i:i + 2]
    src_pak, dst_pak, gc_tree = a
    specs = []
    for s in sets:
        ctx, rest = s.split('=', 1)
        parts = rest.split(':')
        sel = {int(v, 16) for v in parts[2].split(',')} if len(parts) > 2 and parts[2] else None
        specs.append((ctx, parts[0], int(parts[1]), sel))
    files = sorted({(c.split(':')[0].split('#')[0].replace('.arc', '.das')) for c, _, _, _ in specs})
    gc_ids, gc_tpls = gc_eff_tables(gc_tree, files)
    pkgs = read_pak(Path(src_pak).read_bytes())
    report = {'sets': [], 'replaced': 0, 'bytes_before': 0, 'bytes_after': 0}
    done = {}
    for ctx, dat, ent, sel in specs:
        blob = Path(dat).read_bytes()
        ty, s0, s1 = dat_entries(blob)[ent]
        if ty != 'EFF':
            raise SystemExit('%s entry %d is %s, not EFF' % (dat, ent, ty))
        ps2 = ps2_eff_textures(blob[s0:s1])
        if ctx not in gc_ids:
            raise SystemExit('no GameCube EFF table %s' % ctx)
        gids = gc_ids[ctx]
        entry = {'gc': ctx, 'ps2': '%s#%d' % (Path(dat).name, ent), 'ids': [],
                 'gc_only': ['0x%x' % t for t in gids if t not in ps2],
                 'ps2_only': ['0x%x' % t for t in ps2 if t not in gids]}
        for n, tid in enumerate(gids):
            if tid not in ps2 or (sel is not None and tid not in sel):
                continue
            gpics = gc_tpls.get('%s/tpl%d' % (ctx, n), [])
            ppics = ps2[tid]
            row = {'id': '0x%x' % tid, 'gc_frames': len(gpics), 'ps2_frames': len(ppics),
                   'gc_size': '%dx%d' % gpics[0][1:] if gpics else '', 'ps2_size': ''}
            if not gpics or any(p is None for p in ppics):
                row['skipped'] = 'PS2 picture is not linear PSMT4' if gpics else 'no GameCube pictures'
                entry['ids'].append(row)
                continue
            row['ps2_size'] = '%dx%d' % ppics[0][:2]
            weights = {}
            for w, h, px in ppics:
                for c in px:
                    weights[c] = weights.get(c, 0) + 1
            pal = palette16(weights)
            row['ps2_colours'] = len(weights)
            errs, before, after = [], 0, 0
            for f, (key, gw, gh) in enumerate(gpics):
                k = tuple(int(v, 16) for v in key.split('-'))
                if k not in pkgs:
                    row.setdefault('not_in_pack', []).append(key)
                    continue
                w, h, px = ppics[f % len(ppics)]
                if k in done and done[k] != (ctx, tid):
                    raise SystemExit('key %s shared by %s and %s' % (key, done[k], (ctx, tid)))
                blob2, err = package(w, h, px, pal, (w, h))
                before += len(pkgs[k]); after += len(blob2)
                pkgs[k] = blob2; done[k] = (ctx, tid); errs.append(err)
            row.update(replaced=len(errs), bytes_before=before, bytes_after=after,
                       mean_premul_err=round(sum(errs) / max(1, len(errs)), 2))
            report['replaced'] += len(errs); report['bytes_before'] += before; report['bytes_after'] += after
            entry['ids'].append(row)
        report['sets'].append(entry)
    out, _count = texpack.build(pkgs)
    texpack.verify(out)
    Path(dst_pak).write_bytes(out)
    for e in report['sets']:
        print('%s <- %s: gc-only %s ps2-only %s' % (e['gc'], e['ps2'], e['gc_only'], e['ps2_only']))
        for r in e['ids']:
            print('   ', json.dumps(r))
    print('fx_ps2_pack: %d packages replaced, %d -> %d bytes' % (report['replaced'], report['bytes_before'],
                                                                  report['bytes_after']))
    if rep:
        Path(rep).write_text(json.dumps(report, indent=1))


if __name__ == '__main__':
    main()
