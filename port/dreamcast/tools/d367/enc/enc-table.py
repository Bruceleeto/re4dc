"""Lane enc: cost + census table over hwproject runs (2026-09-30).

Usage: python3 enc-table.py [--root EVROOT] [--tsv OUT.tsv] [--frames OUT.tsv] view=hwmodel-dir[:A:B] ...
  hwmodel-dir: a hwproject output dir (proj/, and enc-census.txt from enc-hw.sh); A:B the counted window
  (default 900:1380) for averaging the census lines.
Prints a markdown table: frame / work hw ms (work = frame minus the modelled vsync spin in `main`), the areas, the
character rows (skin / skeleton / motion / model trans / cloth / enemy logic, Leon + Ganados), and the census means.
Also a pooled fit of traced-frame hw ms against the Ganados reaching the draw (per-view intercepts), which is the
per-Ganado marginal cost.
"""
import argparse
import csv
import os
import re
import statistics as st

AREAS = ['game-render-side', 'actors', 'game-logic', 'scenery', 'ui', 'copies', 'kos-idle', 'ta-submit']
# Character rows outside the actors area (Leon + Ganados share them): skinning kernels, weight palettes, skeleton /
# parts world calc, motion interpolation, model trans / light setup, IK, cloth, enemy logic.
CHAR_RX = re.compile(r'avk_|wpal|sk1|[Ss]kin|hermite|Motion|motion|pwc_|pmc_|PSMTXConcat|PSMTXInverse|'
                     r'InverseKinematics|RotMatrix|getPartsPtr|commonModelTrans|ModelRender|LightSetModel|setModel2|'
                     r'materialSetup|[Cc]loth|^cEm|em10|Em10|EmMgr|emMove|updateOldPos|coarse_skin|coarse_ganado')
CENSUS_RX = re.compile(r'ENC f=(\d+) ga=(\d+) oa=(\d+) gr=(\d+) go=(\d+) gs=(\d+) gx=(\d+) gb=(\d+)/(\d+)/(\d+)/(\d+) '
                       r'or=(\d+) ct=(\d+)/(\d+)/(\d+)/(\d+)(?: sr=(\d+)/(\d+)/(\d+))?')
# snp / sst / sot: Ganados the source path drew because the cast had no plan / a sticky source choice / other
KEYS = ['ga', 'oa', 'gr', 'go', 'gs', 'gx', 'b5', 'b12', 'b25', 'bfar', 'or', 'c0', 'c1', 'c2', 'c3', 'snp', 'sst', 'sot']


def census(path):
    out = {}
    if not os.path.exists(path):
        return out
    for line in open(path, encoding='utf-8', errors='replace'):
        m = CENSUS_RX.search(line)
        if m:
            v = [int(x) if x is not None else 0 for x in m.groups()]
            out[v[0]] = dict(zip(KEYS, v[1:]))
    return out


def view(d, a, b):
    proj = os.path.join(d, 'proj')
    txt = open(os.path.join(proj, 'projection.txt')).read()
    hw = float(re.search(r'hardware projection\s+([\d.]+)', txt).group(1))
    lo, hi = (float(x) for x in re.search(r'hardware projection[^\[]*\[low ([\d.]+) \.\. high ([\d.]+)\]', txt).groups())
    fly = float(re.search(r'Flycast \(dynarec charge model\)\s+([\d.]+)', txt).group(1))
    areas = {}
    for r in csv.DictReader(open(os.path.join(proj, 'rep', 'areas.tsv')), delimiter='\t'):
        areas[r['area']] = float(r['hw_ms'])
    spin = 0.0
    char = 0.0
    char_rows = []
    for r in csv.DictReader(open(os.path.join(proj, 'rep', 'functions.tsv')), delimiter='\t'):
        ms = float(r['hw_ms'])
        if r['func'] == 'main':
            spin += ms
        elif r['area'] != 'actors' and CHAR_RX.search(r['func']):
            char += ms
            char_rows.append((ms, r['func'][:60]))
    frames = []
    for r in csv.DictReader(open(os.path.join(proj, 'nominal.frames.tsv')), delimiter='\t'):
        f = int(re.search(r'trace-(\d+)\.bin', r['trace']).group(1))
        frames.append((f, float(r['ms'])))
    cen = census(os.path.join(d, 'enc-census.txt'))
    win = [cen[f] for f in range(a, b + 1) if f in cen]
    mean = {k: (st.mean(x[k] for x in win) if win else float('nan')) for k in KEYS}
    mx = {k: (max(x[k] for x in win) if win else 0) for k in KEYS}
    return dict(hw=hw, lo=lo, hi=hi, fly=fly, spin=spin, work=hw - spin, areas=areas, char=char,
                char_rows=sorted(char_rows, reverse=True), frames=frames, census=cen, mean=mean, max=mx,
                ncensus=len(win))


def fit(views):
    """ms = a_view + b * x over traced frames with a census line; returns b per regressor."""
    res = {}
    for key in ('gr', 'go', 'ga'):
        num = den = 0.0
        n = 0
        for name, v in views.items():
            pts = [(v['census'][f][key], ms) for f, ms in v['frames'] if f in v['census']]
            if len(pts) < 3:
                continue
            mx = st.mean(p[0] for p in pts)
            my = st.mean(p[1] for p in pts)
            num += sum((x - mx) * (y - my) for x, y in pts)
            den += sum((x - mx) ** 2 for x, _ in pts)
            n += len(pts)
        res[key] = (num / den if den else float('nan'), n)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default='/mnt/c/Flycast-Evidence/re4-dreamcast')
    ap.add_argument('--tsv')
    ap.add_argument('--frames')
    ap.add_argument('views', nargs='+')
    o = ap.parse_args()
    views = {}
    for spec in o.views:
        name, rest = spec.split('=', 1)
        parts = rest.split(':')
        d = parts[0] if os.path.isabs(parts[0]) else os.path.join(o.root, parts[0])
        a, b = (int(parts[1]), int(parts[2])) if len(parts) == 3 else (900, 1380)
        views[name] = view(d, a, b)
    hdr = ('| view | frame hw ms [lo..hi] | work | vs 33.3 | ' + ' | '.join(AREAS[:6]) +
           ' | char rows | Ganados alive / reach draw (max) / cast-owned / source (no plan) | reaching by dist '
           '<5/5-12/12-25/>25 m | other enemies alive / drawn | crowd tiers full/near/mid/far |')
    print(hdr)
    print('|' + '---|' * (hdr.count('|') - 1))
    rows = []
    for name, v in views.items():
        m = v['mean']
        ar = [v['areas'].get(k, 0.0) for k in AREAS[:6]]
        line = ('| %s | %.1f [%.1f..%.1f] | %.1f | %+.1f | %s | %.1f | %.1f / %.1f (%d) / %.1f / %.1f (%.1f) | '
                '%.1f/%.1f/%.1f/%.1f | %.1f / %.1f | %.1f/%.1f/%.1f/%.1f |' % (
                    name, v['hw'], v['lo'], v['hi'], v['work'], v['work'] - 33.3, ' | '.join('%.1f' % x for x in ar),
                    v['char'], m['ga'], m['gr'], v['max']['gr'], m['go'], m['gs'], m['snp'], m['b5'], m['b12'],
                    m['b25'], m['bfar'], m['oa'], m['or'], m['c0'], m['c1'], m['c2'], m['c3']))
        print(line)
        rows.append([name, v['hw'], v['lo'], v['hi'], v['work'], v['fly']] + ar + [v['char']] +
                    [m[k] for k in KEYS] + [v['ncensus']])
    print()
    for key, (b, n) in fit(views).items():
        print('pooled within-view fit: traced-frame hw ms per %s = %.2f ms (%d frames)' % (key, b, n))
    if o.tsv:
        with open(o.tsv, 'w') as f:
            f.write('\t'.join(['view', 'hw_ms', 'lo', 'hi', 'work_ms', 'fly_ms'] + AREAS[:6] + ['char_rows'] +
                              ['mean_' + k for k in KEYS] + ['census_frames']) + '\n')
            for r in rows:
                f.write('\t'.join(r[0:1] + ['%.2f' % x for x in r[1:]]) + '\n')
    if o.frames:
        with open(o.frames, 'w') as f:
            f.write('\t'.join(['view', 'frame', 'hw_ms'] + KEYS) + '\n')
            for name, v in views.items():
                for fr, ms in v['frames']:
                    c = v['census'].get(fr)
                    f.write('\t'.join([name, str(fr), '%.3f' % ms] + [str(c[k]) if c else '' for k in KEYS]) + '\n')


if __name__ == '__main__':
    main()
