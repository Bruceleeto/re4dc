#!/usr/bin/env python3
"""hw_incl.py <hwmodel dir> <drawn|skip> <name-regex> [...]: inclusive LOGIC hw ms per tick of the subtrees of the
hw model's call tree (proj-*/cg.cg.tsv) rooted at the functions that match (outermost match only, under
gameMainLoop / GameTask), the calls per tick at those roots, and the subtree's self ms by function. Lane fm
2026-10-05; one Ganado's tick: '^cEm10::move$' (inclusive / calls)."""
import bisect, collections, os, re, sys
if len(sys.argv) < 4:
    sys.exit(__doc__)
E, MODE = sys.argv[1], sys.argv[2]
RX = [re.compile(r) for r in sys.argv[3:]]
P = os.path.join(E, 'proj-drawn' if MODE == 'drawn' else 'proj-skip')


def short(n):
    n = re.sub(r'\(anonymous namespace\)::', '', n)
    return n.split('(')[0] if '(' in n and not n.startswith('(') else n


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
K = 200000.0 * nfr
fn = {n: (short(name(nodes[n][1])) if n else '<root>') for n in nodes}
for rx in RX:
    tot = 0.0
    calls = 0
    sub = collections.Counter()
    stack = [(0, False, False)]
    while stack:
        n, inlogic, inside = stack.pop()
        f_ = fn[n]
        if re.match(r'^(gameMainLoop|GameTask)$', f_):
            inlogic = True
        start = False
        if inlogic and not inside and rx.search(f_):
            inside = True
            start = True
            calls += nodes[n][3]
        if inside:
            tot += nodes[n][2]
            sub[f_] += nodes[n][2]
        for c in kids.get(n, []):
            stack.append((c, inlogic, inside))
    print('%s %s  /%s/  inclusive %.3f ms/tick, %.1f calls/tick' % (os.path.basename(E), MODE, rx.pattern, tot / K, calls / nfr))
    print('   ' + ', '.join('%s %.3f' % (k, v / K) for k, v in sub.most_common(14)))
