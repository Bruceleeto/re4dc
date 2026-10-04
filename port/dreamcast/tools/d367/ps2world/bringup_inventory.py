#!/usr/bin/env python3
"""bringup_inventory.py: what entering each eligible room needs, per requirement, as machine-readable JSON (WSL).

    bringup_inventory.py --manifest <world-coverage.json> --out <dir> [--rooms-dir DIR] [--room rXXX ...]

For every room the registry manifest marks eligible (validation ok) it records, from the sources themselves:
  package       the registry's selected PS2 world package and states (staged / entered / drawn / reviewed)
  container     the source room container on GC disc 1 (stN/rXXX.das, bytes) and whether this lane prepared the
                released .dar/.arc (<rooms-dir>/rel-rXXX); compact-room needs a reviewed prepare_native_ui.py
                ROOM_CONTRACTS entry (slot count, SMD / EFF / ITM / model slots) - listed if present
  banks         aica_banks.py ROOMS entry (the room's arena banks) and a banked .dar in <rooms-dir>/aica-*
  player        Leon's costume archive: St1 pl00 (on the base disc); St2/St4 costume 1 pl08 (the route lane's set,
                the GC pl08.drs exceeds the player area); partner pl11 (Ashley) for St2/St4 (WORLD_STAGE_MODULES)
  enemies       assetpipe discover: the room's ESL lists and script spawns/loads -> archives (prepared? source
                heap-4 bytes) and REL modules (Makefile MODULES / modules.cpp table / audit list); its problems
  module        the stage REL holding the room script (src/stN/rXXX.cpp) and its lint errors (discover)
  events        discover's events (evd actors, route movie) and their problems
  pose          warp.py presets for the room; GC door arrivals into the room (registry door scan)
Status: 'staged' (a fixture in this lane / the play fixtures stages the room's container), 'stageable' (no blocker;
'needs' lists the table entries still to add, each derived here from the sources: the compact-room contract from the
decoded container's slot tags, the aica_banks.py ROOMS entry from the room .dar + discover's archives, a warp preset
from a door arrival; the rest is produced by le_mirror, prepare_native_ui, room_smd, convert_room_bins, aica_banks,
room_fixture), else 'blocked' with the blockers. Writes <out>/bringup-inventory.json
and .md. Read-only: discover runs without --wire/--fix and writes nothing.
"""
import argparse, json, re, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOLS = HERE.parents[1]
REPO = HERE.parents[4]
sys.path[:0] = [str(TOOLS), str(TOOLS / 'd367')]
import warp  # noqa: E402
import world_registry as reg  # noqa: E402
from assetpipe.config import Config  # noqa: E402
from assetpipe.discover import discover  # noqa: E402
from assetpipe.rooms import GcIso  # noqa: E402

PL08 = (Path('/root/probe/lanes/route/aica-r104/em/pl08.drs'), Path('/root/probe/lanes/route/tex-pl08'))
LANE_ROOMS = Path('/root/probe/sup-world-coverage-20261003/rooms')
PREPARED_ROOT = Path('/root/probe/lanes/route')   # the route lane's per-room prepared dirs (aica-rXXX/em/...)
STAGE_LINKED = ('st2_0', 'st4_0', 'pl11')        # game/Makefile WORLD_STAGE_MODULES=1: MODULES += st2_0 st4_0 pl11


def knob_modules(makefile):
    """{module: knob} for the Makefile's knob-guarded `MODULES += ...` lines (ifneq ($(KNOB),0) blocks): modules an
    image links only with that knob (WORLD_STAGE_MODULES=1: st2_0 st4_0 pl11; WORLD_ROOM_MODULES=1: st2_2 em1f)."""
    out, knob = {}, None
    for line in Path(makefile).read_text().splitlines():
        m = re.match(r'ifneq \(\$\((\w+)\),0\)', line)
        if m:
            knob = m.group(1)
        m = re.match(r'MODULES \+= (.*)$', line)
        if m and knob:
            for mod in m.group(1).split():
                out.setdefault(mod, knob)
    return out


def contracts():
    import prepare_native_ui
    return prepare_native_ui.ROOM_CONTRACTS


def aica_rooms():
    import aica_banks
    return aica_banks.ROOMS


def slot_tags(iso, src):
    """The source room container's slot tags (le_mirror.prepare_room_archive's decode of its one YZ2 payload, read
    big-endian as the source archive is), or (None, error)."""
    import struct
    import le_mirror
    from decode_yz2 import decode
    data = iso.read(src)
    try:
        if data[:32] != le_mirror.CONTAINER_MAGIC:
            return None, 'not a DVD container'
        for pos in range(le_mirror.ENTRY_SIZE, le_mirror.HEADER_TABLE, le_mirror.ENTRY_SIZE):
            kind, size, _dest, offset = struct.unpack_from('>4I', data, pos)
            if kind == 0:
                dec = decode(data[offset:offset + size])
                n = struct.unpack_from('>I', dec)[0]
                return [dec[16 + 4 * n + 4 * i:20 + 4 * n + 4 * i].rstrip(b'\0').decode('ascii', 'replace')
                        for i in range(n)], None
        return None, 'no type-0 payload'
    except Exception as e:  # a source the decoder refuses is reported, not fatal
        return None, '%s: %s' % (type(e).__name__, e)


def derive_contract(tags):
    """prepare_native_ui.py ROOM_CONTRACTS shape from slot tags: slot count, the SMD, EFF and ITM slots and every TPL
    right after a BIN (the model texture slots). Unreviewed: header_grow and other per-room facts need a look."""
    one = lambda t: [i for i, x in enumerate(tags) if x == t]
    smd, itm = one('SMD'), one('ITM')
    return dict(slots=len(tags), smd=smd[0] if len(smd) == 1 else smd, effs=tuple(one('EFF')),
                itm=itm[0] if len(itm) == 1 else itm,
                model_slots=tuple(i for i, x in enumerate(tags) if x == 'TPL' and i and tags[i - 1] == 'BIN'))


def same(a, b):
    return (tuple(a) if isinstance(a, (list, tuple)) else a) == (tuple(b) if isinstance(b, (list, tuple)) else b)


def room_inventory(cfg, iso, rec, arrivals, rooms_dir, contract_tab, aica_tab):
    room = rec['room']
    stage = int(room[1], 16)
    st = 'st%d' % stage
    req, blockers, needs = {}, [], []
    # package
    stt = rec.get('states') or {}
    req['package'] = dict(selected_by=(rec.get('package') or {}).get('selected_by'), hashes=stt.get('hashes'),
                          staged=stt.get('staged'), entered=len(stt.get('entered') or []),
                          drawn=len(stt.get('drawn') or []), reviewed=len(stt.get('reviewed') or []))
    # container
    src = '%s/%s.das' % (st, room)
    size = iso.size(src) if hasattr(iso, 'size') else (len(iso.read(src)) if iso.find(src) else None)
    rel = rooms_dir / ('rel-' + room) / st
    req['container'] = dict(source=src if size else None, source_bytes=size,
                            released=[str(p) for p in (rel / (room + '.dar'), rel / (room + '.arc')) if p.is_file()],
                            contract=contract_tab.get(room), fixtures=(rec.get('staging') or {}).get('room_container'))
    if not size:
        blockers.append('container: %s not on GC disc 1' % src)
    if size:
        tags, why = slot_tags(iso, src)
        dc = derive_contract(tags) if tags else None
        req['container'].update(slot_tags=tags, derived_contract=dc)
        if tags is None:
            blockers.append('container: source not decodable (%s)' % why)
        elif room in contract_tab:
            req['container']['contract_matches_tags'] = all(same(contract_tab[room][k], dc[k]) for k in dc)
        elif not isinstance(dc['smd'], int) or not isinstance(dc['itm'], int):
            blockers.append('container: slot tags give no single SMD / ITM slot (%s)' % ' '.join(tags))
        else:
            needs.append('ROOM_CONTRACTS entry (derived from the slot tags, to review): %s' % dc)
    # banks
    banked = sorted(str(p) for p in rooms_dir.glob('aica-*/%s/%s.dar' % (st, room)))
    req['banks'] = dict(aica_rooms_entry=aica_tab.get(room), banked=banked)
    aica_need = room not in aica_tab
    # player / partner
    if stage == 1:
        req['player'] = dict(archive='em/pl00.drs', source='base disc')
    else:
        req['player'] = dict(archive='em/pl08.drs (costume 1)', source=str(PL08[0]), images=str(PL08[1]),
                             available=PL08[0].is_file() and PL08[1].is_dir(),
                             partner='pl11 (Ashley): WORLD_STAGE_MODULES=1 links pl11; images prepare_native_ui over '
                                     'em/pl11.drs (%s)' % ('present' if (rooms_dir / 'tex-pl11').is_dir() else 'not prepared'))
        if not req['player']['available']:
            blockers.append('player: the route lane pl08 set is absent')
    # enemies / module / events (discover, read-only)
    try:
        d = discover(cfg, room)
        req['enemies'] = [dict(id=r['id'], archive=r.get('archive'), module=r.get('module'), reasons=r['reasons'],
                               heap4_bytes=r.get('heap4_bytes'), heap4_basis=r.get('heap4_basis', 'prepared'),
                               build=r.get('build')) for r in d['demand']]
        req['module'] = dict(stage_module=d['stage_module'], script=d['script']['file'],
                             lists=d['lists'], entries=len(d['entries']))
        req['events'] = [dict(event=e['event'], on_disc=e['on_disc'], movie=e.get('movie'),
                              prepared=e.get('prepared'), qualified=e.get('qualified')) for e in d['events']]
        req['heap4'] = {k: d['heap4'][k] for k in ('enemy_archives', 'slots', 'worst_case_bytes', 'budget_bytes', 'verdict')}
        probs = [p for p in d['problems'] if not p.startswith('room container')]   # the container is judged above
        req['discover_problems'] = probs
        for e in req['enemies']:
            # a prepared copy elsewhere (the route lane's room dirs, this lane's) serves; else le_mirror prepares the
            # GC disc's source archive (discover counted its source size)
            if e.get('archive') and e['heap4_basis'] != 'prepared':
                name = Path(e['archive']).name
                found = sorted(str(p) for p in list(PREPARED_ROOT.glob('*/em/' + name)) + list(rooms_dir.glob('*/em/' + name)))
                e['prepared_elsewhere'] = found[:3]
        # the room's own stage module (discover lints it but does not check that it is linked)
        mk = REPO / 'port/dreamcast/game/Makefile'
        base_mods = re.search(r'^MODULES = (.*)$', mk.read_text(), re.M).group(1).split()
        kmods = knob_modules(mk)
        sm = d['stage_module']
        req['module']['linked'] = 'default' if sm in base_mods else (kmods[sm] + '=1' if sm in kmods else 'no')
        if req['module']['linked'] == 'no' and sm:
            needs.append('stage module %s: link it (Makefile MODULES under a default-0 knob, modules.cpp MODULE(id, %s), '
                         'audit list; lint %s)' % (sm, sm, 'clean' if not any(p.startswith('error %s:' % sm) for p in probs)
                                                    else 'errors, see blockers'))
        for e in req['enemies']:
            if e.get('module') in kmods:
                e['linked_by'] = kmods[e['module']] + '=1'
        for p in probs:
            if re.match(r'0x[0-9a-f]+ (%s): not in (Makefile MODULES|the ENEMY_DEMAND audit list)' % '|'.join(kmods), p):
                continue   # linked by a knob's MODULES += line (WORLD_STAGE_MODULES=1 / WORLD_ROOM_MODULES=1)
            m = re.match(r'(0x[0-9a-f]+): prepared archive (\S+) missing', p)
            if m:
                e = next((x for x in req['enemies'] if x['id'] == m.group(1)), {})
                needs.append(('enemy archive %s: prepared copy %s' % (m.group(2), e['prepared_elsewhere'][0]))
                             if e.get('prepared_elsewhere') else
                             'enemy archive %s: le_mirror from the GC disc source (%s B)' % (m.group(2), e.get('heap4_bytes')))
            else:
                blockers.append('discover: ' + p)
    except SystemExit as e:
        req['discover_error'] = str(e)
        blockers.append('discover: %s' % e)
    except OSError as e:   # a module discover cannot lint (e.g. no config/G4BE08/modules/<mod>/splits.txt)
        req['discover_error'] = '%s: %s' % (type(e).__name__, e)
        blockers.append('discover failed: %s' % req['discover_error'])
    if aica_need:
        needs.append('aica_banks.py ROOMS entry: %s' % ([st + '/' + room + '.dar'] +
                     [e['archive'] for e in req.get('enemies', []) if e.get('archive')]))
    # pose
    presets = sorted(k for k, v in warp.PRESETS.items() if v['room'] == int(room[1:], 16))
    arr = [x for x in arrivals.get(room, []) if any(x['pos'])]
    req['pose'] = dict(presets=presets, door_arrivals=arr[:12], door_arrival_count=len(arr))
    if not presets and not arr:
        blockers.append('pose: no warp preset and no GC door arrival')
    elif not presets:
        needs.append('warp.py preset from a door arrival: %s door %s at %s' % (arr[0]['src'], arr[0]['door'], arr[0]['pos']))
    staged = bool((req['container']['fixtures'] or {}).get('base_disc') or (req['container']['fixtures'] or {}).get('fixtures')
                  or (req['container']['released'] and req['banks']['banked']))
    # staged: a fixture (or the base disc) already stages the room's container; its open items stay listed
    status = 'staged' if staged else ('stageable' if not blockers else 'blocked')
    return dict(room=room, stage=stage, status=status, blockers=blockers, needs=needs, requirements=req)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--manifest', required=True, type=Path)
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--rooms-dir', type=Path, default=LANE_ROOMS)
    ap.add_argument('--room', action='append')
    a = ap.parse_args(argv)
    man = json.loads(a.manifest.read_text())
    cfg = Config()
    iso = GcIso(str(cfg.path('gc_iso')))
    arrivals = reg.gc_rooms_and_arrivals()['arrivals']
    ctab, atab = contracts(), aica_rooms()
    rows = []
    for room, rec in sorted(man['rooms'].items()):
        if a.room and room not in a.room:
            continue
        if not (rec.get('validation') or {}).get('ok'):
            continue
        rows.append(room_inventory(cfg, iso, rec, arrivals, a.rooms_dir, ctab, atab))
        print(room, rows[-1]['status'], '; '.join(rows[-1]['blockers'])[:160], flush=True)
    counts = {}
    for r in rows:
        counts[r['status']] = counts.get(r['status'], 0) + 1
    doc = dict(schema='re4dc-bringup-inventory/1', generated=time.strftime('%Y-%m-%dT%H:%M:%S%z'),
               tool=dict(path='port/dreamcast/tools/d367/ps2world/bringup_inventory.py', sha256=reg.sha(__file__)),
               manifest=dict(path=str(a.manifest), sha256=reg.sha(a.manifest)), counts=counts, rooms=rows)
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / 'bringup-inventory.json').write_text(json.dumps(doc, indent=1, default=str) + '\n')
    md = ['# Bring-up inventory (tools/d367/ps2world/bringup_inventory.py)', '', 'counts: %s' % counts, '',
          '| room | status | enemies (archive/module) | stage module | contract | banks | pose | needs | blockers |',
          '|---|---|---|---|---|---|---|---|---|']
    for r in rows:
        q = r['requirements']
        md.append('| %s | %s | %s | %s | %s | %s | %s | %d | %s |' % (
            r['room'], r['status'],
            ' '.join('%s/%s' % (Path(e['archive']).stem if e.get('archive') else '-', e.get('module') or '-')
                     for e in q.get('enemies', [])) or 'none',
            (q.get('module') or {}).get('stage_module'), 'yes' if q['container']['contract'] else 'no',
            'yes' if q['banks']['aica_rooms_entry'] else 'no',
            '%d preset, %d doors' % (len(q['pose']['presets']), q['pose']['door_arrival_count']),
            len(r['needs']), '; '.join(r['blockers'])[:220]))
    (a.out / 'bringup-inventory.md').write_text('\n'.join(md) + '\n')
    print(json.dumps(counts))


if __name__ == '__main__':
    main()
