#!/usr/bin/env python3
"""refit.py: store-miss term refit with the console Bench A / Bench B constraints (lane storemiss 2026-10-15).

Traces of the hwcal scenes are gone (24 h rule), so this is a LINEAR refit on the kept re-simulated variants:
per scene/part cycles(d, i, w) = nominal + d*Sd + i*Si + w*Sw (+ cross terms ignored), with Sd/Si/Sw solved from the
grid variants (d0i4w70, d0i8w70, d0i3w80, d10i6, d15i6, d15i6w10). Error = hwcal weighted RMS log(console/model)
(fit.py's) + chi2 of the two console A/B pairs (memlay hwmodel-ml-ctl/-A/-B, first order with overlap 0.79):
  Bench A (ACTOR_MOVCA): console delta per tick cross -0.15, house -0.05 (control pair 47.1/47.6, 37.4/37.5)
  Bench B (MEM_MOVCA):   console cross +0.05, house +0.45
  sigma 0.3 ms (detection floor, HWMODEL-CALIBRATION section 8).
"""
import csv, math, os, sys
sys.path.insert(0, '/mnt/c/Flycast-Evidence/re4-dreamcast/hwmiss-20261015/tools')
import fit  # noqa: E402  (pic(), CON, P)
P, CON = fit.P, fit.CON
ms = lambda x: x / 200000.0
V = {}
for v in ['nominal', 'd0i4w70', 'd0i8w70', 'd0i3w80', 'd10i6', 'd15i6', 'd15i6w10', 'd5i8w30', 'd8i6w20']:
    V[v] = {sc: fit.pic(sc, v) for sc in CON}
def cyc(v, sc, p): return V[v][sc][p]['cyc']
S = {}
for sc in CON:
    for p in P:
        n = cyc('nominal', sc, p)
        Si = (cyc('d0i8w70', sc, p) - cyc('d0i4w70', sc, p)) / 4.0
        Sw = (cyc('d0i4w70', sc, p) - n - 4 * Si) / 70.0
        Sd = (cyc('d15i6', sc, p) - cyc('d10i6', sc, p)) / 5.0
        S[(sc, p)] = (n, Sd, Si, Sw)
def model(sc, p, d, i, w):
    n, Sd, Si, Sw = S[(sc, p)]
    return n + d * Sd + i * Si + w * Sw
# linearity check against variants not used to solve
chk = []
for v, (d, i, w) in [('d0i3w80', (0, 3, 80)), ('d5i8w30', (5, 8, 30)), ('d8i6w20', (8, 6, 20)), ('d15i6w10', (15, 6, 10))]:
    e = max(abs(ms(model(sc, p, d, i, w)) - ms(cyc(v, sc, p))) for sc in CON for p in P)
    chk.append('%s max |lin - sim| %.2f ms' % (v, e))
E = '/mnt/c/Flycast-Evidence/re4-dreamcast/memlay-20261015'
def counts(arm):
    p = '%s/hwmodel-ml-%s/proj' % (E, arm)
    sm = dict(l.split()[:2] for l in open(p + '/nominal.sum.txt') if len(l.split()) >= 2)
    fr = float(sm['frames']); W = I = 0.0
    with open(p + '/nominal.pcs.tsv') as f:
        h = f.readline().rstrip('\n').split('\t'); wi = h.index('dwmiss'); ii = h.index('imiss_n')
        for l in f:
            c = l.split('\t'); W += float(c[wi]); I += float(c[ii])
    return float(sm['dfills_per_frame']), I / fr, W / fr, float(sm['ms_per_frame'])
C0 = counts('ctl'); CA = counts('A'); CB = counts('B')
AB = [('A', CA, -0.10), ('B', CB, +0.25)]   # console delta per tick (scene mean of cross / house)
SIG = 0.3
def ab_delta(arm, d, i, w):
    df, di, dw = arm[0] - C0[0], arm[1] - C0[1], arm[2] - C0[2]
    return (arm[3] - C0[3]) + 0.79 * (d * df + i * di + w * dw) / 200000.0
def err(d, i, w):
    e = s = 0.0
    for sc in CON:
        for k, p in enumerate(P):
            c = CON[sc][0][k]; m = ms(model(sc, p, d, i, w))
            if m <= 0: return 9e9
            e += c * math.log(c / m) ** 2; s += c
    rms = math.sqrt(e / s)
    chi = sum(((ab_delta(a, d, i, w) - con) / SIG) ** 2 for _, a, con in AB)
    return rms, chi
best = []
for d in range(0, 31):
    for i in range(0, 13):
        for w in range(0, 101, 5):
            rms, chi = err(d, i, w)
            best.append((rms, chi, d, i, w))
print('\n'.join(chk))
print('counts/frame (dfill, ifill, wmiss, nominal ms): ctl %s A %s B %s' % tuple(
    '(%.0f %.0f %.0f %.2f)' % c for c in (C0, CA, CB)))
print('\nhwcal-only best (rms):')
for r in sorted(best)[:5]: print('  d%d i%d w%d rms %.4f chiAB %.1f  A %+.2f B %+.2f' % (r[2], r[3], r[4], r[0], r[1], ab_delta(CA, *r[2:]), ab_delta(CB, *r[2:])))
print('\nconstrained (chiAB <= 2, i.e. both A/B within ~1 sigma):')
ok = sorted([r for r in best if r[1] <= 2.0])
for r in ok[:8]: print('  d%d i%d w%d rms %.4f chiAB %.2f  A %+.2f B %+.2f' % (r[2], r[3], r[4], r[0], r[1], ab_delta(CA, *r[2:]), ab_delta(CB, *r[2:])))
print('\njoint (rms^2/0.04^2 + chi):')
for r in sorted(best, key=lambda r: (r[0] / 0.04) ** 2 + r[1])[:5]:
    print('  d%d i%d w%d rms %.4f chiAB %.2f  A %+.2f B %+.2f' % (r[2], r[3], r[4], r[0], r[1], ab_delta(CA, *r[2:]), ab_delta(CB, *r[2:])))
if ok:
    d, i, w = ok[0][2:]
    print('\nREFIT d%d i%d w%d: per part console/model' % (d, i, w))
    for sc in CON:
        print('  %-8s ' % sc + ' '.join('%s %.2f' % (p, CON[sc][0][k] / ms(model(sc, p, d, i, w))) for k, p in enumerate(P)))

# re-price lever pairs at the refit (first order, overlap 0.79): python3 refit.py ctl_dir arm_dir label ...
def cnt(d):
    p = d + '/proj'
    sm = dict(l.split()[:2] for l in open(p + '/nominal.sum.txt') if len(l.split()) >= 2)
    fr = float(sm['frames']); W = I = 0.0
    with open(p + '/nominal.pcs.tsv') as f:
        h = f.readline().rstrip('\n').split('\t'); wi = h.index('dwmiss'); ii = h.index('imiss_n')
        for l in f:
            c = l.split('\t'); W += float(c[wi]); I += float(c[ii])
    return float(sm['dfills_per_frame']), I / fr, W / fr, float(sm['ms_per_frame'])
a = sys.argv[1:]
for k in range(0, len(a), 3):
    c, r, lab = cnt(a[k]), cnt(a[k + 1]), a[k + 2]
    for (d, i, w) in [(0, 4, 70), (6, 5, 0), (6, 5, 5)]:
        dd = (r[3] - c[3]) + 0.79 * (d * (r[0] - c[0]) + i * (r[1] - c[1]) + w * (r[2] - c[2])) / 200000.0
        print('%s d%d i%d w%d: nominal %+.2f -> %+.2f ms/frame (dW %+.0f dFill %+.0f)' % (lab, d, i, w, r[3] - c[3], dd, r[2] - c[2], r[0] - c[0]))
