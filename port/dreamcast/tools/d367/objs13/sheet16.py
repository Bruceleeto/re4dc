"""sheet16.py: test 13 objects before / after stills, 4 heaviest rooms (r117, r11b, r10b, r119). Per room: the control
mcheck run g16-<r>-cm (test 12 dar: p2b objects incl. PS2 breakables) vs the test run g16-<r>-m (objs13 dar), the same
shot slots (mcheck runs, same warp, deterministic logic). Output objs-20261014/sheets/t13-objs-<r>.png + t13-objs.png."""
import os
from PIL import Image, ImageDraw
E = r'C:\Flycast-Evidence\re4-dreamcast\objs-20261014'
rows = []
for r in ('117', '11b', '10b', '119'):
    pair = []
    for run, label in (('g16-%s-cm' % r, 'r%s test 12 (before)' % r), ('g16-%s-m' % r, 'r%s objs13 (after)' % r)):
        d = os.path.join(E, run, 'capture', 'shots')
        shots = sorted(s for s in os.listdir(d) if os.path.exists(os.path.join(d, s, 'frames', 'fb0.png')))
        pair.append((label, shots, d))
    common = sorted(set(pair[0][1]) & set(pair[1][1]))
    s = common[-1] if r != '119' else common[min(1, len(common) - 1)]
    rows.append([(lab + ' ' + s, Image.open(os.path.join(d, s, 'frames', 'fb0.png')).convert('RGB')) for lab, _, d in pair])
w, h = rows[0][0][1].size
out = Image.new('RGB', (w * 2, (h + 16) * len(rows)), 'black')
dr = ImageDraw.Draw(out)
for i, row in enumerate(rows):
    for c, (lab, im) in enumerate(row):
        out.paste(im.resize((w, h)), (c * w, i * (h + 16) + 16))
        dr.text((c * w + 4, i * (h + 16) + 2), lab, fill='yellow')
os.makedirs(os.path.join(E, 'sheets'), exist_ok=True)
p = os.path.join(E, 'sheets', 't13-objs.png')
out.save(p)
print(p, out.size)
