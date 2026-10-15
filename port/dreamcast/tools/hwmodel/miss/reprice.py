#!/usr/bin/env python3
"""reprice.py LABEL CTL_DIR ARM_DIR [LABEL CTL ARM ...]
Re-prices a hwproject A/B pair under the console-fitted miss penalties WITHOUT the traces, from proj/nominal.pcs.tsv
and proj/nominal.sum.txt: extra cycles = K_OVL * (DMISS_LAT * D fills + IMISS_LAT * I misses + WMISS_LAT * write misses).
Default = the refit (hwsim --console-fit: D 6, I 5, W 0); --w70 = the first fit (D 0, I 4, W 70), contradicted by
console Bench A/B, for comparison only.
K_OVL = 0.79 is the overlap factor measured on the four hwcal scenes (full re-simulation / first-order estimate:
cross 0.78, house 0.78, Del Lago 0.83, farm 0.78). Prints ms/frame nominal and console-fit for both arms and the deltas."""
import sys, os
DMISS_LAT, IMISS_LAT, WMISS_LAT, K_OVL = 6.0, 5.0, 0.0, 0.79
if '--w70' in sys.argv:
    sys.argv.remove('--w70'); DMISS_LAT, IMISS_LAT, WMISS_LAT = 0.0, 4.0, 70.0
HZ = 200000.0  # cycles per ms
def load(d):
    p = os.path.join(d, 'proj')
    sm = dict(l.split()[:2] for l in open(os.path.join(p, 'nominal.sum.txt')) if len(l.split()) >= 2)
    fr = float(sm['frames']); msf = float(sm['ms_per_frame'])
    I = W = 0.0
    with open(os.path.join(p, 'nominal.pcs.tsv')) as f:
        h = f.readline().rstrip('\n').split('\t'); ii = h.index('imiss_n'); wi = h.index('dwmiss')
        for l in f:
            c = l.split('\t'); I += float(c[ii]); W += float(c[wi])
    extra = K_OVL * (DMISS_LAT * float(sm['dfills_per_frame']) * fr + IMISS_LAT * I + WMISS_LAT * W) / HZ / fr
    return msf, msf + extra, I / fr, W / fr
a = sys.argv[1:]
print('lever | ctl nominal | arm nominal | delta nominal | ctl fit | arm fit | delta fit | dI/frame | dW/frame')
for i in range(0, len(a), 3):
    lab, c, r = a[i:i + 3]
    try:
        cn, cf, ci, cw = load(c); an, af, ai, aw = load(r)
    except Exception as e:
        print('%s | missing (%s)' % (lab, e)); continue
    print('%s | %.2f | %.2f | %+.2f | %.2f | %.2f | %+.2f | %+.0f | %+.0f' % (lab, cn, an, an - cn, cf, af, af - cf, ai - ci, aw - cw))
