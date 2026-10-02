#!/usr/bin/env python3
"""Lane crowd: a look sheet from CROWD_FREEZE captures (looks.sh / crun.sh).

sheet.py <out.png> <title> <label>=<scenario dir>[:<fb>[:<n>]] ...   (n: the n-th held frame, default 1)

For each scenario (<harness>/scenarios/cw-look-<arm>-<view>), finds the held frame: the longest run of consecutive
screenshot slots (capture/shots/tNNNN/frames/fbN.png) with identical bytes after boot (slot > 30 s), and tiles the
chosen framebuffer (default fb0) of every arm under its label, with the md5 of the image so identical tiles are
visible as identical. The game frame is the one CROWD_FREEZE logged (capture/run-output.txt).
"""
import hashlib
import re
import sys
from pathlib import Path
from PIL import Image, ImageDraw


def held(scen, fb, idx=1):
    """the idx-th (1-based) run of >= 2 consecutive identical screenshots after 30 s"""
    shots = sorted((Path(scen) / 'capture' / 'shots').glob('t*'))
    runs, run, prev = [], [], None
    for s in shots:
        p = s / 'frames' / f'{fb}.png'
        if not p.exists() or int(s.name[1:]) < 30:
            prev = None; run = []
            continue
        h = hashlib.md5(p.read_bytes()).hexdigest()
        if h == prev:
            run.append(p)
            if len(run) == 2: runs.append(run)
        else:
            run = [p]
        prev = h
    return runs[idx - 1][0] if len(runs) >= idx else None


def frozen(scen):
    t = (Path(scen) / 'capture' / 'run-output.txt').read_bytes().decode('latin1')
    return re.findall(r'CROWD_FREEZE t=(\d+): the screen holds frame (\d+)', t)


out, title, items = sys.argv[1], sys.argv[2], sys.argv[3:]
tiles = []
for it in items:
    label, spec = it.split('=', 1)
    parts = spec.split(':')
    scen, fb, idx = parts[0], (parts[1] if len(parts) > 1 and parts[1] else 'fb0'), int(parts[2]) if len(parts) > 2 else 1
    p = held(scen, fb, idx)
    if not p:
        print('no held frame in', scen); continue
    im = Image.open(p).convert('RGB')
    tiles.append((label, im, hashlib.md5(p.read_bytes()).hexdigest()[:8], frozen(scen), p))
    print(label, p, tiles[-1][2], tiles[-1][3])
if not tiles:
    sys.exit('nothing to tile')
w, h = tiles[0][1].size
cols = min(3, len(tiles)); rows = (len(tiles) + cols - 1) // cols
pad = 34
sheet = Image.new('RGB', (cols * w, pad + rows * (h + pad)), (20, 20, 20))
d = ImageDraw.Draw(sheet)
d.text((8, 8), title, fill=(255, 255, 255))
for k, (label, im, md5, fz, p) in enumerate(tiles):
    x, y = (k % cols) * w, pad + (k // cols) * (h + pad)
    d.text((x + 6, y + 8), f'{label}   [{md5}]', fill=(255, 230, 120))
    sheet.paste(im, (x, y + pad))
sheet.save(out)
print('sheet', out, sheet.size)
# <out>-diff.png: |tile - first tile| x 4 per arm, with the share of changed pixels, so small changes are visible.
from PIL import ImageChops
ref = tiles[0][1]
dsheet = Image.new('RGB', sheet.size, (20, 20, 20))
dd = ImageDraw.Draw(dsheet)
dd.text((8, 8), title + '  |  difference vs ' + tiles[0][0] + ' (x4)', fill=(255, 255, 255))
for k, (label, im, md5, fz, p) in enumerate(tiles):
    x, y = (k % cols) * w, pad + (k // cols) * (h + pad)
    diff = ImageChops.difference(im, ref)
    changed = sum(1 for v in diff.convert('L').getdata() if v > 8) / float(w * h)
    dd.text((x + 6, y + 8), f'{label}   changed {changed * 100:.1f}% of pixels', fill=(255, 230, 120))
    dsheet.paste(diff.point(lambda v: min(255, v * 4)), (x, y + pad))
    print(label, 'changed %.2f%%' % (changed * 100))
dout = out[:-4] + '-diff.png'
dsheet.save(dout)
print('sheet', dout)
