"""sheet.py [room ...]: WORLDTEST-<room>.png, columns A | B | C, rows = the room's two gameplay cameras (Flycast trace arm
wtrT, frozen tick, View Full, fog on). Labels: arm, kept vertex share, MODELLED world ms vs A (room-budget model)."""
import os, re, sys, json
from PIL import Image, ImageDraw, ImageFont, ImageChops, ImageStat
E = r'C:\Flycast-Evidence\re4-dreamcast\worldtest-20261016'
OUT = r'C:\Game Dev\Emulators\worldtest-20261016'
PRICE = json.load(open(os.path.join(OUT, 'price-1.json')))
CTAG = {'r101': 'C3'}  # other rooms: Cm25
RUNC = {'r101': 'C3'}  # run suffix of arm C
CAMID = {'r102': ('c1', 'c2b'), 'r106': ('c1', 'c2', 'c3')}
KEPT = {'r101': {'A': 1.0, 'B': 0.619, 'C': 0.634}, 'r102': {'A': 1.0, 'B': 0.367, 'C': 0.933},
        'r106': {'A': 1.0, 'B': 0.599, 'C': 0.866}, 'r108': {'A': 1.0, 'B': 0.529, 'C': 0.844},
        'r10a': {'A': 1.0, 'B': 0.632, 'C': 0.860}}
ARMS = {'A': 'A current world', 'B': 'B world16 as built', 'C': 'C landmarks + gentler'}
R101 = {'A': 'A pre-world32 (bake13)', 'B': 'B world32 as landed', 'C': 'C world32 + stake/pyre kept'}
CAMS = {'r101': ['cross (-7914,0,2000) crowd alerted', 'road (entry, walk fwd)'],
        'r102': ['door from r101 (-19691,0,-19088) yaw .785', 'merchant spot em18 (-12210,-8720,38420) yaw 2.75'],
        'r106': ['door from r103 (11141,-893,-120) yaw 1.18', 'worst view em2a (113920,-7860,-13210) yaw 2.75', '2nd worst em2a (113010,-8260,-33390) yaw 1.18 (added: worst view faces a hillside)'],
        'r108': ['door from r102 (-43905,-38,-14737) yaw 1.96', 'worst view em16 (-1390,10000,-19250) yaw 1.96'],
        'r10a': ['door from r109 (-58327,7346,69786) yaw 1.18', 'worst view em12 (41850,-10000,89330) yaw 1.18']}


def kind(im):
    r, g, b = ImageStat.Stat(im.resize((64, 48))).mean
    if b > 60 and r < 40 and g < 40:
        return 'hang'
    return 'black' if r + g + b < 30 else 'scene'


def pick(run):
    d = os.path.join(E, run, 'capture', 'shots')
    shots = sorted(os.listdir(d))
    ims = [(t, Image.open(os.path.join(d, t, 'frames', 'fb0.png')).convert('RGB')) for t in shots]
    best = None
    for (t0, a), (t1, b) in zip(ims, ims[1:]):
        if kind(a) == 'scene' and kind(b) == 'scene':
            diff = ImageChops.difference(a, b).convert('L')
            if sum(1 for p in diff.get_flattened_data() if p > 8) < 200:
                best = (t0, a); break
    log = open(os.path.join(E, run, 'capture', 'run-output.txt'), encoding='latin-1').read()
    m = re.search(r'warp: frozen at tick (\d+)', log)
    wv = re.findall(r'WORLDVERT room=(\w+) want=\d+ loaded=(\d+)', log)
    return best, (m.group(1) if m else None), wv


def main(rooms):
    F = ImageFont.truetype('arial.ttf', 15); FB = ImageFont.truetype('arialbd.ttf', 17); FT = ImageFont.truetype('arialbd.ttf', 22)
    CW, CH = 560, 420
    for room in rooms:
        sheet = Image.new('RGB', (3 * CW + 40, 96 + len(CAMID.get(room, 'xx')) * (CH + 70)), (24, 24, 24))
        d = ImageDraw.Draw(sheet)
        d.text((10, 8), 'WORLDTEST %s: in game (Flycast JIT, trace arm wtrT = t15/int 6153f987, WORLD_VERT=1 LEVEL=5, View Full, fog on), '
                        'same frozen tick per row; only the world data differs' % room, font=F, fill=(230, 230, 230))
        hdr = R101 if room == 'r101' else ARMS
        for i, arm in enumerate('ABC'):
            tag = arm if arm != 'C' else CTAG.get(room, 'Cm25')
            p = PRICE.get('%s:%s' % (room, tag)); pa = PRICE['%s:A' % room]
            ms = '' if arm == 'A' else ' | MODELLED world %+.1f ms p90 (%+.1f worst view)' % (p['ms_p90'] - pa['ms_p90'], p['ms_max'] - pa['ms_max'])
            if arm == 'A':
                ms = ' | MODELLED world %.1f ms p90, %.1f worst' % (pa['ms_p90'], pa['ms_max'])
            d.text((10 + i * (CW + 10), 34), hdr[arm], font=FB, fill=(255, 220, 120))
            d.text((10 + i * (CW + 10), 56), 'kept %.2f%s' % (KEPT[room][arm], ms), font=F, fill=(200, 200, 200))
        y = 84
        for ci, cam in enumerate(CAMID.get(room, ('c1', 'c2'))):
            d.text((10, y), 'camera %d: %s' % (ci + 1, CAMS[room][ci]), font=FB, fill=(150, 210, 255)); y += 26
            ims = []
            for i, arm in enumerate('ABC'):
                run = '%s-%s-%s' % (room, cam, RUNC.get(room, 'C') if arm == 'C' else arm)
                try:
                    best, tick, wv = pick(run)
                except FileNotFoundError:
                    best, tick, wv = None, None, []
                im = best[1].resize((CW, CH)) if best else Image.new('RGB', (CW, CH), (80, 0, 0))
                ims.append(im); sheet.paste(im, (10 + i * (CW + 10), y))
                lv = ','.join('%s:%s' % x for x in wv if x[0] == room[1:]) or '-'
                d.text((14 + i * (CW + 10), y + CH + 4), '%s tick %s shot %s WORLDVERT %s' % (run, tick, best[0] if best else None, lv),
                       font=F, fill=(255, 255, 0))
            for i in (1, 2):
                diff = ImageChops.difference(ims[0], ims[i]).convert('L')
                print(room, cam, 'ABC'[i], 'pixels differing >16 vs A: %.1f%%' % (100.0 * sum(1 for q in diff.get_flattened_data() if q > 16) / (CW * CH)))
            y += CH + 44
        p = os.path.join(OUT, 'WORLDTEST-%s.png' % room); sheet.save(p); print(p)


if __name__ == '__main__':
    main(sys.argv[1:] or ['r101', 'r102', 'r106', 'r108', 'r10a'])
