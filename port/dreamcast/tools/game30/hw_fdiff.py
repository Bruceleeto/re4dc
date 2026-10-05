#!/usr/bin/env python3
"""hw_fdiff.py <hwmodel A dir> <hwmodel B dir> [touched-regex]: function-level A/B of two hwmodel runs
(proj-{drawn,skip}/rep/functions.tsv, hw ms per tick): the touched set's sum (default: GAME_ROT_FSCA's, the
local-matrix stage with every caller of re4dc_sincosf), the largest other per-function deltas and their net
(whole tick, all callers; the pace / retrace waits left out of the net). Lane fm 2026-10-05."""
import os, re, sys

if len(sys.argv) < 3:
    sys.exit(__doc__)
A, B = sys.argv[1], sys.argv[2]
TOUCH = re.compile(sys.argv[3] if len(sys.argv) > 3 else
                   r'^(cModel::partsMatCalc|re4dc_pmc_run|re4dc_pmc_part_slow|pmc_words|RotMatrix|RotMatrix_uncached|'
                   r're4dc_sincosf|sincosf_big|ScaleMatrix|TransMatrix|re4dc_sh4_MTXCopy|PSMTXCopy)$')


def short(n):
    n = re.sub(r'\(anonymous namespace\)::', '', n)
    if n.startswith('void ') or n.startswith('int ') or n.startswith('float '):
        n = n.split(' ', 1)[1]
    return n.split('(')[0] if '(' in n and not n.startswith('(') else n


def load(d, mode):
    p = os.path.join(d, 'proj-drawn' if mode == 'drawn' else 'proj-skip', 'rep', 'functions.tsv')
    out = {}
    with open(p) as f:
        hdr = next(f).rstrip('\n').split('\t')
        hi = hdr.index('hw_ms')
        for l in f:
            c = l.rstrip('\n').split('\t')
            k = short(c[0])
            out[k] = out.get(k, 0.0) + float(c[hi])
    return out


for mode in ('drawn', 'skip'):
    a, b = load(A, mode), load(B, mode)
    keys = set(a) | set(b)
    ta = sum(v for k, v in a.items() if TOUCH.search(k))
    tb = sum(v for k, v in b.items() if TOUCH.search(k))
    print('== %s: touched set A %.3f  B %.3f  delta %+.3f ms/tick; all functions A %.2f B %.2f delta %+.2f' % (
        mode, ta, tb, tb - ta, sum(a.values()), sum(b.values()), sum(b.values()) - sum(a.values())))
    for k in sorted((k for k in keys if TOUCH.search(k)), key=lambda k: b.get(k, 0) - a.get(k, 0)):
        print('   T %-28s %7.3f %7.3f %+7.3f' % (k[:28], a.get(k, 0), b.get(k, 0), b.get(k, 0) - a.get(k, 0)))
    d = sorted(((b.get(k, 0) - a.get(k, 0), k) for k in keys if not TOUCH.search(k)), key=lambda x: -abs(x[0]))
    print('   largest other deltas: ' + ', '.join('%s %+.3f' % (k[:40], v) for v, k in d[:14]))
    print('   other functions net (excl. pace / retrace waits): %+.3f' % sum(
        v for v, k in d if not re.search(r'pace_end|retrace|vblank|wait', k)))
