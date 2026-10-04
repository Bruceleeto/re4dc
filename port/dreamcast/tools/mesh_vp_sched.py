#!/usr/bin/env python3
"""mesh_vp_sched.py: list-schedule one iteration of the software-pipelined meshlet transform (front of vertex j + back of
vertex j-1) under hwsim.c's issue rules (in-order; an instruction pairs with the previous one when that one issued
alone, the groups differ or one is MT, they define no common register and its operands are ready), and print the
three asm macro bodies for room/mesh_fastpath_sched.hpp:
  VPS_PROLOGUE  front(0): the body's front instructions in body order (no back work exists yet)
  VPS_BODY      front(j) + back(j-1), the scheduled order (without the closing dt/bf)
  VPS_EPILOGUE  back(n-1): the body's back instructions in body order
The dependency graph keeps every RAW, WAR and WAW order on registers (r0-r3, %[c], %[k], FPUL, T, fr0-fr15) and
on the in / dst / oc / pf pointer chains, so no value or memory access changes; hwsim (simloop.py) judges the
result. Usage: mesh_vp_sched.py [TRIES] > body.inc"""
import random, sys

LS, EX, MT, FE = 'LS', 'EX', 'MT', 'FE'
# (asm, group, defs, uses, latency, role F=front(j) B=back(j-1))   latencies: hwsim.c decode table (SH-4 manual
# 8.3): load 2, lds fpul 1, float/fmul/fmac 3, fcmp->T 2, fsrra 5, ftrv 6, EX/MT 1, fmov reg 0, stores 0
def I(asm, g, d, u, lat, role='F'):
    return dict(asm=asm, g=g, d=set(d.split()), u=set(u.split()), lat=lat, role=role)

BODY = [
    I('mov.l   @%[in]+,r1', LS, 'r1 in', 'in', 2),
    I('mov.l   @%[in]+,r2', LS, 'r2 in', 'in', 2),
    I('mov.l   @%[in]+,r3', LS, 'r3 in', 'in', 2),
    I('extu.w  r1,r0', EX, 'r0', 'r1', 1),
    I('lds     r0,fpul', LS, 'fpul', 'r0', 1),
    I('float   fpul,fr0', FE, 'fr0', 'fpul', 3),            # x(j)
    I('shlr16  r1', EX, 'r1', 'r1', 1),
    I('lds     r1,fpul', LS, 'fpul', 'r1', 1),
    I('float   fpul,fr1', FE, 'fr1', 'fpul', 3),            # y(j)
    I('extu.w  r2,r0', EX, 'r0', 'r2', 1),
    I('lds     r0,fpul', LS, 'fpul', 'r0', 1),
    I('float   fpul,fr2', FE, 'fr2', 'fpul', 3),            # z(j)
    I('fldi1   fr3', LS, 'fr3', '', 0),
    I('VP_ASM_FTRV', FE, 'fr0 fr1 fr2 fr3', 'fr0 fr1 fr2 fr3', 6),
    # back(j-1): fr4 = 1/w(j-1), fr5/fr6 = x/y(j-1), %[k] = its depth bits; screen bits in r1
    I('fmul    fr4,fr5', FE, 'fr5', 'fr4 fr5', 3, 'B'),
    I('fmov.s  fr4,@-%[dst]', LS, 'dst', 'fr4 dst', 0, 'B'),   # z(j-1) @12
    I('fmul    fr4,fr6', FE, 'fr6', 'fr4 fr6', 3, 'B'),
    I('fcmp/gt fr5,fr7', FE, 'T', 'fr5 fr7', 2, 'B'),          # x<0
    I('rotcl   r1', EX, 'r1 T', 'r1 T', 1, 'B'),
    I('fcmp/gt fr12,fr5', FE, 'T', 'fr12 fr5', 2, 'B'),        # x>640
    I('rotcl   r1', EX, 'r1 T', 'r1 T', 1, 'B'),
    I('fcmp/gt fr6,fr7', FE, 'T', 'fr6 fr7', 2, 'B'),          # y<0
    I('fmov.s  fr6,@-%[dst]', LS, 'dst', 'fr6 dst', 0, 'B'),   # y(j-1) @8
    I('rotcl   r1', EX, 'r1 T', 'r1 T', 1, 'B'),
    I('fcmp/gt fr13,fr6', FE, 'T', 'fr13 fr6', 2, 'B'),        # y>480
    I('fmov.s  fr5,@-%[dst]', LS, 'dst', 'fr5 dst', 0, 'B'),   # x(j-1) @4
    I('rotcl   r1', EX, 'r1 T', 'r1 T', 1, 'B'),
    I('shll2   r1', EX, 'r1', 'r1', 1, 'B'),
    I('add     #56,%[dst]', MT, 'dst', 'dst', 1, 'B'),         # entry(j-1)+4 -> entry(j)+28
    I('or      %[k],r1', EX, 'r1', 'r1 k', 1, 'B'),
    I('mov.b   r1,@%[oc]', LS, 'ocmem', 'r1 oc', 0, 'B'),
    I('add     #1,%[oc]', MT, 'oc', 'oc', 1, 'B'),
    # front(j) continued: depth bits, moves, 1/w
    I('fcmp/gt fr3,fr14', FE, 'T', 'fr3 fr14', 2),             # w<near
    I('movt    %[k]', EX, 'k', 'T', 1),
    I('fcmp/gt fr15,fr3', FE, 'T', 'fr15 fr3', 2),             # w>far
    I('rotcl   %[k]', EX, 'k T', 'k T', 1),
    I('fmov    fr0,fr5', LS, 'fr5', 'fr0', 0),
    I('fmov    fr1,fr6', LS, 'fr6', 'fr1', 0),
    I('fmov    fr3,fr4', LS, 'fr4', 'fr3', 0),
    I('fmul    fr4,fr4', FE, 'fr4', 'fr4', 3),
    I('VP_ASM_FSRRA4', FE, 'fr4', 'fr4', 5),
    # u/v(j)
    I('mov     r2,r0', MT, 'r0', 'r2', 1),
    I('shlr16  r0', EX, 'r0', 'r0', 1),
    I('lds     r0,fpul', LS, 'fpul', 'r0', 1),
    I('float   fpul,fr0', FE, 'fr0', 'fpul', 3),
    I('fmov    fr9,fr2', LS, 'fr2', 'fr9', 0),
    I('fmac    fr0,fr8,fr2', FE, 'fr2', 'fr0 fr8 fr2', 3),     # u' = u*au+bu
    I('extu.w  r3,r0', EX, 'r0', 'r3', 1),
    I('lds     r0,fpul', LS, 'fpul', 'r0', 1),
    I('float   fpul,fr0', FE, 'fr0', 'fpul', 3),
    I('fmov    fr11,fr3', LS, 'fr3', 'fr11', 0),
    I('fmac    fr0,fr10,fr3', FE, 'fr3', 'fr0 fr10 fr3', 3),   # v' = v*av+bv
    # colour(j): ARGB1555 high/low byte LUT words, and/or material bits
    I('shlr16  r3', EX, 'r3', 'r3', 1),
    I('extu.b  r3,r0', EX, 'r0', 'r3', 1),
    I('shll2   r0', EX, 'r0', 'r0', 1),
    I('mov.l   @(r0,%[lo]),%[c]', LS, 'c', 'r0 lo', 2),
    I('shlr8   r3', EX, 'r3', 'r3', 1),
    I('mov     r3,r0', MT, 'r0', 'r3', 1),
    I('shll2   r0', EX, 'r0', 'r0', 1),
    I('mov.l   @(r0,%[hi]),r2', LS, 'r2', 'r0 hi', 2),
    I('or      r2,%[c]', EX, 'c', 'r2 c', 1),
    I('and     %[andm],%[c]', EX, 'c', 'c andm', 1),
    I('or      %[orb],%[c]', EX, 'c', 'c orb', 1),
    I('mov.l   %[c],@-%[dst]', LS, 'dst', 'c dst', 0),         # argb(j) @24
    I('fmov.s  fr3,@-%[dst]', LS, 'dst', 'fr3 dst', 0),        # v(j) @20
    I('fmov.s  fr2,@-%[dst]', LS, 'dst', 'fr2 dst', 0),        # u(j) @16
    I('pref    @%[pf]', LS, 'pfmem', 'pf', 0),
    I('add     #12,%[pf]', MT, 'pf', 'pf', 1),
]
DT = I('dt      %[count]', EX, 'count T', 'count', 1)

def preds(body):
    out = [set() for _ in body]
    for j in range(len(body)):
        for i in range(j):
            a, b = body[i], body[j]
            if (a['d'] & b['u']) or (a['u'] & b['d']) or (a['d'] & b['d']):
                out[j].add(i)
    return out

def issue(order, body, ready):
    """hwsim's in-order issue: returns issue times; `ready` register -> cycle (mutated)"""
    t_prev, prev_paired, prev = -1, True, None
    times = []
    for i in order:
        ins = body[i]
        dep = max([ready.get(r, -99) for r in ins['u']] + [-99])
        can_pair = (prev is not None and not prev_paired and (ins['g'] != prev['g'] or ins['g'] == MT or prev['g'] == MT)
                    and not (ins['d'] & prev['d']) and dep <= t_prev)
        t = t_prev if can_pair else max(t_prev + 1, dep)
        prev_paired = can_pair
        for r in ins['d']:
            ready[r] = t + ins['lat']
        times.append(t); t_prev, prev = t, ins
    return times

def span(order, body, iters=8):
    full = list(order) + [len(body)]
    b = body + [DT]
    ready = {}
    for _ in range(iters):
        times = issue(full, b, ready)
        s = times[-1] + 1 + 1     # bf (BR) issues after dt, +1 redirect
        ready = {r: v - s for r, v in ready.items()}
    return s

def schedule(body, rnd, pred):
    n = len(body)
    succ = [[] for _ in range(n)]
    for j in range(n):
        for i in pred[j]:
            succ[i].append(j)
    prio = [0] * n
    for i in reversed(range(n)):
        prio[i] = body[i]['lat'] + max([prio[j] for j in succ[i]] + [0])
    prio[[k for k, x in enumerate(body) if x['asm'] == 'VP_ASM_FSRRA4'][0]] += rnd.randint(0, 12)
    done, order, ready = set(), [], {'fr4': rnd.randint(0, 4)}
    t_prev, prev_paired, prev = -1, True, None
    while len(order) < n:
        best = None
        for i in range(n):
            if i in done or not pred[i] <= done:
                continue
            ins = body[i]
            dep = max([ready.get(r, -99) for r in ins['u']] + [-99])
            can_pair = (prev is not None and not prev_paired and (ins['g'] != prev['g'] or ins['g'] == MT or prev['g'] == MT)
                        and not (ins['d'] & prev['d']) and dep <= t_prev)
            t = t_prev if can_pair else max(t_prev + 1, dep)
            key = (t, -prio[i] + rnd.random() * 3)
            if best is None or key < best[0]:
                best = (key, i, can_pair, t)
        _, i, can_pair, t = best
        for r in body[i]['d']:
            ready[r] = t + body[i]['lat']
        prev_paired = can_pair; t_prev, prev = t, body[i]
        done.add(i); order.append(i)
    return order

def main():
    tries = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
    pred = preds(BODY)
    best = None
    for s in range(tries):
        order = schedule(BODY, random.Random(s), pred)
        sp = span(order, BODY)
        if best is None or sp < best[0]:
            best = (sp, order, s)
    sp, order, s = best
    print('/* mesh_vp_sched.py: modelled steady-state span %d cycles per vertex (seed %d of %d) */' % (sp, s, tries))
    def emit(name, idx):
        lines = ['    %s' % (BODY[i]['asm'] if BODY[i]['asm'].startswith('VP_') else '"%s\\n\\t"' % BODY[i]['asm']) for i in idx]
        print('#define %s \\\n%s' % (name, ' \\\n'.join(lines)))
    emit('VPS_PROLOGUE', [i for i in range(len(BODY)) if BODY[i]['role'] == 'F'])
    emit('VPS_BODY', order)
    emit('VPS_EPILOGUE', [i for i in range(len(BODY)) if BODY[i]['role'] == 'B'])

if __name__ == '__main__':
    main()
