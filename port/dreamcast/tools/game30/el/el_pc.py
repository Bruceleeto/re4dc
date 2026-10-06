#!/usr/bin/env python3
"""el_pc.py <hwmodel A> <hwmodel B> <function regex>: calls and inclusive hw ms per tick of the matching calling-context
nodes (proj-{drawn,skip}/cg.cg.tsv), grouped by their parent function, A vs B. Lane el 2026-10-05."""
import bisect, collections, os, re, sys
def short(n):
    n = re.sub(r'\(anonymous namespace\)::', '', n)
    return n.split('(')[0] if '(' in n and not n.startswith('(') else n
def load(E, mode, rx):
    P = os.path.join(E, 'proj-' + mode)
    syms = []
    for l in open(os.path.join(P, 'cg.syms.txt')):
        p = l.rstrip('\n').split(' ', 2)
        if len(p) == 3: syms.append((int(p[0], 16), p[2]))
    syms.sort(); sa = [a for a, _ in syms]
    nodes, kids = {}, collections.defaultdict(list)
    with open(os.path.join(P, 'cg.cg.tsv')) as f:
        next(f)
        for l in f:
            i, par, e, selfc, n = l.split('\t'); i = int(i); par = int(par)
            a = int(e, 16); j = bisect.bisect_right(sa, a) - 1
            nodes[i] = (par, short(syms[j][1]) if i else '<root>', float(selfc), int(n))
            if i: kids[par].append(i)
    nfr = sum(1 for _ in open(os.path.join(P, 'cgsim.frames.tsv'))) - 1
    def inc(n):
        st = [n]; t = 0.0
        while st:
            x = st.pop(); t += nodes[x][2]; st.extend(kids.get(x, []))
        return t
    c = collections.defaultdict(lambda: [0, 0.0])
    for i, (par, nm, s, n) in nodes.items():
        if i and rx.match(nm):
            pn = nodes[par][1] if par in nodes else '?'
            c[pn][0] += n; c[pn][1] += inc(i)
    return c, nfr
rx = re.compile(sys.argv[3])
for mode in ('drawn', 'skip'):
    a, na = load(sys.argv[1], mode, rx); b, nb = load(sys.argv[2], mode, rx)
    for k in sorted(set(a) | set(b), key=lambda k: -(a[k][1] if k in a else 0)):
        aa = a.get(k, [0, 0.0]); bb = b.get(k, [0, 0.0])
        print('%s %-34s calls A %6.1f B %6.1f | ms A %6.3f B %6.3f d %+6.3f' % (mode, k[:34], aa[0] / na, bb[0] / nb, aa[1] / 200000 / na, bb[1] / 200000 / nb, (bb[1] / nb - aa[1] / na) / 200000))
