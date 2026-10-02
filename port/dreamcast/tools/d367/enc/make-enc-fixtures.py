"""Lane enc fixtures (2026-09-30): tour fixtures for crowd views the r21k tour does not have.

Writes into the playability harness tour dir (new files only, never over an existing file):
  tour/enc-r101-bell-fight/warp.txt        tools/d367/warp.py r101-bell-fight (square fight about to start)
  tour/enc-rel-r101-bell-fight-pw.json     tour/rel-r101-entry-pw.json (the play staging: PS2 worlds, texture VQ,
                                           release r100) with that warp.txt and the shared tour padscript.txt
and copies both into this directory's fixtures/ for the record (they name private paths, hold no game data).
Usage: python3 make-enc-fixtures.py
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WARP = HERE.parent / 'warp.py'
TOUR = Path('/mnt/c/Game Dev/Emulators/re4-assets-private/world-agent-20260926/continuation-20260927/'
            'playability-r11-r1/tour')
REC = HERE / 'fixtures'

VIEWS = {  # name -> (warp preset, base fixture, padscript relative to tour/)
    'r101-bell-fight': ('r101-bell-fight', 'rel-r101-entry-pw.json', 'padscript.txt'),
}


def new_file(path, text):
    if path.exists():
        if path.read_text() != text:
            sys.exit(f'{path} exists with other content; pick a new name')
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


REC.mkdir(exist_ok=True)
for name, (preset, base, pad) in VIEWS.items():
    warp = subprocess.check_output([sys.executable, str(WARP), preset], text=True)
    d = json.loads((TOUR / base).read_text())
    rep = d['replace']
    rep['dc/warp.txt'] = f'enc-{name}/warp.txt'
    rep['dc/padscript.txt'] = pad
    assert (TOUR / pad).is_file()
    fx = json.dumps(d, indent=1) + '\n'
    new_file(TOUR / f'enc-{name}' / 'warp.txt', warp)
    new_file(TOUR / f'enc-rel-{name}-pw.json', fx)
    (REC / f'enc-{name}-warp.txt').write_text(warp)
    (REC / f'enc-rel-{name}-pw.json').write_text(fx)
    print(f'tour/enc-rel-{name}-pw.json ({len(rep)} entries), warp {preset}')
# Record the existing tour warps/padscripts the census uses (read-only copies).
for p in ['padscript.txt'] + [f'{v}/warp.txt' for v in ('r100-s20', 'r100-post-radio', 'r100-bridge', 'r100-east-door',
          'r101-entry', 'r101-post-bell-door', 'r103-entry')] + ['r101-entry/padscript.txt', 'r101-post-bell-door/padscript.txt']:
    shutil.copyfile(TOUR / p, REC / ('tour-' + p.replace('/', '-')))
