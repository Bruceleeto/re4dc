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

# AICA banks (aica_banks.py build --route title,r100,r101,r103,<rooms> --fixed-route title,r100,r101,r103):
# the room's own sound banks converted into the disc's frozen AICA layout (r100-r103 banks unchanged).
AICA = {'r106': L / 'aica-r106', 'r104': L / 'aica-r104'}  # per room, each against the same frozen layout
ROOMS = {  # room -> (PS2 world package dir, route movies, banks only this room uses)
    # r106: the PS2-pattern bake (--color-light ps2, room TEV x4; ps2rooms 2026-10-01, cost-neutral vs the
    # authored package: 44.8 vs 44.9 hw ms at the r106 entry).
    'r106': (PS2 / 'r106-ps2', ['r106s00'], ['em/em29.drs', 'em/em2e.drs']),
    # r104 (2026-10-01): ps2rooms --color-light ps2 bake; em13 (chapter 1-2 Ganados, not on the kite disc) with its
    # bank prebuilt (its EM0 equals em12's). Movies: none yet (s00 needs the QTE path; s10/s20 follow it).
    'r104': (PS2 / 'r104-ps2', [], ['em/em13.drs']),
}
# Texture sets a view stages by naming the key in its rooms list (first dir wins):
#   chapNN  the chapter-results pictures of SS/eng/chapNN.dat (prepare_native_ui.py over the GC original, then
#           vq_native_ui.py with the run's load log); r106's s00 event ends chapter 1-1 on this screen.
#   em2a    em/em2a.drs (prepare_native_ui.py /root/re4data, manifest em/em2a.drs): 8fb0fccf, which r106 loads
#           and r100-r103 never did (the kite disc stages no em2a pictures).
TEXSETS = {'chap01': [L / 'tex-chap01-vq', L / 'tex-chap01'], 'em2a': [L / 'tex-em2a'], 'em13': [L / 'tex-em13'], 'pl08': [L / 'tex-pl08']}
# Files a set stages besides its pictures. pl08: Leon without the jacket (costume 1 after r106; title.cpp),
# prepare_enemy_motions.py textures-only (869,728 B resident: needs PLAYER_RESIDENT_BYTES=869728), with its
# prebuilt PL bank (identical to pl00's, resident in aica_banks.py).
SET_FILES = {'pl08': {'em/pl08.drs': AICA['r104'] / 'em/pl08.drs'},
             # r104mov: r104's route movies; s00c is the QTE cut alone (played after a skip).
             'r104mov': {f'dc/movie/{m}.seq': MOVIES / m / f'{m}.seq'
                         for m in ('r104s00', 'r104s00c', 'r104s01', 'r104s02', 'r104s10', 'r104s20')}}
# Pad scripts a view stages by naming 'pad-<key>' in its rooms list (dc/padscript.txt, retrace clock). qte-*: the
# r104 s00 QTE press, 20 frames into the cut (route_movie_bridge.cpp reports fixture state qte=1 while it runs);
# ActBtn flags 0x42 fail a press of both pairs, so each run presses one (r104 picks A+B or L+R by Rnd).
PADSCRIPTS = {'qte-ab': '0 0000 1 qte=1 200000\n+20 0300 8\n', 'qte-lr': '0 0000 1 qte=1 200000\n+20 0060 8\n',
              'none': '',
              # chapter-a: A every 2 s from 90 s (the r106 closet results screen draws at ~94 s): Next Chapter, the
              # Save? prompt and the save screens, into chapter 1-2. A alone neither skips a movie nor fails the QTE.
              'chapter-a': '5400 0100 6\n' + '+120 0100 6\n' * 40}
VIEWS = {  # name -> (warp preset, base fixture, rooms staged, warp.py options)
    # *-snd (2026-10-01): + the r106 AICA banks (room .dar, em29, em2e); *-ps2 had GC banks (no room sound).
    'r106-entry-snd': ('r106-entry', 'rel-r103-entry-pw.json', ['r106'], []),
    # r103-r106-door (2026-10-01, single-use name) was written without --door: Leon stood at the door.
    # *-ps2 (2026-10-01): the r106 bake; the earlier names staged the authored r106 package.
    'r103-r106-walk-snd': ('r103-r106-door', 'rel-r103-entry-pw.json', ['r106'], ['--door']),
    'r106-closet-snd': ('r106-closet', 'rel-r103-entry-pw.json', ['r106'], ['--door']),
    # *-snd2: + the chapter 1-1 results pictures (r106-closet-snd showed the screen without them).
    'r106-closet-snd2': ('r106-closet', 'rel-r103-entry-pw.json', ['r106', 'chap01'], ['--door']),
    # *-snd3: no pad script (the snd2 run's B+Up from the kite script turned the save screen into "Exit?").
    'r106-closet-snd3': ('r106-closet', 'rel-r103-entry-pw.json', ['r106', 'chap01'], ['--door']),
    # *-snd4 / r106-entry-snd4 / r103-r106-walk-snd4: + em2a; the r106 play set from here on.
    'r106-closet-snd4': ('r106-closet', 'rel-r103-entry-pw.json', ['r106', 'chap01', 'em2a'], ['--door']),
    'r106-entry-snd4': ('r106-entry', 'rel-r103-entry-pw.json', ['r106', 'chap01', 'em2a'], []),
    'r103-r106-walk-snd4': ('r103-r106-door', 'rel-r103-entry-pw.json', ['r106', 'chap01', 'em2a'], ['--door']),
    # r104 bring-up (arrival event skipped by its own room flag); em13 pictures: prepare_native_ui.py over the GC
    # em/em13.drs (iso-src-r104, manifest em/em13.drs; 87 images).
    'r104-noevt-a': ('r104-entry-noevt', 'rel-r103-entry-pw.json', ['r104', 'em13'], []),
    # *-b: + pl08 (the r104-noevt-a run halted reading pl08.drs: 1,057,792 B > the 846,656 B player area).
    'r104-noevt-b': ('r104-entry-noevt', 'rel-r103-entry-pw.json', ['r104', 'em13', 'pl08'], []),
    # r104 arrival with the movies: s00 to picture 4795, the QTE cut as game frames over the movie, s01 or s02.
    'r104-qte-ab': ('r104-arrival', 'rel-r103-entry-pw.json', ['r104', 'em13', 'pl08', 'r104mov', 'pad-qte-ab'], []),
    'r104-qte-lr': ('r104-arrival', 'rel-r103-entry-pw.json', ['r104', 'em13', 'pl08', 'r104mov', 'pad-qte-lr'], []),
    # *-none: no press (the miss branch; 5 s shots catch the 2 s QTE window for the prompt over the movie).
    # r106 closet -> chapter 1-1 end -> chapter 1-2 (r104 s00): the play path into r104, every set staged.
    'r106-r104-chapter': ('r106-closet', 'rel-r103-entry-pw.json',
                          ['r106', 'chap01', 'em2a', 'r104', 'em13', 'pl08', 'r104mov', 'pad-chapter-a'], ['--door']),
    'r104-qte-none': ('r104-arrival', 'rel-r103-entry-pw.json', ['r104', 'em13', 'pl08', 'r104mov', 'pad-none'], []),
}
# The kite base disc carries its own dc/padscript.txt (58 entries, source clock): dropping it from 'replace' left
# it running in these views (written before 2026-10-01 evening, kept as recorded). Later views remove it.
KITE_PADSCRIPT = {'r106-entry-snd', 'r103-r106-walk-snd', 'r106-closet-snd', 'r106-closet-snd2'}


def new_file(path, text):
    if path.exists():
        if path.read_text() != text:
            sys.exit(f'{path} exists with other content; pick a new name')
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def room_files(room):
    if room in SET_FILES and room not in TEXSETS:
        return dict(SET_FILES[room])
    if room in TEXSETS:
        rep = {}
        for t in [t for d in TEXSETS[room] for t in sorted(d.glob('*.re4tex'))]:
            rep.setdefault(f'dc/tex/{t.name[0]}/{t.name}', t)
        rep.update(SET_FILES.get(room, {}))
        return rep
    ps2, movies, banks = ROOMS[room]
    rep = {}
    rep[f'st1/{room}.dar'] = AICA[room] / f'st1/{room}.dar'
    rep[f'st1/{room}.arc'] = L / f'rel-{room}/st1/{room}.arc'
    for b in banks:
        rep[b] = AICA[room] / b
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
for name, (preset, base, rooms, opts) in VIEWS.items():
    warp = subprocess.check_output([sys.executable, str(WARP), preset] + opts, text=True)
    d = json.loads((TOUR / base).read_text())
    rep = d['replace']
    rep['dc/warp.txt'] = f'route-{name}/warp.txt'
    rep.pop('dc/padscript.txt', None)
    pads = [r[4:] for r in rooms if r.startswith('pad-')]
    if pads:  # an empty script still replaces the kite base disc's
        new_file(TOUR / f'route-{name}' / 'padscript.txt', PADSCRIPTS[pads[0]])
        rep['dc/padscript.txt'] = f'route-{name}/padscript.txt'
        (REC / f'route-{name}-padscript.txt').write_text(PADSCRIPTS[pads[0]])
    elif name not in KITE_PADSCRIPT:
        d['remove'] = sorted(set(d.get('remove', [])) | {'dc/padscript.txt'})
    added = 0
    for room in [r for r in rooms if not r.startswith('pad-')]:
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
