#!/usr/bin/env python3
"""iv_incl.py <hwmodel dir> [drawn|skip] [top]: lane iv (2026-10-05). Inclusive hw ms per tick of the ENC_CENSUS=2
per-state wrappers (re4dc_iv_t_<state> around a Ganado's emTrans, re4dc_iv_r_<state> around its ModelRender) from the
hw model's call tree (proj-*/cg.cg.tsv, as tools/game30/hw_incl.py, without its logic-only filter), their calls per
tick, ms per call, and the subtree's self ms by function (top N). Also the whole Trans / Render / emTrans /
ModelRender subtrees for scale."""
import bisect, collections, os, re, sys

E = sys.argv[1]
MODES = [sys.argv[2]] if len(sys.argv) > 2 and sys.argv[2] in ('drawn', 'skip') else ['drawn', 'skip']
TOP = int(sys.argv[3]) if len(sys.argv) > 3 else 12
STATES = ['new', 'hidden', 'frustum', 'off', 'fog', 'empty', 'drawn', 'source', 'other']


def short(n):
    n = re.sub(r'\(anonymous namespace\)::', '', n)
    return n.split('(')[0] if '(' in n and not n.startswith('(') else n


def load(mode):
    P = os.path.join(E, 'proj-drawn' if mode == 'drawn' else 'proj-skip')
    syms = []
    for l in open(os.path.join(P, 'cg.syms.txt')):
        p = l.rstrip('\n').split(' ', 2)
        if len(p) == 3:
            syms.append((int(p[0], 16), p[2]))
    syms.sort()
    sa = [a for a, _ in syms]

    def name(a):
        i = bisect.bisect_right(sa, a) - 1
        base, n = syms[i]
        return n if base == a else '%s+0x%x' % (n, a - base)

    nodes, kids = {}, collections.defaultdict(list)
    with open(os.path.join(P, 'cg.cg.tsv')) as f:
        next(f)
        for l in f:
            i, par, e, selfc, calls = l.split('\t')
            i = int(i); par = int(par)
            nodes[i] = [par, int(e, 16), float(selfc), int(calls)]
            if i:
                kids[par].append(i)
    nfr = sum(1 for _ in open(os.path.join(P, 'cgsim.frames.tsv'))) - 1
    fn = {n: (short(name(nodes[n][1])) if n else '<root>') for n in nodes}
    return nodes, kids, fn, nfr


def subtree(nodes, kids, fn, rx):
    """Outermost matches of rx: (inclusive cycles, calls, Counter of self cycles by function)."""
    tot, calls, sub = 0.0, 0, collections.Counter()
    stack = [(0, False)]
    while stack:
        n, inside = stack.pop()
        f_ = fn[n]
        if not inside and rx.search(f_):
            inside = True
            calls += nodes[n][3]
        if inside:
            tot += nodes[n][2]
            sub[f_] += nodes[n][2]
        for c in kids.get(n, []):
            stack.append((c, inside))
    return tot, calls, sub


for mode in MODES:
    try:
        nodes, kids, fn, nfr = load(mode)
    except FileNotFoundError as e:
        print('%s: %s' % (mode, e)); continue
    K = 200000.0 * nfr
    print('== %s %s (%d ticks)' % (os.path.basename(E.rstrip('/')), mode, nfr))
    for label, pat in (('Trans', r'^Trans$'), ('Render', r'^Render$'), ('emTrans (all enemies)', r'^emTrans$'),
                       ('ModelRender (all models)', r'^ModelRender$')):
        t, c, _ = subtree(nodes, kids, fn, re.compile(pat))
        print('  %-26s %7.3f ms/tick  %6.1f calls/tick' % (label, t / K, c / nfr))
    for side, pre in (('trans', 're4dc_iv_t_'), ('render', 're4dc_iv_r_')):
        allt = 0.0
        for s in STATES:
            t, c, sub = subtree(nodes, kids, fn, re.compile('^' + pre + s + '$'))
            allt += t
            if not c:
                continue
            print('  %s %-8s %7.3f ms/tick  %5.2f calls/tick  %6.3f ms/call' % (side, s, t / K, c / nfr, t / K / (c / nfr)))
            print('      ' + ', '.join('%s %.3f' % (k, v / K) for k, v in sub.most_common(TOP)))
        print('  %s all Ganados %.3f ms/tick' % (side, allt / K))
