"""looksheet.py: objs13 look sheet r102..r119. Per room: test 12 (before: p2b objects, PS2 breakables, GC pictures)
vs objs13 (after), Leon warped facing a converted object (work/warps/look<r>.txt), frozen at ui 1200 (warp `freeze`),
so both columns are the same settled frame. Shot slot t0030 (after the freeze; t0045/46 is the same frame).
Output objs-20261014/sheets/t13-look.png (+ t13-look-<r>.png full size per room)."""
import os
from PIL import Image, ImageDraw
E = r'C:\Flycast-Evidence\re4-dreamcast\objs-20261014'
LAB = {'102': 'et1300 door', '103': 'et0500 rack', '104': 'et1700', '105': 'et2200 door', '106': 'BIN 0x34 closet',
       '107': 'et1600', '108': 'et1a00 blue medal', '109': 'et1000 torch', '10a': 'BIN 0x20 rock (high)',
       '10b': 'BIN 0x1e float island', '117': 'et1600', '118': 'et1a00 blue medal', '11a': 'et1000 torch',
       '11b': 'et0300', '119': 'BIN 0x22 tree'}
rooms = list(LAB)
W, H = 480, 360
out = Image.new('RGB', (W * 4, (H + 18) * ((len(rooms) + 1) // 2)), 'black')
dr = ImageDraw.Draw(out)
os.makedirs(os.path.join(E, 'sheets'), exist_ok=True)
for i, r in enumerate(rooms):
    pair = []
    for arm, lab in (('c', 'test 12'), ('t', 'objs13')):
        if arm == 't':  # the latest objs13 arm: t4 (v5: PS2 size declared or bilinear), t3 (nearest resample), t2 (r104 image remap), t
            arm = next(a for a in ('t4', 't3', 't2', 't') if os.path.isdir(os.path.join(E, 'g16L-%s-%s' % (r, a))))
            lab = 'objs13 (%s)' % arm
        d = os.path.join(E, 'g16L-%s-%s' % (r, arm), 'capture', 'shots')
        if not os.path.isdir(d):
            pair.append(('r%s %s: no run' % (r, lab), Image.new('RGB', (640, 480), 'gray')))
            continue
        shots = sorted(s for s in os.listdir(d) if os.path.exists(os.path.join(d, s, 'frames', 'fb0.png')))
        s = [x for x in shots if x >= 't0030'][0] if any(x >= 't0030' for x in shots) else shots[-1]
        pair.append(('r%s %s %s (%s)' % (r, lab, s, LAB[r]), Image.open(os.path.join(d, s, 'frames', 'fb0.png')).convert('RGB')))
    big = Image.new('RGB', (1280, 498), 'black')
    bd = ImageDraw.Draw(big)
    for c, (lab, im) in enumerate(pair):
        big.paste(im.resize((640, 480)), (c * 640, 18)); bd.text((c * 640 + 4, 3), lab, fill='yellow')
    big.save(os.path.join(E, 'sheets', 't13-look-%s.png' % r))
    row, col = i // 2, (i % 2) * 2
    for c, (lab, im) in enumerate(pair):
        x, y = (col + c) * W, row * (H + 18)
        out.paste(im.resize((W, H)), (x, y + 18)); dr.text((x + 4, y + 3), lab, fill='yellow')
p = os.path.join(E, 'sheets', 't13-look.png')
out.save(p)
print(p, out.size)
