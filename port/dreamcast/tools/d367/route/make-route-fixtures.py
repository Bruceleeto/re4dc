"""Lane route fixtures (2026-10-01): play-staging fixtures for rooms past r103 (r106 first).

Writes into the playability harness tour dir (new files only, never over an existing file):
  tour/route-<view>/warp.txt         tools/d367/warp.py <preset>
  tour/route-rel-<view>-pw.json      tour/rel-r103-entry-pw.json (the play staging: PS2 worlds, texture VQ, release
                                     r100) + the room's files below, that warp.txt and no pad script
and copies both into this directory's fixtures/ for the record (they name private paths, hold no game data).

Per room (the r103 pattern, tools/d367/README.md "Any room"; inputs are rebuildable, recipe in docs/lanes/route.md):
  st1/<room>.dar/.arc                 compact-room + room_smd.py release (rel-<room>)
  dc/native/<room>/MAINSCENARIO.re4mesh   the release identity / open-failure fallback (pkg-<room>)
  dc/native/<room>/ps2-world.*        the PS2 world package + its textures (ps2rooms lane)
  dc/tex/<k>/<key>.re4tex             the compact room's upload-only textures (tex-<room>)
  dc/movie/<event>.seq                the room's route movies (convert_route_movies.py)
Usage: python3 make-route-fixtures.py
"""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WARP = HERE.parent / 'warp.py'
TOUR = Path('/mnt/c/Game Dev/Emulators/re4-assets-private/world-agent-20260926/continuation-20260927/'
            'playability-r11-r1/tour')
REC = HERE / 'fixtures'
L = Path('/root/probe/lanes/route')
PS2 = Path('/mnt/c/Game Dev/Emulators/re4-assets-private/ps2rooms-20260930/out')
MOVIES = Path('/root/probe/d367-agents/cutscenes/movies-288x192-full')

ROOMS = {  # room -> (PS2 world package dir, route movies)
    'r106': (PS2 / 'r106', ['r106s00']),
}
VIEWS = {  # name -> (warp preset, base fixture, rooms staged)
    'r106-entry': ('r106-entry', 'rel-r103-entry-pw.json', ['r106']),
    'r103-r106-door': ('r103-r106-door', 'rel-r103-entry-pw.json', ['r106']),
}


def new_file(path, text):
    if path.exists():
        if path.read_text() != text:
            sys.exit(f'{path} exists with other content; pick a new name')
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def room_files(room):
    ps2, movies = ROOMS[room]
    rep = {}
    for ext in ('dar', 'arc'):
        rep[f'st1/{room}.{ext}'] = L / f'rel-{room}/st1/{room}.{ext}'
    rep[f'dc/native/{room}/MAINSCENARIO.re4mesh'] = L / f'pkg-{room}/MAINSCENARIO.re4mesh'
    for ext in ('re4mesh', 'r4pw'):
        rep[f'dc/native/{room}/ps2-world.{ext}'] = ps2 / f'ps2-world.{ext}'
    tex = sorted((ps2 / 'tex').glob('*.re4tex')) + sorted((L / f'tex-{room}').glob('*.re4tex'))
    for t in tex:
        rep.setdefault(f'dc/tex/{t.name[0]}/{t.name}', t)
    for m in movies:
        rep[f'dc/movie/{m}.seq'] = MOVIES / m / f'{m}.seq'
    for k, v in rep.items():
        assert v.is_file(), (k, v)
    return rep


REC.mkdir(exist_ok=True)
for name, (preset, base, rooms) in VIEWS.items():
    warp = subprocess.check_output([sys.executable, str(WARP), preset], text=True)
    d = json.loads((TOUR / base).read_text())
    rep = d['replace']
    rep['dc/warp.txt'] = f'route-{name}/warp.txt'
    rep.pop('dc/padscript.txt', None)
    added = 0
    for room in rooms:
        for k, v in room_files(room).items():
            if k.startswith('dc/tex/') and k in rep:
                continue  # an image the base already stages (VQ overlay) keeps its staged form
            rep[k] = str(v)
            added += 1
    fx = json.dumps(d, indent=1) + '\n'
    new_file(TOUR / f'route-{name}' / 'warp.txt', warp)
    new_file(TOUR / f'route-rel-{name}-pw.json', fx)
    (REC / f'route-{name}-warp.txt').write_text(warp)
    (REC / f'route-rel-{name}-pw.json').write_text(fx)
    print(f'tour/route-rel-{name}-pw.json ({len(rep)} entries, {added} added), warp {preset}')
