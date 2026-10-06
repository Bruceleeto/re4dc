#!/usr/bin/env python3
"""el_lqcost.py <hwmodel dir> <elc summary (el_elc.py output)>: hw ms per tick of every line query (hitCheck2
inclusive) inside gameMainLoop / GameTask, grouped by the census caller chain, joined with the census repeat
fractions and polygon funnel: upper bounds for (a) same-tick de-dup, (b) cross-tick cache, (c) an AABB prefilter
(leaf kernel cycles x the share of tested polygons whose box misses the segment's). Both tick types. Lane el."""
import bisect, collections, os, re, sys

E, ELC = sys.argv[1], sys.argv[2]


def short(n):
    n = re.sub(r'\(anonymous namespace\)::', '', n)
    n = n.split('(')[0] if '(' in n and not n.startswith('(') else n
    return n.replace('getNearPointCore', 'getNearPoint')


cen = {}
for l in open(ELC):
    m = re.match(r'^(\S.*?)\s{2,}(\d+\.\d+)\s+(\d+\.\d)\s+(\d+\.\d)\s+(\d+\.\d)\s+(\d+\.\d)\s+(\d+) \|\s+(.*)$', l.rstrip('\n'))
    if not m or ' < ' not in m.group(1) and not m.group(1).startswith('cSatMgr'):
        continue
    key = m.group(1).strip().replace('getNearPointCore', 'getNearPoint')
    w = [float(x) for x in m.group(8).split()]
    cen[key] = dict(q=float(m.group(2)), new=float(m.group(3)), tick=float(m.group(4)), prev=float(m.group(5)),
                    r8=float(m.group(6)), tested=w[3], axyz=w[5], listed=w[2])


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
        return syms[i][1]
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


for mode in ('drawn', 'skip'):
    nodes, kids, fn, nfr = load(mode)
    K = 200000.0 * nfr
    incl = {}

    def inc(n):
        st = [n]; tot = 0.0
        while st:
            x = st.pop(); tot += nodes[x][2]; st.extend(kids.get(x, []))
        return tot

    def sub(n, rx):
        st = [n]; tot = 0.0
        while st:
            x = st.pop()
            if rx.match(fn[x]):
                tot += inc(x); continue
            st.extend(kids.get(x, []))
        return tot
    LEAF = re.compile(r'^(re4dc_line_leaf2|re4dc_line_leaf)$')
    agg = collections.defaultdict(lambda: [0.0, 0.0, 0])
    st = [(0, False, ())]
    while st:
        n, inl, path = st.pop()
        if re.match(r'^(gameMainLoop|GameTask)$', fn[n]):
            inl = True
        if inl and fn[n] == 'cSatMgr::hitCheck2':
            p = path
            k = [p[-1]]
            if p[-1] in ('cSatMgr::hitCheck', 'cSatMgr::getFloor') and len(p) > 1:
                k.append(p[-2])
                if p[-2] == 'rckLineHitCheck' and len(p) > 2:
                    k.append(p[-3])
                    if p[-3] == 'getNearPoint' and len(p) > 3:
                        k.append(p[-4])
            if p[-1] == 'cSatMgr::wallAdjust' and len(p) > 1:
                k.append(p[-2])
            if len(k) == 4 and k[2] == 'getNearPoint' and k[3] in ('RouteCkPosToPosDis', 'RouteCkToPos'):
                k[3] = 'em10RouteCk'   # the census wrapper is inlined there: its caller is em10RouteCk
            key = ' < '.join(k)
            agg[key][0] += inc(n)
            agg[key][1] += sub(n, LEAF)
            agg[key][2] += nodes[n][3]
            continue
        st.extend((c, inl, path + (fn[n],)) for c in kids.get(n, []))
    print('== %s %s (%d sampled ticks): line queries in the game logic' % (os.path.basename(E), mode, nfr))
    print('%-72s %7s %6s %7s %6s %6s %6s | %7s %7s %7s' % ('chain', 'ms/tk', 'q/tk', 'leaf ms', 'tick%', 'xtick%', 'axyz%',
                                                          'dedup', 'cache', 'aabb'))
    T = [0.0] * 6
    for key, (c, lc, calls) in sorted(agg.items(), key=lambda kv: -kv[1][0]):
        z = cen.get(key)
        ms, lms = c / K, lc / K
        if z:
            dd = ms * z['tick'] / 100.0
            ca = ms * (z['tick'] + z['prev'] + z['r8']) / 100.0
            ab = lms * (1.0 - z['axyz'] / z['tested']) if z['tested'] else 0.0
            print('%-72s %7.3f %6.1f %7.3f %6.1f %6.1f %6.1f | %7.3f %7.3f %7.3f' % (
                key[:72], ms, calls / nfr, lms, z['tick'], z['prev'] + z['r8'],
                100.0 * z['axyz'] / z['tested'] if z['tested'] else 0, dd, ca, ab))
            T[3] += dd; T[4] += ca; T[5] += ab
        else:
            print('%-72s %7.3f %6.1f %7.3f   (no census row)' % (key[:72], ms, calls / nfr, lms))
        T[0] += ms; T[2] += lms
    print('%-72s %7.3f %6s %7.3f %6s %6s %6s | %7.3f %7.3f %7.3f' % ('ALL', T[0], '', T[2], '', '', '', T[3], T[4], T[5]))
    print()
