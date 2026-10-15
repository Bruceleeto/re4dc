#!/usr/bin/env python3
"""fxtrim.py --fixture FIX.json [--min-gain F] [--out INC] [--report JSON] LOG...: the FX_SPRITE_TRIM table.

Reads the `fxtrim key:` lines of FX_SPRITE_TRIM_DIAG=1 run logs (every effect texture key the native sprite path drew,
with its blend), finds each key's .re4tex package on the fixture's disc data (dc/tex.pak, else the loose
dc/tex/<c>/<key>.re4tex), decodes its first texture (ARGB1555 / ARGB4444 / PAL4_ARGB4444; linear, twiddled or VQ;
RGB565 is opaque and never trimmed) and writes platform/include/fx_sprite_trim_table.inc: per key the bounding box of
the texels with alpha > 0, widened by 1 texel on each side for the bilinear filter (x1 / y1 exclusive, clamped to the
texture). A pixel the runtime no longer draws therefore samples only alpha-0 texels: with the blends fxtrim.mk allows
(SRCALPHA with INVSRCALPHA or ONE) it left the frame buffer unchanged before too.
Only keys seen at least once with an allowed blend (the runtime checks each sprite's blend again), and whose box or octagon saves at least --min-gain of the texture area (default 0.05), are
written (gain = the share of the drawn image area outside the box). Stdlib only (no numpy). Deterministic: the same inputs give the same bytes."""
import argparse, json, re, struct, sys, zlib
from pathlib import Path

HEADER = struct.Struct('<8s10I')
TEXTURE = struct.Struct('<64s8I')
KEYLINE = re.compile(r'fxtrim key: ([0-9a-f]{8})-([0-9a-f]{8}) img=(\d+)x(\d+) tex=(\d+)x(\d+) fmt=(\d+) pay=(\d+) '
                     r'src=(\d+) dst=(\d+) pad=(\d+) screen=(\d+)')


def twiddle(x, y, w, h):
    """PVR twiddled offset of texel (x, y): Morton order per min(w, h) square, squares side by side."""
    m = min(w, h)
    loc = ((x // m) + (y // m)) * m * m
    xi, yi, bit, sh = x & (m - 1), y & (m - 1), 1, 0
    while bit < m:
        if yi & bit:
            loc += 1 << (2 * sh)
        if xi & bit:
            loc += 2 << (2 * sh)
        bit <<= 1
        sh += 1
    return loc


def alpha_of(word, fmt):
    if fmt == 1:
        return 255 if word & 0x8000 else 0
    if fmt in (2, 4):
        return (word >> 12) * 17
    return 255   # RGB565


def decode_alpha(pkg):
    """-> (width, height, format, alpha rows) of the package's first texture."""
    magic, _v, _hs, stride, count, toff, _doff, _dlen, _crc, _n, _f = HEADER.unpack_from(pkg, 0)
    if magic != b'RE4DCTX\0' or count < 1:
        raise ValueError('not a re4tex')
    _name, w, h, fmt, off, size, _flags, payload, _r = TEXTURE.unpack_from(pkg, toff)
    raw = pkg[off:off + size]
    A = [[0] * w for _ in range(h)]
    if fmt == 4:   # PAL4: twiddled 4-bit indices, then 16 ARGB4444 colours
        pal = struct.unpack_from('<16H', raw, len(raw) - 32)
        for y in range(h):
            for x in range(w):
                loc = twiddle(x, y, w, h)
                A[y][x] = alpha_of(pal[(raw[loc // 2] >> (4 * (loc % 2))) & 15], 4)
    elif payload == 2:   # VQ: 256 x 4-texel codebook, twiddled index of 2x2 blocks
        cb = struct.unpack_from('<1024H', raw, 0)
        idx = raw[2048:]
        for by in range(h // 2):
            for bx in range(w // 2):
                c = idx[twiddle(bx, by, w // 2, h // 2)] * 4
                # codebook entry order: (0,0) (0,1)=row 1 (1,0)=col 1 (1,1)
                A[2 * by][2 * bx] = alpha_of(cb[c], fmt)
                A[2 * by + 1][2 * bx] = alpha_of(cb[c + 1], fmt)
                A[2 * by][2 * bx + 1] = alpha_of(cb[c + 2], fmt)
                A[2 * by + 1][2 * bx + 1] = alpha_of(cb[c + 3], fmt)
    else:
        words = struct.unpack_from('<%dH' % (w * h), raw, 0)
        for y in range(h):
            for x in range(w):
                A[y][x] = alpha_of(words[twiddle(x, y, w, h) if payload == 1 else y * w + x], fmt)
    return w, h, fmt, A


def box(A, w, h):
    """Box (x0, y0, x1, y1) and octagon (s0, s1, d0, d1) of the UV points a texel with alpha > 0 can reach.
    Bilinear: texel (a, b) feeds the UV points (texel units) within 1 of its centre, x in (a - 0.5, a + 1.5); the
    box keeps 0.5 texel spare: [a - 1, a + 2). For x + y that square spans (a + b - 1, a + b + 3), for x - y
    (a - b - 2, a - b + 2); with the same 0.5 spare, rounded outward: s0 = min - 2, s1 = max + 4, d0 = min - 3,
    d1 = max + 3. The octagon is (0, 0, 0, 0) (not used) when its clamped vertices would not run clockwise."""
    pts = [(x, y) for y in range(h) for x in range(w) if A[y][x]]
    if not pts:
        return None
    x0 = max(0, min(p[0] for p in pts) - 1); x1 = min(w, max(p[0] for p in pts) + 2)
    y0 = max(0, min(p[1] for p in pts) - 1); y1 = min(h, max(p[1] for p in pts) + 2)
    s0 = min(p[0] + p[1] for p in pts) - 2; s1 = max(p[0] + p[1] for p in pts) + 4
    d0 = min(p[0] - p[1] for p in pts) - 3; d1 = max(p[0] - p[1] for p in pts) + 3
    X, Y = octagon(x0, y0, x1, y1, s0, s1, d0, d1)
    if not (X[0] <= X[1] and Y[2] <= Y[3] and X[5] <= X[4] and Y[7] <= Y[6]):
        s0 = s1 = d0 = d1 = 0
    return x0, y0, x1, y1, s0, s1, d0, d1


def octagon(x0, y0, x1, y1, s0, s1, d0, d1):
    """fx_sprite_trim.inc fx_trim_octagon: the 8 vertices, clockwise from the top edge's left end, clamped."""
    def cl(v, lo, hi):
        return lo if v < lo else hi if v > hi else v
    X = [cl(s0 - y0, x0, x1), cl(d1 + y0, x0, x1), x1, x1, cl(s1 - y1, x0, x1), cl(d0 + y1, x0, x1), x0, x0]
    Y = [y0, y0, cl(x1 - d1, y0, y1), cl(s1 - x1, y0, y1), y1, y1, cl(x0 - d0, y0, y1), cl(s0 - x0, y0, y1)]
    return X, Y


def area(X, Y):
    return abs(sum(X[i] * Y[(i + 1) % 8] - X[(i + 1) % 8] * Y[i] for i in range(8))) / 2.0


def pak_index(path):
    b = Path(path).read_bytes()
    magic, _ver, count, ioff, _doff, icrc = struct.unpack_from('<8s5I', b, 0)
    if magic != b'RE4PAK1\0':
        raise SystemExit('%s: not a tex.pak' % path)
    index = b[ioff:ioff + (count * 16 + 2047) // 2048 * 2048]   # the crc covers the zero-padded sectors
    if zlib.crc32(index) & 0xffffffff != icrc:
        raise SystemExit('%s: index crc mismatch' % path)
    out = {}
    for i in range(count):
        c, f, o, s = struct.unpack_from('<4I', index, 16 * i)
        out[(c, f)] = (o, s)
    return b, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--fixture', required=True)
    ap.add_argument('--min-gain', type=float, default=0.05)
    ap.add_argument('--out')
    ap.add_argument('--report')
    ap.add_argument('logs', nargs='+')
    a = ap.parse_args()
    seen = {}
    for lp in a.logs:
        for line in open(lp, 'rb'):
            m = KEYLINE.search(line.decode('latin-1', 'replace'))
            if not m:
                continue
            g = m.groups()
            key = (int(g[0], 16), int(g[1], 16))
            src, dst, pad, screen = int(g[8]), int(g[9]), int(g[10]), int(g[11])
            r = seen.setdefault(key, dict(img=(int(g[2]), int(g[3])), tex=(int(g[4]), int(g[5])), fmt=int(g[6]),
                                          pay=int(g[7]), blends=set(), logs=set()))
            r['blends'].add((src, dst, pad, screen))
            r['logs'].add(Path(lp).parent.parent.name)
    fix = json.load(open(a.fixture))
    rep = fix['replace']
    pak = rep.get('dc/tex.pak')
    pb, pidx = pak_index(pak) if pak else (None, {})
    rows, report = [], []
    for key in sorted(seen):
        r = seen[key]
        name = '%08x-%08x' % key
        ok_blend = any(s == 4 and d in (1, 5) and not (p & 1) for s, d, p, _sc in r['blends'])
        if key in pidx:
            o, s = pidx[key]
            pkg, where = pb[o:o + s], 'tex.pak'
        else:
            lp = rep.get('dc/tex/%s/%s.re4tex' % (name[0], name))
            if not lp:
                report.append(dict(key=name, status='package not found'))
                continue
            pkg, where = Path(lp).read_bytes(), lp
        w, h, fmt, A = decode_alpha(pkg)
        if (w, h) != tuple(r['tex']):
            report.append(dict(key=name, status='size mismatch %dx%d vs log %s' % (w, h, r['tex'])))
            continue
        b = box(A, w, h)
        iw, ih = r['img']   # the sprite shows the image part [0, iw) x [0, ih) of the (padded) texture
        barea = max(0, min(b[2], iw) - b[0]) * max(0, min(b[3], ih) - b[1]) if b else 0
        gain = 1.0 - barea / float(iw * ih)
        oct_gain = None
        if b and b[5] > b[4] and (iw, ih) == (w, h):
            oct_gain = round(1.0 - area(*octagon(*b)) / float(w * h), 3)
        best = max(gain, oct_gain or 0.0)
        st = 'trim' if b and ok_blend and best >= a.min_gain else ('blend' if not ok_blend else 'small gain')
        report.append(dict(key=name, status=st, tex=[w, h], fmt=fmt, box=list(b) if b else None,
                           gain=round(gain, 3), oct_gain=oct_gain, blends=sorted(r['blends']),
                           runs=sorted(r['logs']), source=where))
        if st == 'trim':
            rows.append((key, b))
    text = ['// Generated by tools/d367/fxtrim/fxtrim.py (FX_SPRITE_TRIM, fxtrim.mk): per effect texture key the',
            '// box (x0, y0, x1, y1; x1 / y1 exclusive) and octagon (s0, s1, d0, d1) of the UV its alpha > 0 texels',
            '// can reach through the bilinear filter, + 0.5 texel spare; sorted by (crc, fnv). Do not edit.',
            'constexpr unsigned kFxTrimCount=%d;' % len(rows)]
    if rows:
        text.append('const FxTrimRect kFxTrim[kFxTrimCount]={')
        for (c, f), b in rows:
            text.append('    {0x%08xU,0x%08xU,%d,%d,%d,%d,%d,%d,%d,%d},' % ((c, f) + tuple(b)))
        text.append('};')
    else:
        text.append('const FxTrimRect* const kFxTrim=nullptr;')
    body = '\n'.join(text) + '\n'
    if a.out:
        Path(a.out).write_text(body)
    else:
        sys.stdout.write(body)
    if a.report:
        json.dump(report, open(a.report, 'w'), indent=1, default=list)
    for r in report:
        print('%s %-10s %s gain=%s oct=%s box=%s blends=%s' % (r['key'], r['status'], r.get('tex'), r.get('gain'),
                                                                r.get('oct_gain'), r.get('box'), r.get('blends')),
              file=sys.stderr)
    print('fxtrim: %d keys seen, %d trimmed' % (len(seen), len(rows)), file=sys.stderr)


if __name__ == '__main__':
    main()
