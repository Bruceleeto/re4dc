#!/usr/bin/env python3
"""Stage-1 character inventory (lane ps2cast): which characters the required stage-1 rooms need, which the
external cast (cast-20260925, in the play build through cast_bundle.py) covers, and which a PS2 conversion
can supply.

Per room (route order, R4_FIRST_STAGE_GAP_AUDIT.md "Full stage-1 route"): the assets.sh discover data (the
room's enemy list entries with model type, script loads / spawns, event actors). Characters:
- Ganado modules (src/emXX/emXX_set.cpp, the shared cEm10 library): one appearance per (archive, model
  type) = the EmXXSet case's TPL / body / head / default hands arcs (unknown types fall to the default case,
  as the source does).
- other enemy modules: the archive (its models are traced when that character is converted);
- event actors: the evd's actor groups (pl00 Leon, pl01.., emXX, ev/obm/et objects).
Coverage: a Ganado appearance is covered when its GC body and head signatures (counts + vertex FNV, what
coarse_ganado_cast.cpp matches) are among the cast's Ganado signatures; animals by the cast's named packs;
Leon by the cl lane's leon4k. PS2: the archive exists in BIO4DAT.AFS; for Ganado appearances the PS2 entries at
the same arcs are BINs whose bone tables equal the GC's (the converter's binding precondition).

usage: ps2_cast_inventory.py <out dir> [--ps2-iso P] [--cast DIR]   (WSL; pure Python)
"""
import argparse, json, re, struct, sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path[:0] = [str(HERE), str(REPO / 'tools')]
import ps2_bin as pb  # noqa: E402
import convert_character as cc  # noqa: E402
import drs  # noqa: E402
from motion import modelbin  # noqa: E402
from assetpipe.config import Config  # noqa: E402
from assetpipe.discover import discover, Tables  # noqa: E402
from assetpipe.rooms import GcIso  # noqa: E402

PS2_ISO = '/mnt/c/Game Dev/Emulators/re4_helpers/Resident Evil 4 (USA)/Resident Evil 4 (USA).iso'
CAST = '/mnt/c/Game Dev/Emulators/re4-assets-private/cast-20260925'
INPUTS = Path('/root/probe/lanes/ps2cast/inputs')
# route order; (alt) = one of a pair is needed
ROUTE = [('1-1', 'r120'), ('1-1', 'r100'), ('1-1', 'r101'), ('1-1', 'r103'), ('1-1', 'r106'), ('1-2', 'r104'),
         ('1-2', 'r107'), ('1-2', 'r105'), ('1-3', 'r101'), ('1-3', 'r102'), ('1-3', 'r108'), ('1-3', 'r109'),
         ('1-3', 'r10a'), ('1-3', 'r10b'), ('2-1', 'r11b'), ('2-1', 'r11a (alt r10c+r10e)'), ('2-1', 'r10c (alt)'),
         ('2-1', 'r10e (alt)'), ('2-1', 'r119'), ('2-1', 'r118'), ('2-1', 'r117'), ('2-2', 'r112'), ('2-2', 'r111'),
         ('2-2', 'r113'), ('2-2', 'r11c'), ('2-3', 'r11d (alt r11e)'), ('2-3', 'r11e (alt)'), ('2-3', 'r10f'),
         ('2-3', 'r11f')]
NAMES = {  # from the modules' own source headers (src/emXX/*.cpp)
    'em10': 'Ganado (em10 set)', 'em11': 'Ganado (em11 set)', 'em12': 'Ganado (em12 set, r100/r103 villagers)',
    'em13': 'Ganado (em13 set)', 'em15': 'Ganado (em15 set, r101 village)', 'em16': 'Ganado (em16 set)',
    'em17': 'Ganado (em17 set)', 'em18': 'merchant', 'em21': 'dog (cast: dog)', 'em22': 'dog (parasite dog)',
    'em23': 'crow', 'em24': 'small box / coil enemy', 'em26': 'cow', 'em27': 'lake fish', 'em28': 'chicken',
    'em29': 'bats', 'em2a': 'traps (bear trap, tripwire bombs)', 'em2b': 'giant', 'em2e': 'small crawler',
    'em2f': 'lake monster (boss)', 'em30': 'large stationary parasite enemy', 'em34': 'em34/em37/em33 large biter',
    'em35': 'beam hall boss', 'em3b': 'truck / mine carts', 'pl0f': 'lake boat (Del Lago fight)',
    'pl11': 'Ashley (partner archive pl11)', 'pl14': 'Luis (partner, cabin fight r11c)',
    'pl00': 'Leon', 'pl01': 'pl01 (event actor)', 'pl02': 'pl02 (event actor)', 'pl04': 'pl04 (event actor)',
    'pl07': 'pl07 (event actor)', 'pl82': 'pl82 (event actor)'}
CAST_ANIMALS = {'em21': 'dog-00/01', 'em23': 'crow-folded/spread', 'em26': 'cow-00/01', 'em28': 'chicken-00/01'}


def set_table(archive):
    """EmXXSet: {type: dict(tpl, body, head, rhand, lhand)} and the default type (src/emXX/emXX_set.cpp)."""
    p = REPO / f'src/{archive}/{archive}_set.cpp'
    if not p.exists():
        return None, None
    s = p.read_text()
    body = s[re.search(r'void %sSet\(cEm10\* em\)\s*\{' % archive.capitalize(), s).start():]
    body = body[:body.index('\nvoid ', 10)] if '\nvoid ' in body[10:] else body
    out, default = {}, None
    for m in re.finditer(r'((?:\s*(?:case\s+(\d+)|default)\s*:)+)(.*?)break;', body, re.S):
        labels, block = m.group(1), m.group(3)
        mot = {int(k): int(v, 16) for k, v in re.findall(r'w->mot\[(\d+)\] = ARC\(0x([0-9A-Fa-f]+)\)', block)}
        row = dict(tpl=mot.get(0), body=mot.get(1), head=mot.get(2), rhand=mot.get(6), lhand=mot.get(11))
        for t in re.findall(r'case\s+(\d+)', labels):
            out[int(t)] = row
        if 'default' in labels:
            default = row
    return out, default


def gc_sig(d):
    vo = struct.unpack_from('>I', d, 0x30)[0]
    raw = b''.join(struct.pack('<4h', *struct.unpack_from('>4h', d, vo + k)) for k in range(0, 64, 8))
    fnv = 2166136261
    for x in raw:
        fnv = ((fnv ^ x) * 16777619) & 0xffffffff
    return (struct.unpack_from('>H', d, 0x38)[0], struct.unpack_from('>H', d, 0x3a)[0], d[0x18], f'{fnv:08x}')


def gc_tris(d):
    try:
        return len(cc.parse_geometry(d)[9]) // 3
    except Exception:
        return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('out', type=Path); ap.add_argument('--ps2-iso', default=PS2_ISO); ap.add_argument('--cast', default=CAST)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    cfg = Config()
    gciso = GcIso(cfg.path('gc_iso'))
    afs = pb.afs_index(a.ps2_iso)
    cast = Path(a.cast)
    cast_sigs = {}
    for d in sorted(cast.glob('ganado-*')):
        if (d / 'source-bindings.json').exists():
            for b in json.loads((d / 'source-bindings.json').read_text()):
                cast_sigs[(b['positions'], b['normals'], b['palettes'], b['source_vertex_fnv64_le'])] = (d.name, b['role'])
    gcarc, ps2arc = {}, {}

    def gc_archive(name):
        if name not in gcarc:
            gcarc[name] = drs.Drs(gciso.read(f'em/{name}.drs'))
        return gcarc[name]

    def ps2_archive(name):
        if name not in ps2arc:
            p = INPUTS / f'{name}.dat'
            if not p.exists() and f'{name}.dat' in afs:
                INPUTS.mkdir(parents=True, exist_ok=True)
                p.write_bytes(pb.afs_read(a.ps2_iso, f'{name}.dat', afs))
            ps2arc[name] = {i: (t, b) for i, t, b in pb.dat_entries(p.read_bytes())} if p.exists() else None
        return ps2arc[name]

    rooms, chars = [], {}
    tables = Tables(REPO)
    for chapter, label in ROUTE:
        room = label.split()[0]
        res = discover(cfg, room)
        need = defaultdict(set)

        def arcname(eid):  # the enemy id's archive (read.cpp EmFileTbl -> dvd.cpp FileTbl): 0x03 -> pl11 etc.
            e = tables.enemy(eid)
            return Path(e['archive']).stem if e else 'em%02x' % eid
        for e in res['entries']:
            need[(arcname(e['id']), e['type'])].add('entry' if e['alive'] else 'enabled-later')
        by_no = {e['no']: e for e in res['entries']}
        for no in res['script']['list_spawns']:
            if no in by_no:
                need[(arcname(by_no[no]['id']), by_no[no]['type'])].add('script-spawn')
        for eid in res['script']['loads']:
            ids = {k for k in need if k[0] == arcname(eid)}
            if not ids:
                need[(arcname(eid), None)].add('script-load')
            for k in ids:
                need[k].add('script-load')
        ev = defaultdict(int)
        for e in res['events']:
            for g, n in (e.get('actor_groups') or {}).items():
                if g.startswith(('pl', 'em')):
                    ev[g] = max(ev[g], n)
        row = dict(chapter=chapter, room=label, characters=[], events={k: v for k, v in sorted(ev.items())})
        for (arc, typ), why in sorted(need.items(), key=lambda x: (x[0][0], -1 if x[0][1] is None else x[0][1])):
            key = arc  # non-Ganado modules: one row per archive (its model types listed)
            tab, default = set_table(arc)
            if tab is not None and typ is not None:
                app = tab.get(typ, default)
                if app is None:  # no default label: the source leaves the work as set before; take the first case
                    print(f'note: {arc} type {typ:#x} not in {arc.capitalize()}Set and no default: first case used', file=sys.stderr)
                    app = tab[min(tab)]
                key = f'{arc}:{app["body"]:#x}/{app["head"]:#x}/{app["tpl"]:#x}'
            row['characters'].append(dict(key=key, archive=arc, type=typ, why=sorted(why)))
            c = chars.setdefault(key, dict(key=key, archive=arc, name=NAMES.get(arc, arc), types=set(), rooms=[]))
            if typ is not None:
                c['types'].add(typ)
            if label not in c['rooms']:
                c['rooms'].append(label)
            if tab is not None and typ is not None:
                c['sections'] = app
        for g, n in row['events'].items():
            c = chars.setdefault(f'event:{g}', dict(key=f'event:{g}', archive=g, name=NAMES.get(g, g), types=set(), rooms=[], event=True))
            if label not in c['rooms']:
                c['rooms'].append(label)
        rooms.append(row)
    # coverage + PS2 availability
    for c in chars.values():
        arc = c['archive']
        c['types'] = sorted(c['types'])
        c['ps2_archive'] = f'{arc}.dat' in afs
        if 'sections' in c:
            s = c['sections']
            g = gc_archive(arc)
            gb, gh = g.entries[s['body'] - 4][1], g.entries[s['head'] - 4][1]
            c['gc_triangles'] = sum(gc_tris(g.entries[x - 4][1]) or 0 for x in (s['body'], s['head'], s['rhand'], s['lhand']))
            hits = [cast_sigs.get(gc_sig(gb)), cast_sigs.get(gc_sig(gh))]
            c['cast'] = hits[0][0] if hits[0] and hits[1] and hits[0][0] == hits[1][0] else None
            p = ps2_archive(arc)
            ok = p is not None
            if ok:
                for x in (s['body'], s['head'], s['rhand'], s['lhand'], s['tpl']):
                    ok &= (x - 4) in p
                if ok:
                    c['ps2_bone_check'] = {}
                    for x in (s['body'], s['head'], s['rhand'], s['lhand']):
                        m = pb.parse_bin(p[x - 4][1])
                        gm = modelbin.parse(g.entries[x - 4][1])
                        same = len(m.bones) == len(gm.parts) and all((q['id'], q['parent']) == (r.attach, r.parent) for q, r in zip(m.bones, gm.parts))
                        dt = max((max(abs(u - v) for u, v in zip(q['pos'], r.pos)) for q, r in zip(m.bones, gm.parts)), default=0)
                        c['ps2_bone_check'][hex(x)] = dict(bones=[len(m.bones), len(gm.parts)], id_parent_equal=same, max_translation_mm=dt)
                        ok &= same and dt < 1e-3
                    c['ps2_triangles'] = sum(len(pb.triangles(pb.parse_bin(p[x - 4][1]))) for x in (s['body'], s['head'], s['rhand'], s['lhand']))
            c['ps2_convertible'] = bool(ok)
            c['sections'] = {k: (hex(v) if v else None) for k, v in s.items()}
        elif arc in CAST_ANIMALS:
            c['cast'] = CAST_ANIMALS[arc]
        elif arc == 'pl00':
            c['cast'] = 'leon4k (cl lane)'
        else:
            c['cast'] = None
        if not c.get('event') and 'sections' not in c:
            p = ps2_archive(arc) if c['ps2_archive'] else None
            try:
                g = gc_archive(arc)
                c['gc_bins'] = sum(1 for t, _ in g.entries if drs.tag_name(t) == 'BIN')
            except FileNotFoundError:
                c['gc_bins'] = None
            c['ps2_bins'] = sum(1 for t, _ in p.values() if t == 'BIN') if p else None
    out = dict(rooms=rooms, characters=sorted(chars.values(), key=lambda c: c['key']))
    (a.out / 'inventory.json').write_text(json.dumps(out, indent=1, default=list))
    # markdown
    L = ['| Character | Name | Model types | Rooms (route order) | External cast | PS2 source | GC tris | PS2 tris |', '|---|---|---|---|---|---|---|---|']
    first = {}
    for i, r in enumerate(rooms):
        for c in r['characters']:
            first.setdefault(c['key'], i)
        for g in r['events']:
            first.setdefault(f'event:{g}', i)
    for c in sorted(chars.values(), key=lambda c: (first.get(c['key'], 99), c['key'])):
        if 'sections' in c:
            bc = c.get('ps2_bone_check', {})
            if c.get('ps2_convertible'):
                ps2 = 'yes, skeleton identical'
            elif bc and all(v['id_parent_equal'] for v in bc.values()):
                ps2 = 'yes, a section rest differs %.1f mm' % max(v['max_translation_mm'] for v in bc.values())
            elif bc:
                ps2 = 'bone tables differ: ' + ', '.join(f'{k} {v["bones"][0]} vs {v["bones"][1]}' for k, v in bc.items()
                                                         if not v['id_parent_equal'])
            else:
                ps2 = 'archive only' if c['ps2_archive'] else 'no archive'
        elif c.get('event'):
            ps2 = 'event model (evd files)'
        else:
            ps2 = f'{c["archive"]}.dat ({c.get("ps2_bins")} BINs)' if c['ps2_archive'] else '-'
        L.append(f'| {c["key"]} | {c["name"]} | {",".join(hex(t) for t in c["types"]) or "-"} | {" ".join(r.split()[0] for r in c["rooms"])} | '
                 f'{c.get("cast") or "**missing**"} | {ps2} | {c.get("gc_triangles", "")} | {c.get("ps2_triangles", "")} |')
    (a.out / 'inventory.md').write_text('\n'.join(L) + '\n')
    print('\n'.join(L))


if __name__ == '__main__':
    main()
