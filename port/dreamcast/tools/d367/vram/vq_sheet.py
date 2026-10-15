#!/usr/bin/env python3
"""vq_sheet.py <work dir> <out.png> [scale] [crop x0,y0,x1,y1]: one row per re-encoded texture: 16-bit source | VQ |
4x amplified difference, over a checkerboard (alpha shown), labelled with key, size, format, bytes and PSNR
(vq-report.json). Lane vram12 (2026-10-14)."""
import json, sys, pathlib
from PIL import Image, ImageDraw, ImageChops

work = pathlib.Path(sys.argv[1]); out = sys.argv[2]
scale = int(sys.argv[3]) if len(sys.argv) > 3 else 2
crop = tuple(int(v) for v in sys.argv[4].split(',')) if len(sys.argv) > 4 else None
rep = json.loads((work / 'vq-report.json').read_text())['images']


def checker(w, h, c=8):
    im = Image.new('RGBA', (w, h), (200, 200, 200, 255)); d = ImageDraw.Draw(im)
    for y in range(0, h, c):
        for x in range(0, w, c):
            if (x // c + y // c) % 2: d.rectangle([x, y, x + c - 1, y + c - 1], fill=(150, 150, 150, 255))
    return im


rows = []
for e in rep:
    k = e['key']
    a = Image.open(work / 'previews' / (k + '.png')).convert('RGBA')
    b = Image.open(work / 'previews' / (k + '-vq.png')).convert('RGBA')
    if crop:
        a, b = a.crop(crop), b.crop(crop)
    w, h = a.size
    W, H = w * scale, h * scale
    tiles = []
    for im in (a, b):
        bg = checker(W, H); bg.alpha_composite(im.resize((W, H), Image.NEAREST)); tiles.append(bg)
    diff = ImageChops.difference(a.convert('RGB'), b.convert('RGB')).point(lambda v: min(255, v * 4))
    tiles.append(diff.resize((W, H), Image.NEAREST).convert('RGBA'))
    label = '%s %dx%d %s %d -> %d B  PSNR %.1f dB   [16-bit | VQ | diff x4]' % (
        k, e['native_width'], e['native_height'], e['format'], e['before_vram'], e['after_vram'], e['psnr_db'])
    row = Image.new('RGBA', (3 * W + 20, H + 18), (255, 255, 255, 255))
    ImageDraw.Draw(row).text((2, 2), label, fill=(0, 0, 0, 255))
    for i, t in enumerate(tiles):
        row.paste(t, (i * (W + 10), 18))
    rows.append(row)
sw = max(r.size[0] for r in rows); sh = sum(r.size[1] + 6 for r in rows)
sheet = Image.new('RGBA', (sw, sh), (255, 255, 255, 255)); y = 0
for r in rows:
    sheet.paste(r, (0, y)); y += r.size[1] + 6
sheet.convert('RGB').save(out)
print(out, sheet.size)
