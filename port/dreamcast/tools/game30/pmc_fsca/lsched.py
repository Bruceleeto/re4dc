#!/usr/bin/env python3
"""lsched.py <draft.s> [--out sched.s]: lane fm list scheduler for a straight-line SH-4 block under the hw model's
issue rules (minisim.decode). The draft is a semantically ordered instruction list with fixed registers; extra
dependencies are declared in '!' comments: '! uses r1 r12' / '! defs fr9' (branches to out-of-line code: their
targets' reads and writes), '! barrier' (nothing moves across). RAW (latency), WAR and WAW (order) edges come from
the registers; the greedy pass emits, at every step, the ready instruction with the earliest model issue time
(ties: longest latency path to the end, then draft order). Prints the schedule with issue cycles."""
import re, sys
sys.path.insert(0, __import__('os').path.dirname(__file__))
from minisim import decode, MT, EX, BR, LS, FE, CO


def parse_draft(path):
    ins = []
    for raw in open(path):
        line = raw.rstrip('\n')
        code, _, cmt = line.partition('!')
        code = code.split('/*')[0].strip()
        if not code:
            continue
        p = code.split(None, 1)
        mn = p[0].lower()
        ops = []
        if len(p) > 1:
            depth, cur = 0, ''
            for ch in p[1]:
                if ch == '(':
                    depth += 1
                elif ch == ')':
                    depth -= 1
                if ch == ',' and depth == 0:
                    ops.append(cur)
                    cur = ''
                else:
                    cur += ch
            ops.append(cur)
        g, iss, lat, defs, uses, d2, kind = decode(mn, ops)
        defs, uses, d2 = list(defs), list(uses), list(d2)
        m = re.search(r'uses\s+([\w ]+?)(?:\s+defs|\s*$|\s+barrier)', cmt)
        if m:
            uses += m.group(1).split()
        xdefs = []
        m = re.search(r'defs\s+([\w ]+?)(?:\s+uses|\s*$|\s+barrier)', cmt)
        if m:
            xdefs = m.group(1).split()
        barrier = 'barrier' in cmt
        ins.append(dict(text=code, mn=mn, g=g, iss=iss, lat=lat, defs=defs, uses=uses, d2=d2, kind=kind, xdefs=xdefs,
                        barrier=barrier, cmt=cmt.strip()))
    return ins


def build(ins):
    n = len(ins)
    preds = [dict() for _ in range(n)]   # j -> {i: ('raw', lat) | ('ord', 0) | ('waw', 0)}
    last_w = {}
    readers = {}
    last_bar = None
    pseudo = {}                          # reg -> annotated (order-only) writer since the last real write
    for j, x in enumerate(ins):
        alld = x['defs'] + [r for r in x['d2'] if r not in x['defs']]
        for r in x['uses']:
            if r in pseudo and pseudo[r] != j:
                preds[j].setdefault(pseudo[r], ('ord', 0))
        for r in alld + x['xdefs']:
            if r in pseudo and pseudo[r] != j:
                preds[j].setdefault(pseudo[r], ('ord', 0))
        for r in x['xdefs']:
            for i in readers.get(r, []):
                if i != j:
                    preds[j].setdefault(i, ('ord', 0))
            if r in last_w and last_w[r] != j:
                preds[j].setdefault(last_w[r], ('waw', 0))
        for r in x['uses']:
            if r in last_w:
                i = last_w[r]
                lat = ins[i]['lat'] if r in ins[i]['defs'] else 1
                if r.startswith('o_'):
                    lat = 0
                old = preds[j].get(i)
                if not old or old[0] != 'raw' or old[1] < lat:
                    preds[j][i] = ('raw', lat)
        for r in alld:
            for i in readers.get(r, []):
                if i != j:
                    preds[j].setdefault(i, ('ord', 0))
            if r in last_w and last_w[r] != j:
                preds[j].setdefault(last_w[r], ('waw', 0))
        if last_bar is not None:
            preds[j].setdefault(last_bar, ('ord', 0))
        if x['barrier']:
            for i in range(j):
                preds[j].setdefault(i, ('ord', 0))
            last_bar = j
        for r in x['uses']:
            readers.setdefault(r, []).append(j)
        for r in alld:
            last_w[r] = j
            readers[r] = []
            pseudo.pop(r, None)
        for r in x['xdefs']:
            pseudo[r] = j
    return preds


def priorities(ins, preds):
    n = len(ins)
    succ = [[] for _ in range(n)]
    for j in range(n):
        for i, (k, lat) in preds[j].items():
            succ[i].append((j, lat if k == 'raw' else 0))
    pr = [0] * n
    for i in range(n - 1, -1, -1):
        best = ins[i]['lat']
        for j, l in succ[i]:
            best = max(best, l + pr[j])
        pr[i] = best
    return pr


def schedule(ins, preds, pr, rnd=None):
    n = len(ins)
    done = [False] * n
    issue = [None] * n
    order = []
    st = dict(t_prev=0.0, paired=True, iss=1, grp=CO, pdef=set())
    rready = {}

    def when(j):
        x = ins[j]
        base = st['t_prev'] + st['iss']
        can = (not st['paired']) and st['grp'] != CO and x['g'] != CO and (x['g'] != st['grp'] or x['g'] == MT) \
            and not (set(x['defs']) & st['pdef'])
        dep = 0.0
        for i, (k, lat) in preds[j].items():
            if k == 'raw':
                dep = max(dep, issue[i] + lat)
        # order-only predecessors must already be emitted (checked by caller)
        if can and dep <= st['t_prev']:
            return st['t_prev'], True
        return max(base, dep), False

    for _ in range(n):
        cands = [j for j in range(n) if not done[j] and all(done[i] for i in preds[j])]
        best = None
        for j in cands:
            t, p = when(j)
            key = (t, -pr[j] - (rnd.random() * 6 if rnd else 0), j)
            if best is None or key < best[0]:
                best = (key, j, t, p)
        _, j, t, p = best
        done[j] = True
        issue[j] = t
        order.append(j)
        x = ins[j]
        st.update(t_prev=t, paired=p if x['g'] != CO else True, iss=x['iss'], grp=x['g'], pdef=set(x['defs']))
    return order, issue


def main():
    a = sys.argv[1:]
    ins = parse_draft(a[0])
    preds = build(ins)
    pr = priorities(ins, preds)
    order, issue = schedule(ins, preds, pr)
    if '--search' in a:
        import random
        rnd = random.Random(1)
        n = int(a[a.index('--search') + 1])
        def length(o, iss):
            return iss[o[-1]] - iss[o[0]] + ins[o[-1]]['iss']
        best = length(order, issue)
        for k in range(n):
            o2, i2 = schedule(ins, preds, pr, rnd)
            l2 = length(o2, i2)
            if l2 < best:
                best, order, issue = l2, o2, i2
        print('search best %.1f' % best)
    t0 = issue[order[0]]
    out = []
    prev_t = None
    for j in order:
        x = ins[j]
        pair = '|' if prev_t == issue[j] else ' '
        prev_t = issue[j]
        print('%6.1f %s %s  %-28s ! %s' % (issue[j] - t0, pair, x['g'], x['text'], x['cmt']))
        out.append('        %-30s%s' % (x['text'], ('! ' + x['cmt']) if x['cmt'] else ''))
    last = order[-1]
    print('cycles: %.1f  instructions %d' % (issue[last] - t0 + ins[last]['iss'], len(ins)))
    if '--out' in a:
        open(a[a.index('--out') + 1], 'w', newline='\n').write('\n'.join(out) + '\n')


if __name__ == '__main__':
    main()
