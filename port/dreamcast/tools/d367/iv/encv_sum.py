#!/usr/bin/env python3
"""encv_sum.py <run-output.txt> [A:B ...]: mean ENCV states per drawn image (ENC_CENSUS=2, lane iv) over game-tick
windows (t= field), plus the ENC line means (ga/gr/go/gs) over the same lines."""
import re, sys
STATES = ['new', 'hidden', 'frustum', 'off', 'fog', 'empty', 'drawn', 'source', 'other']
txt = open(sys.argv[1], 'rb').read().decode('latin-1')
ev, en = [], []
for l in txt.splitlines():
    m = re.match(r'ENCV f=(\d+) n=(\d+) st=([\d/]+) mis=(\d+) x5=([\d/]+) tri=(\d+) esrc=(\d+) full=(\d+) t=(\d+)(?: fx=([\d/]+))?', l)
    if m:
        ev.append(dict(f=int(m[1]), n=int(m[2]), st=[int(x) for x in m[3].split('/')], mis=int(m[4]),
                       x5=[int(x) for x in m[5].split('/')], tri=int(m[6]), esrc=int(m[7]), full=int(m[8]), t=int(m[9]),
                       fx=[int(x) for x in m[10].split('/')] if m[10] else None))
        continue
    m = re.match(r'ENC f=(\d+) ga=(\d+) oa=(\d+) gr=(\d+) go=(\d+) gs=(\d+) gx=(\d+) .* t=(\d+)', l)
    if m:
        en.append(dict(ga=int(m[2]), oa=int(m[3]), gr=int(m[4]), go=int(m[5]), gs=int(m[6]), gx=int(m[7]), t=int(m[8])))
wins = sys.argv[2:] or ['0:999999']
for w in wins:
    a, b = (int(x) for x in w.split(':'))
    rows = [r for r in ev if a <= r['t'] <= b and r['n']]
    if not rows:
        print('%s: no ENCV lines with images' % w); continue
    n = sum(r['n'] for r in rows)
    st = [sum(r['st'][i] for r in rows) / n for i in range(9)]
    print('%s: %d lines, %d images; per image: %s; mis %.3f, x5 off/empty/drawn %s, tri %.0f, empty-source %.2f, full %d' % (
        w, len(rows), n, ' '.join('%s %.2f' % (s, v) for s, v in zip(STATES, st)), sum(r['mis'] for r in rows) / n,
        '/'.join('%.2f' % (sum(r['x5'][i] for r in rows) / n) for i in range(3)), sum(r['tri'] for r in rows) / n,
        sum(r['esrc'] for r in rows) / n, max(r['full'] for r in rows)))
    fr = [r for r in rows if r['fx']]
    if fr:
        print('   fx per image: live %.2f; on Ganado parts (m_pMod) invisible/visible/other %.2f/%.2f/%.2f; owned (Core_pEm) %.2f/%.2f/%.2f' % tuple(
            [sum(r['fx'][0] for r in fr) / n] + [sum(r['fx'][i] for r in fr) / n for i in range(1, 7)]))
    er = [r for r in en if a <= r['t'] <= b]
    if er:
        print('   ENC: ga %.2f oa %.2f gr %.2f go %.2f gs %.2f gx %.2f' % tuple(sum(r[k] for r in er) / len(er) for k in ('ga', 'oa', 'gr', 'go', 'gs', 'gx')))
