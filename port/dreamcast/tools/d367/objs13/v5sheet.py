"""v5sheet.py: r10b / r11b / r119 before / after for the v5 picture-size fix (coordinator 10-15): test 12 (before),
objs13 v4 (nearest upscale, blocky), objs13 v5 (PS2 size declared, or bilinear where a mask pair needs the GC size).
Frozen frame (look warp, freeze 1200), shot slot t0030. Full frames + a 2x crop around the object."""
import os
from PIL import Image, ImageDraw
E = r'C:\Flycast-Evidence\re4-dreamcast\objs-20261014'
ROOMS = {'10b': 'BIN 0x1e float island', '11bi': 'BIN 0x1f float island', '11b': 'et0300 (v5 no change)', '119': 'BIN 0x22 tree'}
ARMS = (('c', 'test 12'), ('t3', 'objs13 v4 nearest'), ('t4', 'objs13 v5 declared/bilinear'))
def shot(r, arm):
    d = os.path.join(E, 'g16L-%s-%s' % (r, arm), 'capture', 'shots')
    shots = sorted(s for s in os.listdir(d) if os.path.exists(os.path.join(d, s, 'frames', 'fb0.png')))
    s = [x for x in shots if x >= 't0030'][0]
    return s, Image.open(os.path.join(d, s, 'frames', 'fb0.png')).convert('RGB')
rows = []
for r, lab in ROOMS.items():
    ims = [(a, l) + shot(r, a) for a, l in ARMS]
    row = Image.new('RGB', (640 * 3, 18 + 480), 'black'); dr = ImageDraw.Draw(row)
    for c, (a, l, s, im) in enumerate(ims):
        row.paste(im.resize((640, 480)), (c * 640, 18)); dr.text((c * 640 + 4, 3), 'r%s %s %s (%s)' % (r, l, s, lab), fill='yellow')
    row.save(os.path.join(E, 'sheets', 't13-v5-%s.png' % r)); rows.append(row)
out = Image.new('RGB', (640 * 3, sum(x.height for x in rows)), 'black')
y = 0
for x in rows:
    out.paste(x, (0, y)); y += x.height
out.save(os.path.join(E, 'sheets', 't13-v5.png')); print(os.path.join(E, 'sheets', 't13-v5.png'))
