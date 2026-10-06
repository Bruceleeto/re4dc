#!/usr/bin/env python3
"""el_cat.py <hwmodel dir> [<hwmodel dir> ...]: inclusive breakdown of cEmMgr::move (the enemies' logic) by category,
per enemy class (cEmXX::move) and per tick, from the hw model's calling-context tree (proj-{drawn,skip}/cg.cg.tsv).
Every node's self cycles under cEmMgr::move go to one category, decided by its function-name path:
collision line queries by caller context, sphere queries, em-em, damage / hit, foot IK maths, skeleton, motion,
route (non-collision), manager, AI / think. Lane el 2026-10-05."""
import bisect, collections, os, re, sys

LINE = re.compile(r'^(cSatMgr::hitCheck2|cSatMgr::hitCheck|cSatMgr::getFloor|blkPolyLineCk|blkPolyLineCkCore|re4dc_line_\w+|'
                  r'At_poly_line_ck|At_poly_line_tail|rckLineHitCheck|lineLeaf|linePieceWalk|lineWalkLeaves)$')
SPHERE = re.compile(r'^(spwRun|spwWallPair|spwLeaf|spwFinish|blkPolySphereCk|blkPolySphereCkCore|cSatMgr::polySphereCk|'
                    r'At_poly_sphere_ck2?|At_surface_line_ck|re4dc_sphere_\w+|cSatBlock::hitCheckSphere|collision_sphere_hexahedron)$')
EMEM = re.compile(r'^(EmAtCheck|atchk\w*|__em_at_core|At_em_\w+)$')
DMG = re.compile(r'^(em\w*DmCk\w*|cDmg\w*|cDmgMgr::\w+|EmAtkHitCk\w*|emSphereAtCk|em\w*AtkCk|cDmgInfo::\w+|EmYarare\w*|'
                 r'Yarare\w*|em\w*Dmg\w*|em10Damage\w*|em10_R0_Damage|em\w+_R0_Damage)$')
IK = re.compile(r'^(InverseKinematics|ikCalc|IKInit|SetOrientation\w*|ik\w+)$')
SKEL = re.compile(r'^(cModel::partsMatCalc|cModel::partsWorldCalc|skelPartLive|cModel::partsFixAdjust|PartsWorldPosCalc|'
                  r're4dc_pmc_run|re4dc_pwc_\w+|RotMatrix|RotMatrix_uncached|ScaleMatrix|TransMatrix|cModel::matBlend)$')
MOTION = re.compile(r'^(Motion\w+|hermite\w*|C_QUAT\w+|re4dc_motion_\w+|VecRadLimit|cModel::getPartsPtr|motion\w*)$')
ROUTE = re.compile(r'^(em\w*RouteCk|Em\w*RouteCk|RouteCk\w*|getNearPoint|getNearInfo|em10RouteTargetSet)$')
MGR = re.compile(r'^(cEmMgr::move|emMove|cModel::updateOldPos|ShapeMove|cDmgInfo::move)$')
EMMOVE = re.compile(r'^cEm\w+::move$')
CTX = [(re.compile(r'^(InverseKinematics|ikCalc)$'), 'foot IK floor'),
       (re.compile(r'^cSatMgr::wallAdjust$'), 'wall (wallAdjust)'),
       (re.compile(r'^cSatMgr::scrAtCheckSphere(Air)?$'), 'ground (scrAtCheckSphere)'),
       (ROUTE, 'route / sight'),
       (re.compile(r'^(EmAtkHitCk\w*|em\w*AtkCk)$'), 'attack'),
       (re.compile(r'^em\w*SlopeMove$'), 'slope'),
       ]


def short(n):
    n = re.sub(r'\(anonymous namespace\)::', '', n)
    return n.split('(')[0] if '(' in n and not n.startswith('(') else n


def load(E, mode):
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


def category(path):
    # path: names from cEmMgr::move to the node
    li = next((i for i, f in enumerate(path) if LINE.match(f)), None)
    if li is not None:
        for rx, nm in CTX:
            if any(rx.match(f) for f in path[:li]):
                return 'line: ' + nm
        return 'line: other (%s)' % path[li - 1]
    if any(SPHERE.match(f) for f in path):
        return 'sphere queries'
    if any(EMEM.match(f) for f in path):
        return 'em-em (EmAtCheck)'
    if any(DMG.match(f) for f in path):
        return 'damage / hit'
    if any(IK.match(f) for f in path):
        return 'foot IK maths'
    if any(SKEL.match(f) for f in path):
        return 'skeleton'
    if any(MOTION.match(f) for f in path):
        return 'motion'
    if any(ROUTE.match(f) for f in path):
        return 'route (non-collision)'
    if MGR.match(path[-1]):
        return 'manager (emMove, oldpos, shape)'
    return 'AI / think + misc'


def run(E, mode):
    nodes, kids, fn, nfr = load(E, mode)
    K = 200000.0 * nfr
    cat = collections.Counter()           # (class, category) -> cycles
    calls = collections.Counter()         # class -> calls
    total = 0.0
    roots = []
    st = [(0, os.environ.get('EL_ALL') == '1')]  # EL_ALL=1: cEmMgr::move under any context (calls the trace entered mid-chain too)
    while st:
        n, inl = st.pop()
        if re.match(r'^(gameMainLoop|GameTask)$', fn[n]):
            inl = True
        if inl and fn[n] == 'cEmMgr::move':
            roots.append(n)
            continue
        st.extend((c, inl) for c in kids.get(n, []))
    for r in roots:
        st = [(r, (fn[r],), 'other')]
        while st:
            n, path, cls = st.pop()
            if EMMOVE.match(fn[n]) and cls == 'other' and n != r:
                cls = fn[n]
                calls[cls] += nodes[n][3]
            c = category(path)
            cat[(cls, c)] += nodes[n][2]
            total += nodes[n][2]
            for k in kids.get(n, []):
                st.append((k, path + (fn[k],), cls))
    return cat, calls, total / K, K, nfr


for E in sys.argv[1:]:
    for mode in ('drawn', 'skip'):
        cat, calls, tot, K, nfr = run(E, mode)
        print('== %s %s: cEmMgr::move %.3f hw ms per tick (%d sampled ticks)' % (os.path.basename(E), mode, tot, nfr))
        classes = sorted({c for c, _ in cat}, key=lambda c: -sum(v for (k, _), v in cat.items() if k == c))
        cats = sorted({x for _, x in cat}, key=lambda x: -sum(v for (_, k), v in cat.items() if k == x))
        hdr = '%-34s %8s' % ('category', 'all')
        for c in classes[:5]:
            hdr += ' %12s' % c.replace('::move', '')[:12]
        print(hdr)
        for x in cats:
            row = '%-34s %8.3f' % (x[:34], sum(v for (_, k), v in cat.items() if k == x) / K)
            for c in classes[:5]:
                row += ' %12.3f' % (cat.get((c, x), 0) / K)
            print(row)
        row = '%-34s %8.3f' % ('sum', tot)
        for c in classes[:5]:
            row += ' %12.3f' % (sum(v for (k, _), v in cat.items() if k == c) / K)
        print(row)
        row = '%-34s %8s' % ('calls per tick', '')
        for c in classes[:5]:
            row += ' %12.1f' % (calls.get(c, 0) / nfr)
        print(row)
        c10 = 'cEm10::move'
        if calls.get(c10):
            per = calls[c10] / nfr
            print('per Ganado (cEm10::move, %.1f calls per tick): ' % per + ', '.join(
                '%s %.3f' % (x, cat.get((c10, x), 0) / K / per) for x in cats if cat.get((c10, x), 0) / K / per >= 0.005) +
                  '; total %.3f' % (sum(v for (k, _), v in cat.items() if k == c10) / K / per))
        print()
