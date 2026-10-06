#!/usr/bin/env python3
"""el_elc.py <run-output.txt> <nm -n -C file> [ticks=80]: the lane el census (EL_CENSUS=1, "ELC" lines) summarised.
Line queries grouped by caller chain (hitCheck2's caller, getFloor/hitCheck's caller, rckLineHitCheck's caller,
getNearPoint's caller) over all enemies, then by enemy; getNearPoint repeats; skeleton sameness; part-world redundancy.
Lane el 2026-10-05."""
import bisect, collections, re, sys

RUN, NM = sys.argv[1], sys.argv[2]
TICKS = int(sys.argv[3]) if len(sys.argv) > 3 else 80

syms = []
for l in open(NM, errors='replace'):
    p = l.rstrip('\n').split(' ', 2)
    if len(p) == 3 and p[1].lower() in ('t', 'w'):
        try:
            syms.append((int(p[0], 16), p[2]))
        except ValueError:
            pass
syms.sort()
sa = [a for a, _ in syms]


def fn(a, off=False):
    if a == 0:
        return '-'
    i = bisect.bisect_right(sa, a) - 1
    if i < 0:
        return '%08x' % a
    base, n = syms[i]
    n = re.sub(r'\(anonymous namespace\)::', '', n)
    n = n.split('(')[0] if '(' in n and not n.startswith('(') else n
    return n + ('+0x%x' % (a - base) if off else '')


lq, lw, lr, gn, sk, pw = [], {}, {}, [], [], []
head = None
KV = re.compile(r'(\w+)=([0-9a-fx,]+)')
for l in open(RUN, errors='replace'):
    i = l.find('ELC ')
    if i < 0:
        continue
    l = l[i:].strip()
    kind = l.split()[1]
    d = dict(KV.findall(l))
    if kind == 'begin':
        head = l
    elif kind in ('lq', 'lw', 'lr'):
        key = tuple(int(d[k], 16) for k in ('ra0', 'ra1', 'ra2', 'ra3')) + (d['em'], d['live'])
        if kind == 'lq':
            lq.append((key, {k: int(v) for k, v in d.items() if k in ('n', 'new', 'same', 'prev', 'r8', 'mis', 'len')}))
        elif kind == 'lw':
            lw[key] = {k: int(v) for k, v in d.items() if k not in ('ra0', 'ra1', 'ra2', 'ra3', 'em', 'live')}
        else:
            lr[key] = {k: [int(x) for x in v.split(',')] for k, v in d.items() if k in ('same', 'prev', 'r8')}
    elif kind == 'gn':
        gn.append((int(d['ra'], 16), d['em'], {k: (int(v) if ',' not in v else [int(x) for x in v.split(',')])
                                               for k, v in d.items() if k not in ('ra', 'em')}))
    elif kind == 'sk':
        sk.append({k: (int(v, 16) if k == 'id' else int(v)) for k, v in d.items()})
    elif kind == 'pw':
        pw.append({k: (int(v, 16) if k == 'id' else int(v)) for k, v in d.items()})

print(head)
print('window %d ticks; per-tick numbers = totals / %d' % (TICKS, TICKS))


def chain(key):
    ra0, ra1, ra2, ra3 = key[:4]
    parts = [fn(ra0)]
    if ra1:
        parts.append(fn(ra1))
    if ra2:
        parts.append(fn(ra2))
    if ra3:
        parts.append(fn(ra3))
    # collapse: the chain from the outermost known caller inwards
    return ' < '.join(parts)


agg = collections.OrderedDict()
for key, q in lq:
    c = chain(key)
    a = agg.setdefault(c, dict(n=0, new=0, same=0, prev=0, r8=0, mis=0, len=0, w=collections.Counter(),
                                wr=[collections.Counter(), collections.Counter(), collections.Counter()], ems=set()))
    for k in ('n', 'new', 'same', 'prev', 'r8', 'mis', 'len'):
        a[k] += q[k]
    a['w'].update(lw.get(key, {}))
    r = lr.get(key)
    if r:
        for ci, nm in enumerate(('same', 'prev', 'r8')):
            for fi, f in enumerate(('alive', 'leaves', 'listed', 'tested')):
                a['wr'][ci][f] += r[nm][fi]
    a['ems'].add(key[4])

tot = dict(n=0, new=0, same=0, prev=0, r8=0, mis=0, tested=0, rtested=[0, 0, 0], leaves=0, rleaves=[0, 0, 0])
print('\n== line queries by caller chain (hitCheck2 caller < getFloor/hitCheck caller < rckLineHitCheck caller < '
      'getNearPoint caller)')
print('%-88s %6s %5s %5s %5s %5s %4s | %5s %5s %6s %6s %5s %5s %5s %5s %4s' % (
    'chain', 'q/tk', 'new%', 'tick%', 'prev%', 'r8%', 'mis', 'pcs', 'leaf', 'listed', 'tested', 'axz', 'axyz', 'plane',
    'surv', 'hits'))
for c, a in sorted(agg.items(), key=lambda kv: -kv[1]['w']['tested']):
    n = max(a['n'], 1)
    w = a['w']
    print('%-88s %6.2f %5.1f %5.1f %5.1f %5.1f %4d | %5.1f %5.1f %6.1f %6.1f %5.1f %5.1f %5.1f %5.2f %4.2f' % (
        c[:88], a['n'] / TICKS, 100.0 * a['new'] / n, 100.0 * a['same'] / n, 100.0 * a['prev'] / n, 100.0 * a['r8'] / n,
        a['mis'], w['walked'] / n, w['leaves'] / n, w['listed'] / n, w['tested'] / n, w['axz'] / n, w['axyz'] / n,
        w['plane'] / n, w['surv'] / n, w['hits'] / n))
    for k in ('n', 'new', 'same', 'prev', 'r8', 'mis'):
        tot[k] += a[k]
    tot['tested'] += w['tested']
    tot['leaves'] += w['leaves']
    for ci in range(3):
        tot['rtested'][ci] += a['wr'][ci]['tested']
        tot['rleaves'][ci] += a['wr'][ci]['leaves']
n = max(tot['n'], 1)
print('ALL: %.2f queries/tick; new %.1f%%, same-tick repeat %.1f%%, prev-tick repeat %.1f%%, 2..8 back %.1f%%; mis %d; '
      'tested polys/tick %.1f, of which in same-tick repeats %.1f%%, prev-tick %.1f%%, 2..8 back %.1f%%; leaves/tick %.1f '
      '(repeats %.1f%% / %.1f%% / %.1f%%)' % (
          tot['n'] / TICKS, 100.0 * tot['new'] / n, 100.0 * tot['same'] / n, 100.0 * tot['prev'] / n, 100.0 * tot['r8'] / n,
          tot['mis'], tot['tested'] / TICKS, 100.0 * tot['rtested'][0] / max(tot['tested'], 1),
          100.0 * tot['rtested'][1] / max(tot['tested'], 1), 100.0 * tot['rtested'][2] / max(tot['tested'], 1),
          tot['leaves'] / TICKS, 100.0 * tot['rleaves'][0] / max(tot['leaves'], 1),
          100.0 * tot['rleaves'][1] / max(tot['leaves'], 1), 100.0 * tot['rleaves'][2] / max(tot['leaves'], 1)))

print('\n== line queries by enemy (em id, live)')
byem = collections.defaultdict(lambda: collections.Counter())
for key, q in lq:
    e = byem[(key[4], key[5])]
    for k in ('n', 'new', 'same', 'prev', 'r8'):
        e[k] += q[k]
    e['tested'] += lw.get(key, {}).get('tested', 0)
for (em, live), e in sorted(byem.items(), key=lambda kv: -kv[1]['n']):
    n = max(e['n'], 1)
    print('em %s live %s: %.2f q/tick new %.1f%% tick %.1f%% prev %.1f%% r8 %.1f%% tested/q %.1f' % (
        em, live, e['n'] / TICKS, 100.0 * e['new'] / n, 100.0 * e['same'] / n, 100.0 * e['prev'] / n,
        100.0 * e['r8'] / n, e['tested'] / n))

print('\n== getNearPoint by caller')
gagg = collections.defaultdict(lambda: collections.Counter())
for ra, em, d in gn:
    g = gagg[fn(ra)]
    for k in ('n', 'new', 'same', 'prev', 'r8', 'mis', 'lq'):
        g[k] += d[k]
    for ci in range(3):
        g['lqr%d' % ci] += d['lqr'][ci]
for c, g in gagg.items():
    n = max(g['n'], 1)
    print('%-40s %.2f calls/tick new %.1f%% tick %.1f%% prev %.1f%% r8 %.1f%% mis %d; line queries inside %.2f/tick '
          '(in repeats: tick %d prev %d r8 %d)' % (c, g['n'] / TICKS, 100.0 * g['new'] / n, 100.0 * g['same'] / n,
                                                     100.0 * g['prev'] / n, 100.0 * g['r8'] / n, g['mis'],
                                                     g['lq'] / TICKS, g['lqr0'], g['lqr1'], g['lqr2']))

print('\n== skeletons after move() (same = every motion/pose/matrix word equal to one tick earlier)')
for s in sorted(sk, key=lambda s: -s['n']):
    print('id %02x live %d: %.2f units/tick, same %.1f%%, parts/unit %.1f' % (
        s['id'], s['live'], s['n'] / TICKS, 100.0 * s['same'] / max(s['n'], 1), s['parts'] / max(s['n'], 1)))

print('\n== part-world passes (redundant = inputs equal to the model\'s previous pass, same tick / previous tick)')
for p in sorted(pw, key=lambda p: -p['n']):
    print('id %02x: %.2f passes/tick, redundant same tick %.1f%%, prev tick %.1f%%, parts/pass %.1f, redundant parts %.1f%%' % (
        p['id'], p['n'] / TICKS, 100.0 * p['red_tick'] / max(p['n'], 1), 100.0 * p['red_prev'] / max(p['n'], 1),
        p['parts'] / max(p['n'], 1), 100.0 * p['parts_red'] / max(p['parts'], 1)))
