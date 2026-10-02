"""Lane enc: summarize a census.txt (ENC lines) and pick crowd windows (2026-09-30).

Usage: python enc-windows.py census.txt [--bin 120] [--win 480] [--start 900]
Prints per-bin means (Ganados alive / reaching the draw / within 25 m / cast-owned / source; other enemies drawn)
and the best --win window starting at or after --start by mean Ganados reaching the draw within 25 m (then all
reaching), which is the crowd window to project with hwproject.
"""
import argparse
import re

RX = re.compile(r'ENC f=(\d+) ga=(\d+) oa=(\d+) gr=(\d+) go=(\d+) gs=(\d+) gx=(\d+) gb=(\d+)/(\d+)/(\d+)/(\d+) or=(\d+)')
ap = argparse.ArgumentParser()
ap.add_argument('census')
ap.add_argument('--bin', type=int, default=120)
ap.add_argument('--win', type=int, default=480)
ap.add_argument('--start', type=int, default=900)
a = ap.parse_args()
rows = {}
for line in open(a.census, encoding='utf-8', errors='replace'):
    m = RX.search(line)
    if m:
        v = [int(x) for x in m.groups()]
        hp = re.search(r' hp=(-?\d+)', line)
        rows[v[0]] = dict(ga=v[1], oa=v[2], gr=v[3], go=v[4], gs=v[5], gx=v[6], near=v[7] + v[8] + v[9], n5=v[7],
                          n12=v[8], orr=v[11], hp=int(hp.group(1)) if hp else 1)
if not rows:
    raise SystemExit('no ENC lines')
last = max(rows)
print('frames 1..%d' % last)
print(' bin        ga    gr  gr<25m  <12m   go    gs   or  hp(min)')
for b0 in range(1, last + 1, a.bin):
    fs = [rows[f] for f in range(b0, b0 + a.bin) if f in rows]
    if not fs:
        continue
    mean = lambda k: sum(x[k] for x in fs) / len(fs)
    print('%5d-%-5d %4.1f %5.1f %6.1f %5.1f %5.1f %5.1f %4.1f %5d' % (
        b0, b0 + a.bin - 1, mean('ga'), mean('gr'), mean('near'), mean('n5') + mean('n12'), mean('go'), mean('gs'),
        mean('orr'), min(x['hp'] for x in fs)))
best = None
for s in range(a.start, last - a.win + 2, 20):
    fs = [rows[f] for f in range(s, s + a.win) if f in rows]
    if len(fs) < a.win * 0.95 or min(x['hp'] for x in fs) <= 0:   # Leon alive for the whole window
        continue
    key = (sum(x['near'] for x in fs) / len(fs), sum(x['gr'] for x in fs) / len(fs))
    if best is None or key > best[0]:
        best = (key, s)
if best:
    (near, gr), s = best
    print('best window %d:%d  mean Ganados reaching the draw %.1f, within 25 m %.1f' % (s, s + a.win, gr, near))
