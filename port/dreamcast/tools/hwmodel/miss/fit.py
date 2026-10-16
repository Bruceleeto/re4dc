#!/usr/bin/env python3
"""fit.py VARIANT [VARIANT...]: per scene/part console/model ratio, stall per miss, and the fit error
(ms-weighted RMS of log(console/model) over 4 scenes x 5 parts) for each re-simulated variant."""
import csv, re, sys, math
SIM = '/mnt/c/Flycast-Evidence/re4-dreamcast/hwmiss-20261015/sim'
SRC = '/mnt/d/Flycast-Evidence/re4-dreamcast/hwcal-20261015'
P = ['LOGIC', 'APREP', 'ADRAW', 'WORLD', 'OTHER']
CON = {'cross': ([33.1, 2.8, 28.4, 19.1, 15.8], 1.0), 'house': ([45.8, 1.8, 12.4, 7.2, 9.6], 1.0),
       'dellago': ([26.7, 1.8, 13.8, 2.2, 15.4], 0.8), 'farm': ([65.0, 4.9, 27.0, 17.8, 26.8], 1.0)}
ms = lambda x: float(x) / 200000.0
_keep = {}
def farm_keep():
    if 'f' not in _keep:
        log = [l for l in open('%s/hw-farm/trace/hwtrace.log' % SRC).read().splitlines() if l.startswith('frame ')]
        vals = [(int(l.split()[1]), 'traced' in l) for l in log]
        last = max([i for i in range(1, len(vals)) if vals[i][0] < vals[i - 1][0]] or [0])
        _keep['f'] = {v for v, t in vals[last:] if t}
    return _keep['f']
def pic(sc, V):
    rs = list(csv.DictReader(open('%s/hw-%s/proj/%s.phases.tsv' % (SIM, sc, V)), delimiter='\t'))
    if sc == 'farm':
        k = farm_keep(); rs = [r for r in rs if int(re.search(r'trace-(\d+)', r['trace']).group(1)) in k]
    K = CON[sc][1]
    dr = [r for r in rs if ms(r['cyc2']) + ms(r['cyc3']) > 1.0]
    sk = [r for r in rs if ms(r['cyc2']) + ms(r['cyc3']) <= 1.0]
    out = {}
    for p in range(5):
        f = lambda k, L: sum(float(r['%s%d' % (k, p)]) for r in L) / len(L) if L else 0.0
        out[P[p]] = {k: f(k, dr) + K * f(k, sk) for k in ('cyc', 'dmiss', 'imiss', 'dfill', 'ifill')}
    return out
def evaluate(V, verbose=True):
    err = 0.0; wsum = 0.0; rows = []
    for sc in CON:
        o = pic(sc, V); tc = tm = 0; df = dm = imf = im = 0
        for i, p in enumerate(P):
            x = o[p]; c = CON[sc][0][i]; m = ms(x['cyc'])
            tc += c; tm += m; df += x['dfill']; dm += x['dmiss']; imf += x['ifill']; im += x['imiss']
            err += c * math.log(c / m) ** 2; wsum += c
            rows.append((sc, p, c, m, c / m))
        rows.append((sc, 'WORK', tc, tm, tc / tm, dm / df, im / imf))
    rms = math.sqrt(err / wsum)
    if verbose:
        print('== %s  weighted RMS log error %.4f' % (V, rms))
        for r in rows:
            print('  %-8s %-6s console %6.1f model %6.1f ratio %.3f' % r[:5] + ('  Dstall/miss %.1f Istall/miss %.1f' % r[5:] if len(r) > 5 else ''))
    return rms, rows
if __name__ == '__main__':
    for V in sys.argv[1:]:
        evaluate(V)
