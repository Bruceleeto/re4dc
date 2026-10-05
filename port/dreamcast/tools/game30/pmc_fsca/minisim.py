#!/usr/bin/env python3
"""minisim.py <file.S> <start label> <end label> [--taken label,...] [--loop N]: lane fm scheduling aid. Issues the
straight-line instructions between two labels of an SH-4 .S file with the hw model's rules (tools/hwmodel/hwsim.c:
groups, issue, latencies, in-order dual issue, WAW pairing ban, taken-branch redirect 2), no memory stalls.
Prints each instruction's issue cycle and the total. --loop N repeats the block N times (state carried) and prints
the per-iteration cycles of the last one."""
import re, sys

MT, EX, BR, LS, FE, CO = 'MT', 'EX', 'BR', 'LS', 'FE', 'CO'


def regs(s):
    return s.strip().lower()


def decode(mn, ops):
    """-> (group, issue, lat, defs, uses, def2, kind)"""
    o = [regs(x) for x in ops]
    d2 = []
    kind = ''
    if mn in ('mov',):
        if o[0].startswith('#'):
            return EX, 1, 1, [o[1]], [], [], ''
        return MT, 1, 0, [o[1]], [o[0]], [], ''
    if mn in ('add', 'sub', 'and', 'or', 'xor'):
        if o[0].startswith('#'):
            return EX, 1, 1, [o[1]], [o[1]], [], ''
        return EX, 1, 1, [o[1]], [o[1], o[0]], [], ''
    if mn in ('rotl', 'rotr', 'shll', 'shlr', 'shal', 'shar'):
        return EX, 1, 1, [o[0], 't'], [o[0], 't'], [], ''
    if mn in ('shll2', 'shll8', 'shll16', 'shlr2', 'shlr8', 'shlr16'):
        return EX, 1, 1, [o[0]], [o[0]], [], ''
    if mn in ('movt',):
        return EX, 1, 1, [o[0]], ['t'], [], ''
    if mn in ('neg', 'not', 'extu.b', 'extu.w', 'exts.b', 'exts.w', 'swap.w', 'swap.b'):
        return EX, 1, 1, [o[1]], [o[0]], [], ''
    if mn.startswith('cmp/') or mn == 'tst':
        u = [x for x in o if not x.startswith('#')]
        return MT, 1, 1, ['t'], u, [], ''
    if mn in ('bt', 'bf'):
        return BR, 1, 2, [], ['t'], [], 'brc'
    if mn in ('bt/s', 'bf/s'):
        return BR, 1, 2, [], ['t'], [], 'brcd'
    if mn in ('bra', 'bsr'):
        return BR, 1, 2, [], [], [], 'bru'
    if mn in ('jsr', 'jmp'):
        return CO, 2, 3, [], [o[0].strip('@')], [], 'brreg'
    if mn == 'rts':
        return CO, 2, 3, [], ['pr'], [], 'brreg'
    if mn == 'nop':
        return MT, 1, 1, [], [], [], ''
    if mn == 'mova':
        return EX, 1, 1, ['r0'], [], [], ''
    if mn == 'movca.l':
        return LS, 1, 3, [], [o[1].strip('@'), 'r0'], [], 'store'
    if mn == 'pref':
        return LS, 1, 1, [], [o[0].strip('@')], [], ''
    if mn in ('mov.l', 'mov.w', 'mov.b'):
        a, b = o
        if a.startswith('@'):           # load
            m = re.match(r'@\((\-?\d+|r0),(r\d+)\)', a)
            if m:
                u = [m.group(2)] + (['r0'] if m.group(1) == 'r0' else [])
                return LS, 1, 2, [b], u, [], 'load'
            if a.endswith('+'):
                r = a[1:-1]
                return LS, 1, 2, [b], [r], [r], 'load'
            if re.match(r'@r\d+$', a):
                return LS, 1, 2, [b], [a[1:]], [], 'load'
            return LS, 1, 2, [b], [], [], 'load'   # pc-relative literal
        # store
        m = re.match(r'@\((\-?\d+|r0),(r\d+)\)', b)
        if m:
            return LS, 1, 1, [], [a, m.group(2)], [], 'store'
        if b.startswith('@-'):
            r = b[2:]
            return LS, 1, 1, [], [a, r], [r], 'store'
        return LS, 1, 1, [], [a, b[1:]], [], 'store'
    if mn in ('fmov.s', 'fmov'):
        a, b = o
        if a.startswith('@'):
            m = re.match(r'@\(r0,(r\d+)\)', a)
            if m:
                return LS, 1, 2, [b], [m.group(1), 'r0'], [], 'load'
            if a.endswith('+'):
                r = a[1:-1]
                return LS, 1, 2, [b], [r], [r], 'load'
            return LS, 1, 2, [b], [a[1:]], [], 'load'
        if b.startswith('@'):
            m = re.match(r'@\(r0,(r\d+)\)', b)
            if m:
                return LS, 1, 1, [], [a, m.group(1), 'r0'], [], 'store'
            if b.startswith('@-'):
                r = b[2:]
                return LS, 1, 1, [], [a, r], [r], 'store'
            return LS, 1, 1, [], [a, b[1:]], [], 'store'
        return LS, 1, 0, [b], [a], [], ''
    if mn in ('fneg', 'fabs'):
        return LS, 1, 0, [o[0]], [o[0]], [], ''
    if mn in ('fldi0', 'fldi1'):
        return LS, 1, 0, [o[0]], [], [], ''
    if mn in ('fadd', 'fsub', 'fmul'):
        return FE, 1, 3, [o[1]], [o[1], o[0]], [], ''
    if mn == 'ftrc':
        return FE, 1, 3, ['fpul'], [o[0]], [], ''
    if mn == 'float':
        return FE, 1, 3, [o[1]], ['fpul'], [], ''
    if mn == 'fsca':
        n = int(o[1][2:])
        return FE, 1, 4, ['fr%d' % n, 'fr%d' % (n + 1)], ['fpul'], [], ''
    if mn == 'lds' and o[1] == 'fpul':
        return LS, 1, 1, ['fpul'], [o[0]], [], ''
    if mn == 'sts' and o[0] == 'fpul':
        return LS, 1, 3, [o[1]], ['fpul'], [], ''
    if mn == 'fsts':
        return LS, 1, 0, [o[1]], ['fpul'], [], ''
    if mn == 'flds':
        return LS, 1, 0, ['fpul'], [o[0]], [], ''
    if mn in ('fcmp/gt', 'fcmp/eq'):
        return FE, 1, 2, ['t'], [o[0], o[1]], [], ''
    if mn in ('sts.l', 'lds.l'):
        return CO, 2, 2, [], [], [], ''
    raise SystemExit('unknown: %s %s' % (mn, ops))


def parse(path, start, end):
    out, on = [], False
    for raw in open(path):
        l = raw.split('/*')[0].split('!')[0].rstrip()
        if not l.strip():
            continue
        m = re.match(r'^\s*([.\w]+):\s*(.*)$', l)
        if m:
            lab = m.group(1)
            if lab == end and on:
                break
            if lab == start:
                on = True
            l = m.group(2)
            if not l.strip():
                continue
        if not on:
            continue
        s = l.strip()
        if s.startswith('.'):
            continue
        p = s.split(None, 1)
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
        out.append((s, mn, ops))
    return out


def main():
    a = sys.argv[1:]
    path, start, end = a[0], a[1], a[2]
    taken = set()
    loops = 1
    if '--taken' in a:
        taken = set(a[a.index('--taken') + 1].split(','))
    if '--loop' in a:
        loops = int(a[a.index('--loop') + 1])
    ins = parse(path, start, end)
    rready = {}
    t_prev, prev_paired, prev_issue, prev_grp, prev_def = 0.0, True, 1, CO, set()
    floor = 0.0
    br_t = -1
    counts = {}
    for it in range(loops):
        t_start = None
        rows = []
        for s, mn, ops in ins:
            g, iss, lat, defs, uses, d2, kind = decode(mn, ops)
            counts[g] = counts.get(g, 0) + (1 if it == 0 else 0)
            base = t_prev + prev_issue
            can = (not prev_paired) and prev_grp != CO and g != CO and (g != prev_grp or g == MT) and not (set(defs) & prev_def)
            dep = max([rready.get(u, 0.0) for u in uses] + [0.0])
            if can and dep <= t_prev and floor <= t_prev:
                t = t_prev
                paired = True
            else:
                t = max(base, dep, floor)
                paired = False
            floor = 0.0
            for dd in defs:
                rready[dd] = t + lat
            for dd in d2:
                if dd not in defs:
                    rready[dd] = t + 1
            if t_start is None:
                t_start = t
            # taken branch redirect
            lab = ops[0].strip() if ops else ''
            if kind == 'brc' and lab in taken:
                floor = t + 2
            if kind in ('brcd', 'bru'):
                br_t = t
            if kind in ('brcd', 'bru') and (kind == 'bru' or lab in taken):
                pend = t + 2
            else:
                pend = None
            rows.append((t, paired, g, s))
            t_prev, prev_paired, prev_issue, prev_grp, prev_def = t, paired, iss, g, set(defs)
            if g == CO:
                prev_paired = True
            if 'pend_slot' in locals() and pend_slot is not None:
                floor = max(floor, pend_slot)
                pend_slot = None
            if pend is not None:
                pend_slot = pend   # applies after the delay slot instruction
        t_end = t_prev + prev_issue
        if it == loops - 1:
            for t, p, g, s in rows:
                print('%7.1f %s %s  %s' % (t - t_start, '|' if p else ' ', g, s))
            print('cycles (this iteration): %.1f  instructions %d  groups %s' % (t_end - t_start, len(ins), counts))


if __name__ == '__main__':
    main()
