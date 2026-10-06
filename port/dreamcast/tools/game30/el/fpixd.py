"""fpixd.py <run dir A> <run dir B> [crop.png]: lane fm copy of the int lane's pixd.py with run directories as
arguments. The frozen shot of a freeze-fixture run is the last shot of the longest run of consecutive identical fb0
shots that is not the crash screen. Reports the frozen tick and fb0 / fb1 pixel differences (count, bbox, max
channel delta, and how many differing pixels are 1 RGB565 step: |dR|,|dB| <= 9 and |dG| <= 5, the 5- / 6-bit expansion steps)."""
import sys, os, re, hashlib
from PIL import Image, ImageChops


def shots(d):
    s = os.path.join(d, 'shots')
    return [os.path.join(s, x) for x in sorted(os.listdir(s))]


def frozen_at(d):
    t = open(os.path.join(d, 'run-output.txt'), 'rb').read()
    if t[:2] in (b'\xff\xfe', b'\xfe\xff') or t[1:2] == b'\x00':
        t = t.decode('utf-16', errors='replace')
    else:
        t = t.decode('latin-1')
    m = re.search(r'warp: frozen at tick (\d+)', t)
    return m.group(1) if m else None


def h(p):
    return hashlib.sha256(Image.open(p).convert('RGB').tobytes()).hexdigest()


def crash(p):
    im = Image.open(p).convert('RGB')
    return sum(1 for x in range(0, 200, 2) for y in range(2, 20, 2)
               if im.getpixel((x, y))[0] > 200 and im.getpixel((x, y))[2] < 80) > 20


def frozen_shot(d):
    s = shots(d)
    hs = [h(os.path.join(x, 'frames', 'fb0.png')) for x in s]
    best, cur = None, 1
    for i in range(1, len(s) + 1):
        if i < len(s) and hs[i] == hs[i - 1]:
            cur += 1
            continue
        if cur >= 2 and not crash(os.path.join(s[i - 1], 'frames', 'fb0.png')):
            if best is None or cur >= best[0]:
                best = (cur, s[i - 1])
        cur = 1
    return best


def cmp(a, b, crop=None):
    ia, ib = Image.open(a).convert('RGB'), Image.open(b).convert('RGB')
    if ia.size != ib.size:
        return 'size %s vs %s' % (ia.size, ib.size)
    d = ImageChops.difference(ia, ib)
    bb = d.getbbox()
    if not bb:
        return 'IDENTICAL'
    px = list(d.get_flattened_data()) if hasattr(d, "get_flattened_data") else list(d.getdata())
    n = sum(1 for p in px if p != (0, 0, 0))
    step = sum(1 for p in px if p != (0, 0, 0) and p[0] <= 9 and p[1] <= 5 and p[2] <= 9)
    mx = max(max(p) for p in px)
    if crop:
        pad = 16
        box = (max(0, bb[0] - pad), max(0, bb[1] - pad), min(ia.size[0], bb[2] + pad), min(ia.size[1], bb[3] + pad))
        w, hh = box[2] - box[0], box[3] - box[1]
        im = Image.new('RGB', (w * 3, hh))
        im.paste(ia.crop(box), (0, 0))
        im.paste(ib.crop(box), (w, 0))
        im.paste(d.crop(box).point(lambda v: min(255, v * 30)), (2 * w, 0))
        im.resize((w * 6, hh * 2), Image.NEAREST).save(crop)
    return 'DIFF %d px (%d of them 1 RGB565 step) bbox %s max delta %d' % (n, step, bb, mx)


A, B = sys.argv[1], sys.argv[2]
crop = sys.argv[3] if len(sys.argv) > 3 else None
fa, fb = frozen_shot(A), frozen_shot(B)
print('A', os.path.basename(A), 'frozen tick', frozen_at(A), 'shot', fa and (fa[0], os.path.basename(fa[1])))
print('B', os.path.basename(B), 'frozen tick', frozen_at(B), 'shot', fb and (fb[0], os.path.basename(fb[1])))
for f in ('fb0.png', 'fb1.png'):
    c = None
    if crop:
        root, ext = os.path.splitext(crop)
        c = '%s-%s%s' % (root, f[:3], ext)
    print('A/B', f, cmp(os.path.join(fa[1], 'frames', f), os.path.join(fb[1], 'frames', f), c))
