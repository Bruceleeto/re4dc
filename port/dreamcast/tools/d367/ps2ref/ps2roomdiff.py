#!/usr/bin/env python3
"""PS2 vs GC room/enemy code diff (lane ps2code, 2026-10-15).

Compares the PS2 USA stage modules (SNR2 .rel from BIO4DAT.AFS) with the GC decomp: functions are
aligned per module by order and size (anchored on matching exported names), then per room the enemy
calls (sends, alive counts and thresholds, far-delete, freeze/hide) are listed for both sides.

No game data is stored in the repo. Inputs:
  --rel-dir DIR   extracted PS2 .rel files (made by `extract`); default $PS2REF_REL_DIR
  --tree DIR      decomp root (default: this checkout)

Commands
  extract ISO AFS_JSON [SUF...]  write every BIO4DAT.AFS member ending in SUF (default .rel) into --rel-dir
                                 (room data too: `extract ISO AFS_JSON .rel .dat .esl`)
  align [MOD...]                 align GC/PS2 functions; caches <rel-dir>/modalign.json
  ps2only [MOD...]               PS2-only functions and size-ratio outliers per room
  sendmap MOD ROOM               PS2 enemy calls (args from constant tracking, alive thresholds)
  gcsend ROOM                    the GC source lines with enemy calls, by function
  argdiff [MOD...]               send-id / alive-threshold multiset diff per room (heuristic)
  gating                         room functions that branch on PS2 Easy / game_mode / Game_level
  fconst REL GC_CPP...           float constants (|x| >= 1000) only on one side (e.g. em10)
  aev ROOM [NO...]               PS2 vs GC AEV areas (PS2 <rel-dir>/ROOM.dat): differing / one-sided records,
                                 or the named area numbers, with AreaData-ready XZ4 floats
  cns [ROOM...]                  PS2 vs GC per-room pool constants (CNS 0 = enemy pool, 1 objects, ...)
  esl ROOM [ENTRY...]            PS2 vs GC enemy-list rows of a room (emleonNN.esl)
  atcalls MOD LO HI              SceAt* / SceExec / AreaHit calls in a PS2 address range, constant args
  alive MOD LO HI                SceCountEmAlive calls in a PS2 address range with their `< n` test
GC data (aev / cns / esl): --gc-iso PATH (repeatable; default: the decomp's disc 1 + the disc 2 review ROM).

PS2 room data: the .dat directory is (u32 count, offsets at 0x10, 4-byte extensions right after them),
little endian. PS2 AEV records are 0xA0 bytes (GC 0x9C): the include/sce_at.h fields up to 0x5B, then 4
extra bytes, so the payload union is at 0x60 (GC 0x5C).

PS2 notes: pG+32452 Game_level, +32453 game_mode, +32457 = (game_mode >= 4) (0 on Easy);
pG+464 = Room_flg[2] (area flags); pG+32440 room_id. Results: PS2-ENEMY-CODE-DIFF-20261015.md.
"""
import collections
import json
import math
import os
import re
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ps2dis as P  # noqa: E402

TREE = os.path.abspath(os.path.join(HERE, '..', '..', '..', '..', '..'))
REL_DIR = os.environ.get('PS2REF_REL_DIR', '')
MODS = ['st1_0', 'st1_1', 'st1_2', 'st1_3', 'st2_0', 'st2_1', 'st2_2', 'st2_3', 'st2_4',
        'st3_0', 'st3_1', 'st3_2', 'st3_3']


def rel_path(m):
    return os.path.join(REL_DIR, m + '.rel')


# ---------------------------------------------------------------- extraction
def extract(iso, afs_json, sufs=('.rel',)):
    d = json.load(open(afs_json))
    os.makedirs(REL_DIR, exist_ok=True)
    seen = set()
    with open(iso, 'rb') as f:
        for e in d['BIO4DAT']:
            n = e['name']
            if n.endswith(tuple(sufs)) and n not in seen:
                seen.add(n)
                f.seek(e['abs'])
                open(os.path.join(REL_DIR, n), 'wb').write(f.read(e['size']))
    print('%d members -> %s' % (len(seen), REL_DIR))


# ---------------------------------------------------------------- splitting / alignment
def split(r, lo, hi):
    """Split [lo, hi) into functions: named symbols start one; a function ends at the `jr ra` (+ delay
    slot) past which no branch of it reaches."""
    fs = []
    v = lo
    while v < hi:
        while v < hi and r.W(v) == 0 and v not in r.names:
            v += 4
        if v >= hi:
            break
        s = v
        maxb = v
        while v < hi:
            w = r.W(v)
            op = w >> 26
            if op in (4, 5, 6, 7, 0x14, 0x15, 0x16, 0x17, 1) or (op == 0x11 and ((w >> 21) & 31) == 8):
                imm = w & 0xffff
                maxb = max(maxb, v + 4 + (imm - 0x10000 if imm & 0x8000 else imm) * 4)
            if w == 0x03e00008 and v + 8 > maxb:
                v += 8
                break
            v += 4
            if v in r.names and v > s:
                break
        fs.append((s, v))
    return fs


def gc_funcs(mod):
    base = os.path.join(TREE, 'config', 'G4BE08', 'modules', mod)
    out = []
    for line in open(os.path.join(base, 'symbols.txt')):
        m = re.match(r'(\S+) = \.text:0x([0-9A-Fa-f]+); // type:function size:0x([0-9A-Fa-f]+)', line)
        if m:
            out.append((int(m.group(2), 16), int(m.group(3), 16), m.group(1)))
    out.sort()
    tus = []
    cur = None
    for line in open(os.path.join(base, 'splits.txt')):
        m = re.match(r'(\S+\.c(?:pp)?):', line)
        if m:
            cur = m.group(1)
        m = re.match(r'\s+\.text\s+start:0x([0-9A-F]+) end:0x([0-9A-F]+)', line)
        if m:
            tus.append((int(m.group(1), 16), int(m.group(2), 16), cur))

    def tu(a):
        for s, e, n in tus:
            if s <= a < e:
                return n
    return [(a, s, n, tu(a)) for a, s, n in out]


def base_name(n):
    return n.split('__')[0]


def align(gc, ps, k=1.15, gap=2.5):
    """Needleman-Wunsch on log size ratio (MIPS ~1.15x PPC); exported-name matches are anchors."""
    n, m = len(gc), len(ps)
    INF = 1e18
    D = [[INF] * (m + 1) for _ in range(n + 1)]
    B = [[None] * (m + 1) for _ in range(n + 1)]
    D[0][0] = 0
    for i in range(n + 1):
        for j in range(m + 1):
            if D[i][j] >= INF:
                continue
            if i < n and j < m:
                g, p = gc[i], ps[j]
                c = abs(math.log((p[1] + 8) / (g[1] * k + 8)))
                if p[2] and base_name(p[2]) == base_name(g[2]):
                    c -= 3
                elif p[2]:
                    c += 4
                if D[i][j] + c < D[i + 1][j + 1]:
                    D[i + 1][j + 1] = D[i][j] + c
                    B[i + 1][j + 1] = (i, j)
            if i < n and D[i][j] + gap < D[i + 1][j]:
                D[i + 1][j] = D[i][j] + gap
                B[i + 1][j] = (i, j)
            if j < m and D[i][j] + gap < D[i][j + 1]:
                D[i][j + 1] = D[i][j] + gap
                B[i][j + 1] = (i, j)
    i, j = n, m
    pairs = []
    while (i, j) != (0, 0):
        pi, pj = B[i][j]
        pairs.append((gc[pi] if pi < i else None, ps[pj] if pj < j else None))
        i, j = pi, pj
    return pairs[::-1]


def modalign(mods):
    cache = os.path.join(REL_DIR, 'modalign.json')
    out = json.load(open(cache)) if os.path.exists(cache) else {}
    for m in mods:
        gc = gc_funcs(m)
        r = P.Rel(rel_path(m))
        ps = [(s, e - s, r.names.get(s)) for s, e in split(r, r.lo, r.hi)]
        tu_of = {g[0]: g[3] for g in gc}
        rows = []
        last = None
        for g, p in align([(a, s, n) for a, s, n, t in gc], ps):
            tu = tu_of.get(g[0]) if g else None
            if tu:
                last = tu
            rows.append({'gc': g[2] if g else None, 'gcsize': g[1] if g else 0,
                         'ps': p[0] if p else None, 'pssize': p[1] if p else 0,
                         'psname': p[2] if p else None, 'tu': tu or last})
        out[m] = rows
        print('%s gc %d ps2 %d ps2-only %d gc-only %d' % (
            m, len(gc), len(ps), sum(1 for x in rows if x['ps'] is not None and x['gc'] is None),
            sum(1 for x in rows if x['ps'] is None)))
    json.dump(out, open(cache, 'w'))
    return out


def load_align():
    cache = os.path.join(REL_DIR, 'modalign.json')
    if not os.path.exists(cache):
        return modalign(MODS)
    return json.load(open(cache))


def room_rows(A, m, room):
    return [x for x in A[m] if x['ps'] is not None and x['tu'] and x['tu'].endswith('/%s.cpp' % room)]


# ---------------------------------------------------------------- reports
def ps2only(mods):
    A = load_align()
    for m in mods:
        r = P.Rel(rel_path(m))
        for x in A[m]:
            tu = (x['tu'] or '').split('/')[-1]
            if not tu.startswith('r'):
                continue
            only = x['ps'] is not None and x['gc'] is None
            rt = x['pssize'] / max(x['gcsize'], 1) if x['gc'] and x['ps'] is not None else 1
            if not (only or rt > 1.8 or rt < 0.55):
                continue
            nm = x['psname'] or ''
            if nm.startswith(('__', '_$', '_vt', 'reserve__', 'create__t8cManager')) or (only and x['pssize'] <= 0x20):
                continue
            calls, floats, _ = r.summary(x['ps'], x['ps'] + x['pssize'])
            cs = collections.Counter(c.split('__')[0] for c in calls)
            tag = 'PS2-ONLY' if only else 'ratio %.2f (gc %s %x)' % (rt, x['gc'], x['gcsize'])
            print('%s %-10s %6x %5x %-28s %s' % (m, tu, x['ps'], x['pssize'], nm[:28], tag))
            print('      calls:', ' '.join('%s%s' % (k, 'x%d' % v if v > 1 else '') for k, v in cs.items())[:300])
            if floats:
                print('      floats:', sorted(set(floats))[:20])


ENEMY = re.compile(r'^(setEm|EmSetFromList2|EmListSetAlive|SceCountEmAlive\w*|EmFarDelete\w*|destroy|SceDestroyEm|'
                   r'setMove|setTrans|setFindPL|setHp|setCharacter|EmSetEvent|EmListIsAlive|SetPatrol|setReset|'
                   r'SmdSetTrans|R\w+_setEm|R\w+EmSet\w*)$')


def sendmap(m, room):
    A = load_align()
    r = P.Rel(rel_path(m))
    for x in room_rows(A, m, room):
        a, e = x['ps'], x['ps'] + x['pssize']
        lines = []
        regs = {}
        for v in range(a, e, 4):
            w = r.W(v)
            op = w >> 26
            if op in (0x0a, 0x0b) and ((w >> 21) & 31) == 2 and lines and 'SceCountEm' in lines[-1] and '<' not in lines[-1]:
                lines[-1] += ' <%d' % (w & 0xffff)
            if op == 0x24 and (w & 0xffff) in (32452, 32453, 32457):
                lines.append('   %x reads %s' % (v, {32452: 'Game_level', 32453: 'game_mode', 32457: 'notEasy'}[w & 0xffff]))
            if op == 3:
                t = r.jal_target(v)
                b = t.split('__')[0]
                if ENEMY.match(b) or ('__' not in t and re.match(r'^[0-9a-f]+$', t)):
                    rg = dict(regs)
                    r.track(v + 4, rg)
                    args = ','.join(('%d' % (rg[k] if rg[k] < 0x80000000 else rg[k] - 0x100000000)) if k in rg else '?'
                                    for k in (4, 5, 6))
                    lines.append('   %x %s(%s)' % (v, b, args))
            if (w & 0xffff0000) == 0x27bd0000 and (w & 0x8000):
                regs = {}
            r.track(v, regs)
        if lines:
            print('PS2 %x %-30s (GC %s)' % (a, x['psname'] or '', x['gc']))
            print('\n'.join(lines))


def strip_port_blocks(src):
    """Drop port-only `#if ...RE4DC...` blocks (positive conditions) and comments."""
    out = []
    skip = []
    for line in src.split('\n'):
        s = line.strip()
        if s.startswith('#if'):
            skip.append('RE4DC' in s and '!' not in s)
        elif s.startswith('#else') and skip:
            skip[-1] = not skip[-1]
        elif s.startswith('#endif') and skip:
            skip.pop()
            continue
        if any(skip):
            continue
        out.append(line.split('//')[0])
    return '\n'.join(out)


def gc_room_src(room):
    p = os.path.join(TREE, 'src', 'st%s' % room[1], room + '.cpp')
    return strip_port_blocks(open(p, errors='replace').read()) if os.path.exists(p) else None


GC_ENEMY = re.compile(r'(setEm|EmSetFromList2|EmListSetAlive|SceCountEmAlive|EmFarDelete\w*|SceDestroyEm|setMove|'
                      r'setTrans|setFindPL|setHp|setCharacter|EmSetEvent|EmListIsAlive|SetPatrol|setReset|SmdSetTrans|'
                      r'R2\w+_setEm|Game_level|game_mode|\.destroy)\s*[\(>=]')


def gcsend(room):
    src = gc_room_src(room)
    cur = None
    for line in src.split('\n'):
        m = re.match(r'^(?:extern "C" )?(?:static )?(?:inline )?[\w\*:<> ]+?\b(\w+)\s*\([^;]*\)\s*$', line)
        if m and not line.startswith(' '):
            cur = m.group(1)
        if GC_ENEMY.search(line) and line.startswith(' '):
            print('GC %-26s %s' % (cur, line.strip()[:110]))


ARG = {'EmSetFromList2': 4, 'EmListSetAlive': 4, 'GetEmPtrFromList': 4, 'SceCountEmAlive': 4,
       'EmFarDelete': 4, 'EmFarDeleteNoWrap': 4, 'EmListIsAlive': 4}


def argdiff(mods):
    A = load_align()
    for m in mods:
        r = P.Rel(rel_path(m))
        per = collections.defaultdict(collections.Counter)
        for x in A[m]:
            if x['ps'] is None or not x['tu']:
                continue
            room = x['tu'].split('/')[-1].replace('.cpp', '')
            regs = {}
            for v in range(x['ps'], x['ps'] + x['pssize'], 4):
                w = r.W(v)
                if w >> 26 == 3:
                    t = r.jal_target(v)
                    b = t.split('__')[0]
                    reg = 5 if (b == 'setEm' and '7cEmWrap' in t) else (4 if b == 'setEm' else ARG.get(b))
                    if reg:
                        rg = dict(regs)
                        r.track(v + 4, rg)
                        if b == 'SceCountEmAlive':
                            cmp = ''
                            for y in range(v + 8, v + 24, 4):
                                ww = r.W(y)
                                if ww >> 26 in (0x0a, 0x0b) and ((ww >> 21) & 31) == 2:
                                    cmp = '<%d' % (ww & 0xffff)
                                    break
                            sg = [(rg[k] - 0x100000000 if rg[k] >= 0x80000000 else rg[k]) if k in rg else '?' for k in (4, 5)]
                            per[room]['%s:(%s,%s)%s' % (b, sg[0], sg[1], cmp)] += 1
                        else:
                            per[room]['%s:%s' % (b, ('0x%x' % rg[reg]) if reg in rg else '?')] += 1
                if (w & 0xffff0000) == 0x27bd0000 and (w & 0x8000):
                    regs = {}
                r.track(v, regs)
        for room in sorted(per):
            if not room.startswith('r'):
                continue
            src = gc_room_src(room)
            if src is None:
                continue
            gc = collections.Counter()
            for mm in re.finditer(r'(?<![\w])(setEm|EmSetFromList2|EmListSetAlive|GetEmPtrFromList|SceCountEmAlive|'
                                  r'EmListIsAlive)\s*\(\s*([^,)]*)(?:,\s*([^,)]*))?\)?\s*(<=|<|>=|>)?\s*(\d+)?', src):
                b, a = mm.group(1), mm.group(2).strip()
                try:
                    a = int(a, 0)
                except ValueError:
                    pass
                if b == 'SceCountEmAlive':
                    a2 = (mm.group(3) or '?').strip()
                    try:
                        a2 = int(a2, 0)
                    except ValueError:
                        pass
                    cs = ''
                    if mm.group(4) and mm.group(5):
                        n = int(mm.group(5))
                        cs = {'<': '<%d' % n, '<=': '<%d' % (n + 1), '>': '<%d' % (n + 1), '>=': '<%d' % n}[mm.group(4)]
                    gc['%s:(%s,%s)%s' % (b, a, a2, cs)] += 1
                else:
                    gc['%s:%s' % (b, ('0x%x' % a) if isinstance(a, int) else a)] += 1
            onlyp, onlyg = per[room] - gc, gc - per[room]
            if onlyp or onlyg:
                print('%s %s' % (m, room))
                if onlyp:
                    print('   PS2+:', ' '.join(sorted('%s%s' % (k, 'x%d' % v if v > 1 else '') for k, v in onlyp.items())))
                if onlyg:
                    print('   GC+ :', ' '.join(sorted('%s%s' % (k, 'x%d' % v if v > 1 else '') for k, v in onlyg.items())))


def gating():
    A = load_align()
    for m in MODS:
        r = P.Rel(rel_path(m))
        for x in A[m]:
            if x['ps'] is None or not x['tu']:
                continue
            hits = []
            for v in range(x['ps'], x['ps'] + x['pssize'], 4):
                w = r.W(v)
                if w >> 26 == 0x24 and (w & 0xffff) in (32452, 32453, 32457):
                    hits.append('%x:%s' % (v, {32452: 'Game_level', 32453: 'game_mode', 32457: 'notEasy'}[w & 0xffff]))
            if hits:
                print(m, x['tu'].split('/')[-1], '%x' % x['ps'], x['gc'], ' '.join(hits))


def fconst(relp, cpps):
    r = P.Rel(relp)
    ps = collections.defaultdict(list)
    regs = {}
    for v in range(r.lo, r.hi, 4):
        w = r.W(v)
        op = w >> 26
        if op == 0x11 and ((w >> 21) & 31) == 4 and ((w >> 16) & 31) in regs:
            ps[round(P.f32(regs[(w >> 16) & 31]), 3)].append(v)
        if op == 0x31 and ((w >> 21) & 31) in regs:
            imm = w & 0xffff
            a = (regs[(w >> 21) & 31] + (imm - 0x10000 if imm & 0x8000 else imm)) & 0xffffffff
            if 0 < a < len(r.d) - 4:
                ps[round(P.f32(struct.unpack_from('<I', r.d, a)[0]), 3)].append(v)
        if (w & 0xffff0000) == 0x27bd0000 and (w & 0x8000):
            regs = {}
        r.track(v, regs)
    gc = collections.defaultdict(list)
    for p in cpps:
        for i, line in enumerate(open(p, errors='replace')):
            for mm in re.finditer(r'(?<![\w.])(-?\d+\.\d*(?:[eE][-+]?\d+)?|\d+[eE][-+]?\d+)f\b', line.split('//')[0]):
                gc[round(struct.unpack('<f', struct.pack('<f', float(mm.group(1))))[0], 3)].append(i + 1)
    print('PS2-only floats (|x|>=1000):')
    for k in sorted(ps):
        if abs(k) >= 1000 and k not in gc and -k not in gc:
            print('  %g x%d at %s' % (k, len(ps[k]), ' '.join('%x' % a for a in ps[k][:6])))
    print('GC-only floats (|x|>=1000):')
    for k in sorted(gc):
        if abs(k) >= 1000 and k not in ps and -k not in ps:
            print('  %g x%d at lines %s' % (k, len(gc[k]), gc[k][:4]))


# ---------------------------------------------------------------- room data (AEV / CNS / ESL)
GC_ISOS = []
GC_ISO_DEFAULT = [
    '/root/work/re4-dreamcast/orig/G4BE08/re4_debug_disc1.iso',
    '/mnt/c/Game Dev/Emulators/Resident Evil 4 - 2004.11.25 Disc 2 (Resident Evil 4 Review Rom (GC) '
    'No Reviews Until March 05 Issues).gcm',
]
CNS_NAMES = ['em', 'obj', 'esp', 'espgen', 'ctrl', 'light', 'model', 'parts', 'prim', 'c9', 'coll10', 'coll11']
CNS_DEFAULT = [60, 200, 1024, 256, 10, 100, 1300, 300, 0xA0000, 10, 30, 30]   # src/game/cons.cpp
_gc_cache = []


def gc_isos():
    if not _gc_cache:
        sys.path.insert(0, os.path.join(TREE, 'port', 'dreamcast', 'tools'))
        from assetpipe.rooms import GcIso
        for p in GC_ISOS or GC_ISO_DEFAULT:
            if os.path.exists(p):
                _gc_cache.append(GcIso(p))
    return _gc_cache


def gc_room_arc(room):
    isos = gc_isos()   # puts port/dreamcast/tools on sys.path
    import room_smd
    for iso in isos:
        for r, k in iso.rooms():
            if r == room:
                return room_smd.decode_das(iso.read(k))
    return None


def gc_file(name):
    for iso in gc_isos():
        k = next((x for x in iso.files if x.lower().split('/')[-1] == name.lower()), None)
        if k:
            return iso.read(k)
    return None


def ps2_file(name):
    p = os.path.join(REL_DIR, name)
    return open(p, 'rb').read() if os.path.exists(p) else None


def arc_members(d, e):
    n = struct.unpack_from(e + 'I', d, 0)[0]
    offs = struct.unpack_from(e + '%dI' % n, d, 0x10)
    e0 = 0x10 + n * 4
    return [(d[e0 + 4 * i:e0 + 4 * i + 3].decode('latin-1'), offs[i]) for i in range(n)]


def aev_records(d, e, stride, uoff):
    out = {}
    for ext, o in arc_members(d, e):
        if ext != 'AEV':
            continue
        num = struct.unpack_from(e + 'H', d, o + 6)[0]
        for i in range(num):
            w = o + 0x10 + i * stride
            f = struct.unpack_from(e + '11f', d, w + 8)
            out[d[w + 0x36]] = {
                'type': d[w + 0x35], 'flag': d[w + 0x34], 'trigger': d[w + 0x38], 'checkFlag': d[w + 0x37],
                'checkType': d[w + 0x39], 'area': (d[w + 4], d[w + 5]),
                'xz4': (f[0], f[1], f[2], [(f[3 + 2 * k], f[4 + 2 * k]) for k in range(4)]),
                'payload': d[w + uoff:w + uoff + 8].hex()}
    return out


def aev(room, nos):
    p = ps2_file(room + '.dat')
    g = gc_room_arc(room)
    A = aev_records(p, '<', 0xA0, 0x60) if p else {}
    B = aev_records(g, '>', 0x9C, 0x5C) if g else {}

    def key(r):
        if r is None:
            return None
        fl, h, rad, q = r['xz4']
        k = dict(r)
        k.pop('payload')
        k['xz4'] = (round(fl), round(h), [(round(x), round(z)) for x, z in q])
        return k
    for no in sorted(set(A) | set(B)):
        if nos and no not in nos:
            continue
        a, b = A.get(no), B.get(no)
        if not nos and key(a) == key(b):
            continue
        print('area 0x%02x' % no)
        for tag, r in (('PS2', a), ('GC ', b)):
            if r is None:
                print('   %s -' % tag)
                continue
            fl, h, rad, q = r['xz4']
            print('   %s type %d trigger 0x%x checkType %d checkFlag %d area(be %d, type %d) payload %s' % (
                tag, r['type'], r['trigger'], r['checkType'], r['checkFlag'], r['area'][0], r['area'][1], r['payload']))
            print('       {%rf, %rf, %rf, {%s}}' % (fl, h, rad, ', '.join('{%rf, %rf}' % (x, z) for x, z in q)))


def cns_values(d, e):
    for ext, o in arc_members(d, e):
        if ext == 'CNS':
            num = struct.unpack_from(e + 'I', d, o)[0]
            nb = (num >> 5) + 1
            bits = struct.unpack_from(e + '%dI' % nb, d, o + 4)
            vals = struct.unpack_from(e + '%dI' % num, d, o + 4 + 4 * nb)
            return [vals[i] if (bits[i >> 5] >> (i & 31)) & 1 else None for i in range(num)]
    return []


def cns(rooms):
    if not rooms:
        rooms = sorted(f[:-4] for f in os.listdir(REL_DIR) if re.match(r'r[123][0-9a-f]{2}\.dat$', f))
    same = 0
    for room in rooms:
        p, g = ps2_file(room + '.dat'), gc_room_arc(room)
        if p is None or g is None:
            print('%s: %s' % (room, 'no PS2 .dat' if p is None else 'not on the GC discs'))
            continue
        a, b = cns_values(p, '<'), cns_values(g, '>')
        diffs = []
        for i in range(max(len(a), len(b), len(CNS_DEFAULT))):
            x = a[i] if i < len(a) and a[i] is not None else (CNS_DEFAULT[i] if i < len(CNS_DEFAULT) else None)
            y = b[i] if i < len(b) and b[i] is not None else (CNS_DEFAULT[i] if i < len(CNS_DEFAULT) else None)
            if x != y:
                diffs.append('%s GC %s -> PS2 %s' % (CNS_NAMES[i] if i < len(CNS_NAMES) else i, y, x))
        if diffs:
            print('%s: %s' % (room, '; '.join(diffs)))
        else:
            same += 1
    print('%d rooms with identical effective constants' % same)


def esl_rows(d, e):
    out = {}
    for n in range(len(d) // 0x20):
        w = n * 0x20
        out[n] = {'be': d[w], 'id': d[w + 1], 'type': d[w + 2], 'set': d[w + 3],
                  'flag': struct.unpack_from(e + 'I', d, w + 4)[0], 'hp': struct.unpack_from(e + 'H', d, w + 8)[0],
                  'pos': struct.unpack_from(e + '3h', d, w + 0xC), 'room': struct.unpack_from(e + 'H', d, w + 0x18)[0]}
    return out


def esl(room, entries):
    rid = int(room[1:], 16)
    for k in range(10):
        nm = 'emleon%02d.esl' % k
        p, g = ps2_file(nm), gc_file(nm)
        if not p or not g:
            continue
        A, B = esl_rows(p, '<'), esl_rows(g, '>')
        for n in sorted(set(A) | set(B)):
            a, b = A.get(n), B.get(n)
            if (a or {}).get('room') != rid and (b or {}).get('room') != rid:
                continue
            if entries and n not in entries:
                continue
            same = bool(a and b) and all(a[x] == b[x] for x in a if x != 'pos') and \
                all(abs(u - v) <= 2 for u, v in zip(a['pos'], b['pos']))
            print('%s 0x%02x PS2 %s' % (nm, n, a))
            if not same:
                print('%s 0x%02x GC  %s   <- differs' % (nm, n, b))


def atcalls(m, lo, hi):
    r = P.Rel(rel_path(m))
    regs = {}
    for v in range(lo, hi, 4):
        w = r.W(v)
        if w >> 26 == 3:
            t = r.jal_target(v) or ''
            if t.startswith(('SceAt', 'AreaHit', 'SceExec')):
                rg = dict(regs)
                r.track(v + 4, rg)
                fs = r.func_start(v)
                print('%x in %x %s: %s(%s)' % (v, fs or 0, r.names.get(fs, ''), t.split('__')[0],
                                                ','.join(hex(rg[k]) if k in rg else '?' for k in (4, 5, 6, 7))))
        if (w & 0xffff0000) == 0x27bd0000 and (w & 0x8000):
            regs = {}
        r.track(v, regs)


def alive(m, lo, hi):
    r = P.Rel(rel_path(m))
    for v in range(lo, hi, 4):
        if r.W(v) >> 26 == 3 and (r.jal_target(v) or '').startswith('SceCountEmAlive'):
            cmp = ''
            for y in range(v + 8, v + 28, 4):
                w = r.W(y)
                if w >> 26 in (0x0a, 0x0b):
                    cmp = '< %d' % (w & 0xffff)
                    break
            fs = r.func_start(v)
            print('%x in %x %s %s' % (v, fs or 0, r.names.get(fs, ''), cmp))


def main(argv):
    global REL_DIR, TREE
    args = list(argv[1:])
    while args and args[0].startswith('--'):
        if args[0] == '--rel-dir':
            REL_DIR = args[1]
        elif args[0] == '--tree':
            TREE = args[1]
        elif args[0] == '--gc-iso':
            GC_ISOS.append(args[1])
        args = args[2:]
    if not args:
        print(__doc__)
        return 1
    cmd, rest = args[0], args[1:]
    if not REL_DIR and cmd != 'fconst':
        raise SystemExit('set --rel-dir or PS2REF_REL_DIR')
    if cmd == 'extract':
        extract(rest[0], rest[1], rest[2:] or ('.rel',))
    elif cmd == 'align':
        modalign(rest or MODS)
    elif cmd == 'ps2only':
        ps2only(rest or MODS)
    elif cmd == 'sendmap':
        sendmap(rest[0], rest[1])
    elif cmd == 'gcsend':
        gcsend(rest[0])
    elif cmd == 'argdiff':
        argdiff(rest or MODS)
    elif cmd == 'gating':
        gating()
    elif cmd == 'fconst':
        fconst(rest[0], rest[1:])
    elif cmd == 'aev':
        aev(rest[0], [int(x, 0) for x in rest[1:]])
    elif cmd == 'cns':
        cns(rest)
    elif cmd == 'esl':
        esl(rest[0], [int(x, 16) for x in rest[1:]])
    elif cmd == 'atcalls':
        atcalls(rest[0], int(rest[1], 16), int(rest[2], 16))
    elif cmd == 'alive':
        alive(rest[0], int(rest[1], 16), int(rest[2], 16))
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
