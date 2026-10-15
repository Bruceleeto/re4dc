#!/usr/bin/env python3
# rank.py NM_TXT PROJ_DIR [N]: per-function store misses x 70 cyc x 0.79 overlap, ms per frame (console-fit first order)
import sys, bisect, os
nm, proj = sys.argv[1], sys.argv[2]; N = int(sys.argv[3]) if len(sys.argv) > 3 else 15
syms = []
for l in open(nm):
    p = l.split()
    if len(p) >= 3 and p[1] in 'tTwW':
        syms.append((int(p[0], 16), ' '.join(p[2:])))
syms.sort(); addrs = [a for a, _ in syms]
sm = dict(l.split()[:2] for l in open(os.path.join(proj, 'nominal.sum.txt')) if len(l.split()) >= 2)
fr = float(sm['frames'])
agg = {}
with open(os.path.join(proj, 'nominal.pcs.tsv')) as f:
    h = f.readline().rstrip('\n').split('\t'); wi = h.index('dwmiss'); wr = h.index('writes'); ri = h.index('drmiss')
    for l in f:
        c = l.split('\t'); pc = int(c[0], 16)
        i = bisect.bisect_right(addrs, pc) - 1
        n = syms[i][1] if i >= 0 else '?'
        a = agg.setdefault(n, [0, 0, 0]); a[0] += float(c[wi]); a[1] += float(c[wr]); a[2] += float(c[ri])
tot = sum(v[0] for v in agg.values())
print('total store misses/frame %.0f = %.2f ms' % (tot / fr, 0.79 * 70 * tot / 200000 / fr))
for n, v in sorted(agg.items(), key=lambda x: -x[1][0])[:N]:
    print('%-90s wmiss/f %7.0f writes/f %8.0f rmiss/f %7.0f  ms %.3f' % (n[:90], v[0] / fr, v[1] / fr, v[2] / fr, 0.79 * 70 * v[0] / 200000 / fr))
