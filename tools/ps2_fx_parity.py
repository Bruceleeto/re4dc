#!/usr/bin/env python3
"""ps2_fx_parity.py: GameCube vs PS2 room effect parity for every stage-1 room in one pass.

Reads the extracted room EFF files (worldfx cache: rNNN.gc.effN big-endian, rNNN.ps2.effN little-endian), matches
every GameCube record to its PS2 counterpart and classifies it:
  same     matched, every render field equal (texture, blend, colour, size, range, count, fades, life)
  changed  matched, a render field differs (haze rows are hand-qualified overrides in esp_sub.cpp kPs2Haze)
  cut      no PS2 counterpart: the PS2 release deleted it
and every unmatched PS2 record as added. For each cut it derives the draw-time selector the runtime can test
(esp_sub.cpp Ps2fxGenCut, PS2_FX_GEN=1) and checks that no kept GameCube record of the room shares it; a cut
whose selector is not unique, or whose effect id draws through its own trans (not EspCommonTrans, apart from
the Esp0a streak copies), or which lives in a second EFF (another owner), is reported "not representable".

Outputs: --json (per record), --md (per-room parity table), --inc (C table for esp_sub.cpp, generated rows only;
hand-tuned rows stay as overrides there). Render-only by construction: no record is added, no generator,
Rnd() draw or pool slot is touched; the runtime only declines to draw a matching sprite.
"""
import argparse
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import audit_ps2_fx_recipes as A  # noqa: E402

ROOMS = tuple('r100 r101 r102 r103 r104 r105 r106 r107 r108 r109 r10a r10b r10c r10d r10e r10f '
              'r111 r112 r113 r117 r118 r119 r11a r11b r11c r11d r11e r11f'.split())
# esp.cpp EspFuncTblSet: ids drawn by EspCommonTrans (Ps2fxClass sees the source sprite itself).
COMMON_IDS = {0x00, 0x05, 0x06, 0x07, 0x0B, 0x0D, 0x10, 0x13, 0x14, 0x15, 0x17, 0x1A, 0x1B, 0x40, 0x41, 0x42, 0x43,
              0x44, 0x48, 0x49, 0x4B, 0x4F}
# an unmatched GC record with an unmatched PS2 record of the same EFF, id and texture this close was moved, not cut
MOVED_MM = 3000
RENDER_FIELDS = ('tex', 'blend', 'type', 'rgba', 'size_x', 'size_y', 'size_plus', 'range', 'count_per_emission',
                 'del_far', 'del_near', 'life_max', 'work8')


def load(cache, room, side):
    endian = '>' if side == 'gc' else '<'
    rows = []
    for path in sorted(cache.glob('%s.%s.eff[0-9]' % (room, side))):
        eff = int(path.name.rsplit('eff', 1)[1])
        for r in A.decode_eff(path.read_bytes(), endian):
            rows.append(dict(r, eff=eff))
    return rows


def dist(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a['position'], b['position'])))


def close(a, b, rel=1e-4):
    if isinstance(a, list):
        return len(a) == len(b) and all(close(x, y, rel) for x, y in zip(a, b))
    if isinstance(a, float) or isinstance(b, float):
        return abs(a - b) <= rel * max(1.0, abs(a), abs(b))
    return a == b


def match(gc, ps2):
    """Greedy: same EFF, table and effect id; texture equal (haze may swap 1e/1f); nearest position."""
    pairs, used = {}, set()
    order = sorted(range(len(gc)), key=lambda i: (gc[i]['id'] != 0x15, i))
    for i in order:
        g = gc[i]
        best = None
        for j, p in enumerate(ps2):
            if j in used or p['eff'] != g['eff'] or p['id'] != g['id']:
                continue
            if p['tex'] != g['tex'] and not (g['id'] == 0x15 and {g['tex'], p['tex']} <= {0x1E, 0x1F}):
                continue
            d = dist(g, p)
            if g['id'] != 0x15 and d > 50.0:
                continue
            score = (p['table'] != g['table'], p['area'] != g['area'], d, abs(p['range'] - g['range']))
            if best is None or score < best[0]:
                best = (score, j)
        if best:
            pairs[i] = best[1]
            used.add(best[1])
    return pairs, used


def owner_of(r):
    return 0xD0 if r['table'] == 'sst' else 0x01


def selector(r):
    """What the runtime can test on a drawn cEsp (esp_sub.cpp Ps2fxGenCut)."""
    if r['id'] == 0x0A:
        # Esp0a permanent copies: id 0, record texture, Del x 10; SST copies life 0, EST (Work8[0] = 1) life 1.
        return ('copy', owner_of(r), 0, r['tex'], None, r['del_far'] * 10, r['del_near'] * 10,
                None, 1 if r['work8'][0] == 1 else 0)
    if r['id'] == 0x48:
        return ('sheet', owner_of(r), 0x48, r['tex'], None, None, None, None, None)
    if r['id'] == 0x15:
        return ('haze', owner_of(r), 0x15, r['tex'], None, None, None, tuple(r['rgba'][:3]), None)
    return ('sprite', owner_of(r), r['id'], r['tex'], r['blend'], r['del_far'], r['del_near'],
            tuple(r['rgba'][:3]), r['life_max'])


def selector_hits(sel, r):
    """Would a sprite of record r satisfy selector sel?"""
    return selector(r)[:9] == sel[:9] if sel[0] != 'sheet' else (r['id'] == 0x48 and owner_of(r) == sel[1] and
                                                                 r['tex'] == sel[3])


def representable(r, kept):
    if r['eff'] != 0:
        return False, 'second EFF (owner set by its caller)'
    if r['id'] not in COMMON_IDS and r['id'] != 0x0A:
        return False, 'id %02x has its own trans' % r['id']
    if r['id'] == 0x0A and (r['work8'][0] not in (0, 1) or r['work8'][2] != 0):
        return False, 'Esp0a type %d (not a static copy)' % r['work8'][0]
    sel = selector(r)
    clash = [k for k in kept if k['eff'] == 0 and selector_hits(sel, k)]
    if r['id'] == 0x0A:   # a kept plain id-0 record with the copy's look would also match
        clash += [k for k in kept if k['eff'] == 0 and k['id'] == 0 and owner_of(k) == sel[1] and k['tex'] == sel[3]
                  and k['del_far'] * 10 == sel[5] and k['del_near'] * 10 == sel[6]]
    if clash:
        return False, 'selector shared with %d kept record(s)' % len(clash)
    return True, ''


def room_parity(cache, room):
    gc, ps2 = load(cache, room, 'gc'), load(cache, room, 'ps2')
    pairs, used = match(gc, ps2)
    # second pass: same EFF, same id, position within 50 mm, texture differs (PS2 re-textured it)
    for i, g in enumerate(gc):
        if i in pairs:
            continue
        best = min(((dist(g, p), j) for j, p in enumerate(ps2) if j not in used and p['eff'] == g['eff'] and
                    p['id'] == g['id'] and dist(g, p) <= 50.0 and any(g['position'])), default=None)
        if best:
            pairs[i] = best[1]
            used.add(best[1])
    rows, cand = [], []
    stat = Counter()
    for i, g in enumerate(gc):
        if i in pairs:
            p = ps2[pairs[i]]
            diff = [f for f in RENDER_FIELDS if not close(g[f], p[f])]
            kind = 'changed' if diff else 'same'
            stat[kind] += 1
            if diff and g['id'] != 0x15:
                stat['changed_not_representable'] += 1
            rows.append({'gc': (g['eff'], g['table'], g['no'], g['index']), 'id': g['id'], 'tex': g['tex'],
                         'class': kind, 'ps2': (p['eff'], p['table'], p['no'], p['index']), 'fields': diff})
            continue
        # unmatched: is it a deletion the runtime can express?
        why = ''
        ps2_eff = [p for p in ps2 if p['eff'] == g['eff']]
        if g['eff'] != 0:
            why = 'second EFF (owner set by its caller)'
        elif g['id'] == 0x48:
            if any(p['id'] == 0x48 and p['tex'] == g['tex'] for p in ps2_eff):
                why = 'PS2 keeps Esp48 sheets with this texture'
        elif g['id'] == 0x0A:
            if g['work8'][0] not in (0, 1) or g['work8'][2] != 0:
                why = 'Esp0a type %d (not a static copy)' % g['work8'][0]
            elif any(p['id'] == 0x0A and A.streak_signature(p) == A.streak_signature(g) for p in ps2_eff):
                why = 'PS2 keeps an Esp0a with this signature'
        elif g['id'] == 0x15:
            if any(p['id'] == 0x15 for p in ps2_eff):
                why = 'PS2 has camera haze here (hand row, kPs2Haze)'
        elif g['id'] not in COMMON_IDS:
            why = 'id %02x has its own trans' % g['id']
        elif any(g['position']):
            near = [p for p in ps2_eff if dist(g, p) <= 100.0]
            moved = [p for j, p in enumerate(ps2) if j not in used and p['eff'] == g['eff'] and p['id'] == g['id']
                     and p['tex'] == g['tex'] and dist(g, p) <= MOVED_MM]
            if near:
                why = 'PS2 has %d record(s) within 100 mm (replaced, not deleted)' % len(near)
            elif moved:
                why = 'PS2 has the same effect within %d m (moved / re-authored, not deleted)' % (MOVED_MM // 1000)
        elif any(p['id'] == g['id'] for p in ps2_eff):
            why = 'unplaced (parent-relative) and PS2 keeps effect id %02x' % g['id']
        cand.append((i, g, why))
    # selector uniqueness against every GameCube record of the room that is not a representable cut
    ok_idx = {i for i, g, why in cand if not why}
    changed = True
    while changed:
        changed = False
        others = [gc[k] for k in range(len(gc)) if k not in ok_idx]
        for i in sorted(ok_idx):
            g = gc[i]
            sel = selector(g)
            clash = [k for k in others if k['eff'] == 0 and selector_hits(sel, k)]
            if g['id'] == 0x0A:
                clash += [k for k in others if k['eff'] == 0 and k['id'] == 0 and owner_of(k) == sel[1] and
                          k['tex'] == sel[3] and k['del_far'] * 10 == sel[5] and k['del_near'] * 10 == sel[6]]
            if clash:
                ok_idx.discard(i)
                changed = True
                break
    cuts = []
    for i, g, why in cand:
        ok = i in ok_idx
        if not why and not ok:
            why = 'selector shared with a kept record'
        stat['cut'] += 1
        stat['cut_ok' if ok else 'cut_not_representable'] += 1
        rows.append({'gc': (g['eff'], g['table'], g['no'], g['index']), 'id': g['id'], 'tex': g['tex'],
                     'class': 'cut', 'representable': ok, 'why': why})
        if ok:
            cuts.append((selector(g), g))
    added = [p for j, p in enumerate(ps2) if j not in used]
    stat['added'] = len(added)
    for p in added:
        rows.append({'ps2': (p['eff'], p['table'], p['no'], p['index']), 'id': p['id'], 'tex': p['tex'],
                     'class': 'added'})
    uniq = {}
    for sel, g in cuts:
        uniq.setdefault(sel, []).append(g)
    return {'room': room, 'gc_records': len(gc), 'ps2_records': len(ps2), 'stat': dict(stat), 'rows': rows,
            'cuts': [{'selector': list(s), 'records': len(v), 'ids': sorted({'%02x' % g['id'] for g in v})}
                     for s, v in uniq.items()]}


KIND = {'sprite': 0, 'copy': 1, 'sheet': 2, 'haze': 3}


def emit_inc(results, path):
    out = ['// GENERATED by tools/ps2_fx_parity.py from the worldfx cache GC / PS2 rNNN EFF records: do not edit.',
           '// One row per draw-time selector of a GameCube record the PS2 release deleted (eff 0 only; selector unique',
           '// against the room\'s kept records). kind 0 sprite (id, tex, blend, del, rgb, life), 1 Esp0a copy (id 0,',
           '// tex, del x10, life), 2 Esp48 sheet (tex), 3 camera haze (Esp15: tex, rgb). 0xffff / 0xff = not tested.',
           'static const Ps2fxGenCutRow kPs2GenCut[] = {']
    n = 0
    for res in results:
        room = int(res['room'][1:], 16)
        for c in res['cuts']:
            kind, owner, eid, tex, blend, dfar, dnear, rgb, life = c['selector']
            rgb = rgb or (0, 0, 0)
            out.append('    {0x%03x, %d, 0x%02x, 0x%02x, 0x%02x, 0x%02x, %d, %d, %d, %d, %d, %d, %d}, // %d record(s)' % (
                room, KIND[kind], owner, eid, tex, 0xFF if blend is None else blend,
                0xFFFF if dfar is None else dfar, 0xFFFF if dnear is None else dnear,
                rgb[0], rgb[1], rgb[2], 1 if c['selector'][7] is not None else 0,
                0xFFFF if life is None else life, c['records']))
            n += 1
    out.append('};')
    out.append('#define PS2FX_GEN_CUTS %d' % n)
    path.write_text('\n'.join(out) + '\n')
    return n


def emit_md(results, path):
    lines = ['# PS2 effect parity, stage-1 rooms (tools/ps2_fx_parity.py)', '',
             'GC records matched to PS2 records by EFF, table, effect id, texture and position. same = every render '
             'field equal; changed = matched, a field differs (camera haze: hand-qualified rows, kPs2Haze); cut = no '
             'PS2 counterpart; added = PS2-only. "cut, runtime row" = the runtime (PS2_FX_GEN=1) can decline to draw it; '
             '"not representable" = no unique render-side selector (own trans, second EFF, shared selector).', '',
             '| Room | GC | PS2 | same | changed | cut | cut, runtime row | cut, not representable | changed, not representable | added |',
             '|---|---|---|---|---|---|---|---|---|---|']
    tot = Counter()
    for r in results:
        s = r['stat']
        vals = [s.get(k, 0) for k in ('same', 'changed', 'cut', 'cut_ok', 'cut_not_representable',
                                      'changed_not_representable', 'added')]
        tot.update({'gc': r['gc_records'], 'ps2': r['ps2_records']})
        tot.update(dict(zip(('same', 'changed', 'cut', 'cut_ok', 'cut_nr', 'chg_nr', 'added'), vals)))
        lines.append('| %s | %d | %d | %s |' % (r['room'], r['gc_records'], r['ps2_records'],
                                                ' | '.join(str(v) for v in vals)))
    lines.append('| **all** | %d | %d | %d | %d | %d | %d | %d | %d | %d |' % tuple(
        tot[k] for k in ('gc', 'ps2', 'same', 'changed', 'cut', 'cut_ok', 'cut_nr', 'chg_nr', 'added')))
    why = Counter()
    for r in results:
        for row in r['rows']:
            if row['class'] == 'cut' and not row['representable']:
                w = re.sub(r'PS2 has \d+ record', 'PS2 has N record', row['why'])
                why['effect id with its own trans (not EspCommonTrans)' if 'own trans' in w else
                    re.sub(r'keeps effect id ..', 'keeps that effect id', w)] += 1
    lines += ['', '## Cuts not representable render-side, by reason (all rooms)', '', '| Reason | Records |', '|---|---|']
    lines += ['| %s | %d |' % (k, v) for k, v in why.most_common()]
    lines += ['', 'Changed records (matched, a render field differs) are not restyled by PS2_FX_GEN: a generic restyle '
              'of colour / size / fades would rewrite effect state, so only the hand rows (camera haze kPs2Haze, r104 '
              'statics) do it. Added PS2 records are never drawn (user decision: no wholesale PS2 EFF); the one '
              'hand-qualified addition is PS2_FX_ADDITIONS (r118 area 6, r11c haze).']
    path.write_text('\n'.join(lines) + '\n')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cache', type=Path, default=Path('/root/probe/worldfx-cache'))
    ap.add_argument('--json', type=Path)
    ap.add_argument('--md', type=Path)
    ap.add_argument('--inc', type=Path)
    ap.add_argument('--rooms', default=','.join(ROOMS))
    a = ap.parse_args()
    results = [room_parity(a.cache, r) for r in a.rooms.split(',')]
    if a.json:
        a.json.write_text(json.dumps(results, indent=1, default=list))
    if a.md:
        emit_md(results, a.md)
    if a.inc:
        print('runtime rows', emit_inc(results, a.inc))
    for r in results:
        print(r['room'], r['gc_records'], r['ps2_records'], dict(sorted(r['stat'].items())))


if __name__ == '__main__':
    main()
