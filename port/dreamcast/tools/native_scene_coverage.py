#!/usr/bin/env python3
"""Native scene coverage inventory (2026-10-03): for every room on the available GameCube disc, what the Dreamcast
renderer draws from a native package and what still takes a source fallback, per category (actors, world, room
objects / props, effects), with the evidence behind each claim and the next conversion each gap needs.

It does NOT claim gameplay or route support for any room: a room counts only as listed here; "native asset" means a
package or certificate exists, "runtime" means a named run log showed the path being taken.

Inputs (all existing registries, nothing hand-entered per room):
- rooms: the GC disc's St*/rNNN files (assetpipe sources.toml gc_iso); disc 2 (St3/St5) is reported as unavailable
  when gc_iso2 is empty;
- enemies per room: the ESL lists (etc/emleon0N.esl, omake0N.esl) and the room scripts' EmReadSearch / EmSetFromList2
  (assetpipe/discover.py); stage 1 uses stage.cpp's list rule (esl_list_numbers), other stages the UNION of all lists
  (their rule is not mirrored: marked "list rule unmirrored");
- event actor groups: the stage-1 inventory of ps2_cast_inventory.py (--stage1-inventory) when given;
- actor native coverage: coarse_actor_material.inc source_appearance_type + actor_material_records.inc role rows
  (certified), game/actor_appearance_aliases.inc (aliases behind ACTOR_APPEARANCE_ALIAS, default 0), the alias
  check JSON of native_appearance_alias.py (data-verified pairs not emitted);
- world: native_static.cpp re4dc_ps2_world_room (runtime PS2 world list) and the ps2rooms store's out/<room>-ps2
  packages (converted, not in the runtime list);
- runtime evidence: harness scenario run logs (--runs), their room lines, ACENSUS per-part rows, ATX_WHY /
  ACTOR_MATERIAL decline lines and ENC counts.

usage (WSL): native_scene_coverage.py <out dir> [--alias-json J] [--stage1-inventory J] [--runs S1,S2,...]
Writes <out>/coverage.json and <out>/coverage.md.
"""
import argparse, hashlib, json, re, struct, sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
GAME = HERE.parent / 'game'
REPO = HERE.parents[2]
sys.path[:0] = [str(HERE), str(REPO / 'tools')]
from assetpipe.config import Config  # noqa: E402
from assetpipe.rooms import GcIso  # noqa: E402
from assetpipe import discover as dsc  # noqa: E402
import native_appearance_alias as naa  # noqa: E402

HARNESS = Path('/mnt/c/Game Dev/Emulators/re4-assets-private/world-agent-20260926/continuation-20260927/playability-r11-r1')
PS2ROOMS = Path('/mnt/c/Game Dev/Emulators/re4-assets-private/ps2rooms-20260930/out')
GANADO_MODULES = ('em10', 'em11', 'em12', 'em13', 'em14', 'em15', 'em16', 'em17')
# Leon's archive per room (new game, Leon segments): title.cpp keeps costume 0 (em/pl00.drs, the leon4k-certified
# descriptor) only in r120/r100/r101/r103/r106 and sets costume 1 (em/pl08.drs) in every other room (title.cpp, the
# room_id32 test before PlSetCostume's caller); run logs of r104/r105/r107/r210/r40c read em/pl08.drs. Special
# costumes and the other playable characters (Ashley/Ada segments, omake) are not bound here.
PL00_ROOMS = ('r120', 'r100', 'r101', 'r103', 'r106')
PL08_NOTE = ('pl08 (costume 1): body BINs 0x4/0xa/0xd and TPL 0x5 differ from pl00 (GC entries; head/hand BINs 0x6/0x8/'
             '0x9/0x18 and TPLs 0x7/0x11 identical), so the leon4k role rows cannot admit it')
ANIMAL_CASTS = {'em21': 'dog-00/01', 'em23': 'crow-folded/spread', 'em26': 'cow-00/01', 'em28': 'chicken-00/01'}


def runtime_ps2_world_rooms():
    # The hand list (PS2_WORLD_REGISTRY=0, the default): the definition that returns room==... comparisons. With the
    # registry the first definition is the bitmap lookup, so a plain "first body" search found no rooms.
    s = (GAME / 'platform/native_static.cpp').read_text()
    m = re.search(r'int re4dc_ps2_world_room\(unsigned room\)\{\s*return (room==0x[^;]+);', s)
    return sorted(int(x, 16) for x in re.findall(r'room==(0x[0-9a-fA-F]+)', m.group(1)))


def aliases_emitted(name='actor_appearance_aliases.inc'):
    p = GAME / name
    if not p.exists():
        return {}
    out = {}
    for app, mid, typ in re.findall(r'^\{(\d+)u,0x([0-9a-fA-F]+)u,(\d+)u\}', p.read_text(), re.M):
        out[(int(mid, 16), int(typ))] = int(app)
    return out


def disc_rooms(iso):
    rooms = defaultdict(list)
    for p in iso.files:
        parts = p.split('/')
        if parts[0].lower().startswith('st') and re.match(r'r[0-9a-f]{3}\.', parts[-1]):
            rooms[parts[-1][:4]].append(p)
    return dict(sorted(rooms.items()))


def room_enemies(cfg, tab, room_name):
    room = int(room_name[1:], 16)
    game = cfg.path('game_data')
    try:
        lists, rule = dsc.esl_list_numbers(room), 'stage.cpp checkEmListNo (mirrored)'
    except SystemExit:
        lists, rule = [(i, 'union') for i in range(len(dsc.ESL_FILES))], 'list rule unmirrored: union of all ESL lists'
    out = defaultdict(set)
    for no, cond in lists:
        if no is None:
            continue
        p = Path(game) / dsc.ESL_FILES[no]
        if not p.exists():
            continue
        for e in dsc.esl_entries(p, room):
            out[(e['id'], e['type'])].add(('entry' if e['alive'] else 'enabled-later') + ('' if cond != 'union' else '@' + dsc.ESL_FILES[no].split('/')[-1]))
    sc = dsc.script_refs(REPO, room)
    for eid in sc['loads']:
        if not any(k[0] == eid for k in out):
            out[(eid, None)].add('script-load')
    return out, rule, sc.get('file')


def archive_of(tab, eid):
    e = tab.enemy(eid)
    return Path(e['archive']).stem if e and e.get('archive') else 'em%02x' % eid


def parse_run(path):
    raw = path.read_bytes()
    txt = raw.decode('utf-16' if raw[:2] in (b'\xff\xfe', b'\xfe\xff') else 'utf-8', errors='replace')
    rooms = sorted(set(re.findall(r'\broom[= ](?:0x)?(1[0-9a-f]{2}|2[0-9a-f]{2}|4[0-9a-f]{2})\b', txt)))
    warp = re.findall(r'warp: .*', txt)[:3]
    acensus = defaultdict(lambda: dict(parts=0, frames=0))
    for m in re.finditer(r'ACENSUS frame=(\d+) id=([0-9a-f]+) ot=(\d+) nparts=(\d+) parts=(\d+) verts=\d+ per_frame_verts=(\d+)', txt):
        k = f'id={m.group(2)} ot={m.group(3)} nparts={m.group(4)}'
        acensus[k]['parts'] += int(m.group(5)); acensus[k]['frames'] += 120
        acensus[k]['max_per_frame_verts'] = max(acensus[k].get('max_per_frame_verts', 0), int(m.group(6)))
    why = defaultdict(int)
    for m in re.finditer(r'ATX_WHY f=\d+ m=\S+ vptr=\S+ id=([0-9a-f]+) ot=(\d+) parts=(\d+) (\w+)=(\d+)', txt):
        why[f'id={m.group(1)} {m.group(4)}={m.group(5)}'] += 1
    mat = defaultdict(int)
    for m in re.finditer(r'ACTOR_MATERIAL decline=(\d+) app=(\d+) role=(\d+)', txt):
        mat[f'decline={m.group(1)} app={m.group(2)} role={m.group(3)}'] += 1
    # ATX_M (ACTOR_TRANSACTION_DIAG): owner-path events per model id (no cModel::type in the line: per id only).
    owner = defaultdict(lambda: defaultdict(int))
    for m in re.finditer(r'ATX_M f=\d+ m=\S+ vptr=\S+ id=([0-9a-f]+) ot=\d+ parts=\d+ infos=\d+ ev=([\d: ]+)', txt):
        for pair in m.group(2).split():
            k, v = pair.split(':')
            owner[m.group(1)][int(k)] += int(v)
    # ENC_CENSUS (Ganados ids 0x10..0x20 together, per presented frame): reached / owner-drawn / source / failed.
    enc = [tuple(map(int, m)) for m in re.findall(r'^ENC f=\d+ ga=(\d+) oa=\d+ gr=(\d+) go=(\d+) gs=(\d+) gx=(\d+)', txt, re.M)]
    enc_sum = dict(frames=len(enc), ganados_alive_max=max(e[0] for e in enc), reached=sum(e[1] for e in enc),
                   owner=sum(e[2] for e in enc), source=sum(e[3] for e in enc), failed=sum(e[4] for e in enc)) if enc else None
    return dict(log=path.parent.parent.name, rooms=rooms, warp=warp, enc=enc_sum, halt=len(re.findall(r'\bHALT\b', txt)),
                missing=len(re.findall(r'RE4DC MISSING', txt)), per_part_rows=dict(acensus),
                atx_why=dict(why), material_declines=dict(mat),
                owner_events={k: dict(v) for k, v in owner.items()})


def observed(runs_here, eid):
    """Runtime evidence for one enemy id in the runs of a room (type-agnostic: the logs carry no cModel::type)."""
    key = '%02x' % eid
    out = []
    for name, r in runs_here.items():
        ev = r['owner_events'].get(key, {})
        pp = sum(v['parts'] for k, v in r['per_part_rows'].items() if k.startswith(f'id={key} '))
        if ev or pp:
            out.append(dict(run=name, owner_admitted=ev.get(16, 0), owner_submitted=ev.get(18, 0),
                            semantics_declined=ev.get(6, 0), plan_declined=ev.get(4, 0),
                            source_light_declined=ev.get(26, 0), per_part_parts=pp))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('out', type=Path)
    ap.add_argument('--alias-json', type=Path)
    ap.add_argument('--stage1-inventory', type=Path)
    ap.add_argument('--runs', default='')
    ap.add_argument('--world-manifest', type=Path, help='world worker manifest (world-coverage.json): the world column '
                    'quotes its room status; without it the lane snapshot is labelled superseded')
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    cfg = Config()
    iso = GcIso(cfg.path('gc_iso'))
    tab = dsc.Tables(REPO)
    cert, _ = naa.certified_table()
    cert_pairs = {(mid, t): app for app, (mid, t) in cert.items()}
    emitted = aliases_emitted()
    emitted2 = aliases_emitted('actor_appearance_aliases_ext.inc')
    held = {}
    verified, unsupported = {}, {}
    if a.alias_json and a.alias_json.exists():
        for r in json.loads(a.alias_json.read_text())['results']:
            if r.get('status') in ('verified', 'certified'):
                verified[(int(r['module'][2:], 16), r['type'])] = r.get('appearance')
            if r.get('status') == 'unsupported-source':
                unsupported[r['module']] = r.get('why', '')
            if r.get('status') == 'accessory-differs':
                held[(int(r['module'][2:], 16), r['type'])] = r
    nocast = {}
    if a.alias_json and a.alias_json.exists():
        for r in json.loads(a.alias_json.read_text())['results']:
            if r.get('status') == 'no-certified-appearance':
                nocast[(int(r['module'][2:], 16), r['type'])] = r
    events = {}
    if a.stage1_inventory and a.stage1_inventory.exists():
        inv = json.loads(a.stage1_inventory.read_text())
        for r in inv['rooms']:
            events.setdefault(r['room'].split()[0], {}).update(r.get('events', {}))
    ps2_runtime = runtime_ps2_world_rooms()
    world_manifest, world_src = None, None
    if a.world_manifest and a.world_manifest.exists():
        raw = a.world_manifest.read_bytes()
        world_manifest = json.loads(raw)['rooms']
        world_src = dict(path=str(a.world_manifest), sha256=hashlib.sha256(raw).hexdigest())
    runs = {}
    for name in [x for x in a.runs.split(',') if x]:
        p = HARNESS / 'scenarios' / name / 'capture' / 'run-output.txt'
        if p.exists():
            runs[name] = parse_run(p)
    rooms = disc_rooms(iso)
    rows, summary = [], []
    for room_name, files in rooms.items():
        stage = int(room_name[1], 16)
        enemies, rule, script = room_enemies(cfg, tab, room_name)
        rr = dict(room=room_name, stage=stage, files=sorted(files), enemy_list_rule=rule, script=script, items=[])
        for (eid, typ), why in sorted(enemies.items(), key=lambda x: (x[0][0], -1 if x[0][1] is None else x[0][1])):
            arc = archive_of(tab, eid)
            it = dict(category='actor', family=arc, enemy_id='0x%02x' % eid, type=typ, why=sorted(why))
            if arc in GANADO_MODULES and typ is not None:
                key = (eid, typ)
                if key in cert_pairs:
                    it.update(native_asset='cast + certified role rows', appearance=cert_pairs[key],
                              status='native (certified)', next='-')
                elif key in emitted:
                    it.update(native_asset='existing cast (byte-identical source entries, native_appearance_alias.py)',
                              appearance=emitted[key], status='native behind ACTOR_APPEARANCE_ALIAS=1 (default 0)',
                              next='runtime gates + cost, then adoption decision')
                elif key in emitted2:
                    it.update(native_asset='existing cast (byte-identical source entries, native_appearance_alias.py --knob 2)',
                              appearance=emitted2[key], status='native behind ACTOR_APPEARANCE_ALIAS=2 (default 0)',
                              next='runtime gates in a room that spawns it, then adoption decision')
                elif key in held:
                    it.update(native_asset='not emitted: accessory model differs from the certified type',
                              status='fallback (source path); held out (accessory-differs)',
                              next='certify the accessory (slots ' + ','.join(str(x['slot']) for x in held[key]['accessory_diff']) + ') or keep source')
                elif key in verified:
                    it.update(native_asset='existing cast (data-verified identical source entries; alias not emitted)',
                              appearance=verified[key], status='fallback (source path); alias-ready',
                              next=f'emit alias for {arc} after a runtime run in a room that spawns it')
                elif arc in unsupported:
                    it.update(native_asset='not certifiable as-is', status='fallback (source path); setter outside the reviewed shape',
                              next=f'review {arc}_set.cpp ({unsupported[arc][:80]}) before any alias')
                elif key in nocast:
                    it.update(native_asset='none', status='fallback (source path)',
                              next='convert the appearance (ps2_cast.py / cast_bundle.py), add certified role rows')
                else:
                    it.update(native_asset='unknown (module/type not checked by native_appearance_alias.py)',
                              status='fallback (source path)', next='run native_appearance_alias.py check --archives ' + arc)
            elif arc in ANIMAL_CASTS:
                it.update(native_asset=f'cast pack {ANIMAL_CASTS[arc]} (cast-20260925)', status='fallback: per-part path at source detail (no runtime adapter for non-Ganado packs)',
                          next='generic coarse model adapter (docs/lanes/ps2cast.md proposal)')
            else:
                it.update(native_asset='none', status='fallback: per-part path at source detail (if it qualifies) or source',
                          next='PS2/GC conversion + generic non-Ganado runtime format')
            it['evidence'] = 'generated (source/archive data, not a runtime observation)'
            rr['items'].append(it)
        # The player: leon4k is certified against the pl00 descriptor (appearance 256). Which player archive / costume a
        # room loads (St2/St4 bring-up needed pl08) is not bound here, so the row is a static candidate, never counted
        # native; run logs only add an observation (owner events for id 00 in a named run of the room).
        if room_name in PL00_ROOMS:
            it = dict(category='player', family='Leon em/pl00.drs (costume 0)', archive='em/pl00.drs',
                      status='certified descriptor (leon4k, appearance 256); native only where a run shows the owner path',
                      native_asset='leon4k cast + role rows appearance 256 (pl00)', next='-')
        else:
            it = dict(category='player', family='Leon em/pl08.drs (costume 1)', archive='em/pl08.drs',
                      status='fallback (source path): ' + PL08_NOTE,
                      native_asset='none (leon4k is pl00 only)',
                      next='convert pl08 body BINs 0x4/0xa/0xd + TPL 0x5 (cast + role rows), reuse the identical head/hand rows')
        rr['items'].append(it)
        for g, n in sorted(events.get(room_name, {}).items()):
            if g == 'pl00':
                continue
            rr['items'].append(dict(category='event-actor', family=g, count=n, native_asset='none',
                                    status='fallback (source path) unless it is a certified Leon/Ganado model',
                                    next='event model conversion'))
        room = int(room_name[1:], 16)
        if world_manifest is not None:
            wm = world_manifest.get(room_name)
            w = dict(status=f'{wm["status"]} (world manifest)' if wm else 'not in the world manifest',
                     next='see the world worker manifest')
        elif room in ps2_runtime:
            w = dict(status='native PS2 world package (runtime list native_static.cpp re4dc_ps2_world_room)')
        elif (PS2ROOMS / f'{room_name}-ps2').exists():
            w = dict(status='converted PS2 world package exists (ps2rooms out/), NOT in the runtime list: source/Standard scenery path',
                     next='add to re4dc_ps2_world_room + stage dc/native/<room>/ps2-world.* + in-room gates')
        else:
            w = dict(status='no native world package: source/Standard scenery path', next='ps2_room_r4im.py conversion (ps2rooms lane)')
        if world_manifest is None:
            w['status'] = 'SUPERSEDED lane snapshot: ' + w['status']
        rr['items'].append(dict(category='world', family=room_name, native_asset=w['status'].split(':')[0], **w))
        rr['items'].append(dict(category='props/objects', family='room objects (cObj / SetModel)',
                                status='per-part path (NATIVE_ACTOR_FAST meshlet conversion of the SOURCE geometry, source detail); no native package',
                                native_asset='none', next='static/prop package path (none exists yet)'))
        rr['items'].append(dict(category='effects', family='Esp / Efm',
                                status='EspCommonTrans sprites native (COARSE_FX_SPRITES=2, EFFECT_ROOM=7); other effect draws source',
                                native_asset='native sprite path (shared, not per room)', next='per-effect census in this room'))
        ev = {n: r for n, r in runs.items() if room_name[1:] in r['rooms']}
        rr['runtime_evidence'] = ev if ev else 'untested (no run log given for this room)'
        for i in rr['items']:
            if i['category'] == 'actor' and 'enemy_id' in i:
                obs = observed(ev, int(i['enemy_id'], 16)) if ev else None
                i['runtime'] = obs if obs else ('not observed in the given runs' if ev else 'untested')
            elif i['category'] == 'player':
                obs = observed(ev, 0) if ev else None
                i['runtime'] = obs if obs else ('not observed in the given runs' if ev else 'untested')
        rows.append(rr)
        acts = [i for i in rr['items'] if i['category'] == 'actor']
        pl = [i for i in rr['items'] if i['category'] == 'player'][0]
        wi = rr['items'][[i['category'] for i in rr['items']].index('world')]
        summary.append(dict(room=room_name, stage=stage, actors=len(acts),
                            native=sum(1 for i in acts if i['status'].startswith('native (')),
                            native_knob=sum(1 for i in acts if i['status'].startswith('native behind ACTOR_APPEARANCE_ALIAS=1')),
                            native_knob2=sum(1 for i in acts if i['status'].startswith('native behind ACTOR_APPEARANCE_ALIAS=2')),
                            alias_ready=sum(1 for i in acts if 'alias-ready' in i['status']),
                            fallback=sum(1 for i in acts if not i['status'].startswith('native')),
                            player=('pl00 certified' if pl.get('archive') == 'em/pl00.drs' else 'pl08 fallback') +
                                   (' (owner path seen in a named run)' if isinstance(pl.get('runtime'), list) and
                                    any(o['owner_admitted'] for o in pl['runtime']) else
                                    ' (per-part path seen in a named run)' if isinstance(pl.get('runtime'), list) else ''),
                            world=wi['status'].replace(' (world manifest)', '') if world_manifest is not None else wi['native_asset'],
                            runtime='run log named' if ev else 'none'))
    disc2 = 'unavailable (sources.toml gc_iso2 is empty): St3/St5 rooms are not inventoried' if not cfg.path('gc_iso2') else 'configured'
    out = dict(tool='native_scene_coverage.py', gc_iso='GC disc 1 (sources.toml gc_iso)', disc2=disc2,
               certified={str(k): ['%#x' % v[0], v[1]] for k, v in cert.items()},
               aliases_emitted=[[a_, '%#x' % m, t] for (m, t), a_ in emitted.items()],
               aliases_emitted_knob2=[[a_, '%#x' % m, t] for (m, t), a_ in emitted2.items()],
               runtime_ps2_world_rooms=['r%03x' % r for r in ps2_runtime],
               world_manifest=world_src or 'none given: world column = SUPERSEDED lane snapshot', rooms=rows, summary=summary)
    (a.out / 'coverage.json').write_text(json.dumps(out, indent=1, default=list) + '\n')
    md = ['# Native scene coverage (generated by tools/native_scene_coverage.py)', '',
          f'GC disc: {out["gc_iso"]}; disc 2: {disc2}.', '',
          'Actor rows: one per (enemy id, model type) the room\'s lists/scripts can spawn; "native" = a certified or',
          'alias row admits it on the owner path (still subject to every per-draw proof; gore, alternate hands, fades and',
          'unknown states fall back). Not a gameplay/route support claim.', '',
          'Columns (STATIC CANDIDATE counts from source/archive data, not runtime proof): native = enemy rows a certified',
          'role table admits on the owner path in the default image; knob = only with ACTOR_APPEARANCE_ALIAS=1 (default 0);',
          'alias-ready = existing cast proven byte-identical, not emitted; fallback = every other enemy row (alias-ready',
          "included); knob2 = only with ACTOR_APPEARANCE_ALIAS=2. player = Leon's archive by room (title.cpp costume rule):",
          'pl00 (leon4k certified) in r120/r100/r101/r103/r106, pl08 elsewhere (fallback: its body BINs/TPL differ). Room',
          'objects/props, weapons and most effects are fallback in every room (see coverage.json per room).', '',
          'world = ' + (f"the world worker's manifest status ({world_src['path']}, sha256 {world_src['sha256'][:16]}..)" if world_src
                         else 'SUPERSEDED lane snapshot (no world manifest given)') + '.', '',
          'Evidence: "run log" = a named run log of that room exists; it is NOT proof that the room or its actors are native.',
          'coverage.json adds per actor id what those logs observed (owner admitted/submitted, declines, per-part rows;',
          'per id only: the logs carry no model type).', '',
          '| room | stage | enemy rows | native (static) | knob | knob2 | alias-ready | fallback | player | world | run log |',
          '|---|---|---:|---:|---:|---:|---:|---:|---|---|---|']
    for s in summary:
        md.append(f'| {s["room"]} | {s["stage"]} | {s["actors"]} | {s["native"]} | {s["native_knob"]} | {s["native_knob2"]} | {s["alias_ready"]} | '
                  f'{s["fallback"]} | {s["player"]} | {s["world"]} | {s["runtime"]} |')
    md += ['', '## Actor gaps by family and type (rooms)', '']
    gaps = defaultdict(set)
    for r in rows:
        for i in r['items']:
            if i['category'] == 'actor' and not i['status'].startswith('native'):
                gaps[(i['family'], i.get('type'), i['status'], i.get('next', ''))].add(r['room'])
    md += ['| family | type | status | rooms | next |', '|---|---|---|---|---|']
    for (f, t, st, nx), rs in sorted(gaps.items(), key=lambda x: (-len(x[1]), x[0][0], str(x[0][1]))):
        md.append(f'| {f} | {t} | {st} | {" ".join(sorted(rs))} | {nx} |')
    (a.out / 'coverage.md').write_text('\n'.join(md) + '\n')
    print(f'{len(rows)} rooms; summary rows {len(summary)}; runs parsed {len(runs)}')


if __name__ == '__main__':
    main()
