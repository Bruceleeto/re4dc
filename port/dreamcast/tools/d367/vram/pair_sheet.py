#!/usr/bin/env python3
"""pair_sheet.py <out.png> <shot> <label A> <evidence A> <label B> <evidence B> [<room label> <evA> <evB>]...
(lane resident16, 2026-10-16): still pairs side by side, one row per room: the framebuffer shot <shot> (e.g.
t0060/frames/fb0.png under capture/shots) of run A (before) and run B (after), labelled. For the user's look decision
on a data set that changes pictures (vq16c)."""
import sys
from pathlib import Path
from PIL import Image, ImageDraw

out, shot, la, lb = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
rows = [sys.argv[i:i + 3] for i in range(5, len(sys.argv), 3)]
ims = []
for name, a, b in rows:
    pa, pb = Path(a) / 'capture/shots' / shot, Path(b) / 'capture/shots' / shot
    if pa.exists() and pb.exists():
        ims.append((name, Image.open(pa).convert('RGB'), Image.open(pb).convert('RGB')))
w, h = ims[0][1].size
sheet = Image.new('RGB', (2 * w + 30, len(ims) * (h + 24)), (20, 20, 20))
d = ImageDraw.Draw(sheet)
for i, (name, a, b) in enumerate(ims):
    y = i * (h + 24)
    d.text((4, y + 4), '%s  %s' % (name, la), fill=(255, 255, 255))
    d.text((w + 34, y + 4), '%s  %s' % (name, lb), fill=(255, 255, 255))
    sheet.paste(a, (0, y + 20)); sheet.paste(b, (w + 30, y + 20))
sheet.save(out)
print(out, sheet.size, len(ims), 'rows')
