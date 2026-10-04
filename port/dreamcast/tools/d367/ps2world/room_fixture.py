#!/usr/bin/env python3
"""room_fixture.py: a route-run.sh fixture that enters one brought-up room by the warp rig (README "Add the next room").

    room_fixture.py --room r210 --preset r210-entry --base <fixture.json> --rel <dir> [--aica <dir>]
                    --scenery <dir> --room-tex <dir> [--ps2 <dir> | --no-ps2] [--tex <dir>]... [--file P=SRC]...
                    -o <out dir>/<name>.json

Writes <name>.json and <name>-warp.txt. The fixture is <base> (its padscript, debug config and shared textures)
plus the room's released container (<rel>/stN/rXXX.{arc,dar}; the .dar from <aica> when given, the banked copy
aica_banks.py writes), its scenery package (<scenery>/MAINSCENARIO.re4mesh -> dc/native/rXXX/), its room textures
(<room-tex>/*.re4tex -> dc/tex/<c>/), and with --ps2 the PS2 world package (ps2-world.{re4mesh,r4pw} + tex/).
--no-ps2 leaves dc/native/rXXX/ps2-world.* off the disc (and removes them if <base> stages them): a registry-listed
room whose package is absent must open its own scenery (PS2MESH fallback), which is what that arm tests.
--tex / --file stage what the room's actors need besides the room. St2/St4 Leon is costume 1 (pl08, title.cpp): the
route lane's pl08 set, --file em/pl08.drs=/root/probe/lanes/route/aica-r104/em/pl08.drs --tex
/root/probe/lanes/route/tex-pl08 (the GC pl08.drs, 1,057,792 B, exceeds the 869,728 B player area and halts the
room entry with "native player read REJECTED"). All sources are written as absolute paths; a missing source is an error. A sidecar <name>.json.sources records the
sha256 of every staged room file for the evidence manifest.
"""
import argparse, hashlib, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import warp  # noqa: E402


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def tex_entries(d):
    out = {}
    for t in sorted(Path(d).glob('*.re4tex')):
        out['dc/tex/%s/%s' % (t.name[0], t.name)] = str(t.resolve())
    if not out:
        raise SystemExit('no .re4tex in %s' % d)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--room', required=True, help='rXXX (hex)')
    ap.add_argument('--preset', required=True, help='warp.py preset')
    ap.add_argument('--base', required=True, type=Path)
    ap.add_argument('--rel', required=True, type=Path)
    ap.add_argument('--aica', type=Path)
    ap.add_argument('--scenery', required=True, type=Path)
    ap.add_argument('--room-tex', required=True, type=Path)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--ps2', type=Path)
    g.add_argument('--no-ps2', action='store_true')
    ap.add_argument('--tex', type=Path, action='append', default=[], help='extra .re4tex dir (dc/tex/<c>/)')
    ap.add_argument('--file', action='append', default=[], help='DISC_PATH=SOURCE (extra staged file)')
    ap.add_argument('-o', '--output', required=True, type=Path)
    a = ap.parse_args(argv)
    room = a.room.lower()
    if len(room) != 4 or room[0] != 'r':
        ap.error('--room rXXX')
    st = 'st' + room[1]
    if a.preset not in warp.PRESETS or warp.PRESETS[a.preset]['room'] != int(room[1:], 16):
        ap.error('preset %s is not a %s warp' % (a.preset, room))

    base = json.loads(a.base.read_text())
    rep = {k: str((a.base.parent / v).resolve()) for k, v in base['replace'].items()}
    remove = list(base.get('remove') or [])
    own = {}
    own['%s/%s.arc' % (st, room)] = a.rel / st / (room + '.arc')
    own['%s/%s.dar' % (st, room)] = (a.aica or a.rel) / st / (room + '.dar')
    own['dc/native/%s/MAINSCENARIO.re4mesh' % room] = a.scenery / 'MAINSCENARIO.re4mesh'
    for f in a.file:
        k, _, v = f.partition('=')
        own[k] = Path(v)
    tex = {}
    for d in a.tex:
        tex.update(tex_entries(d))
    tex.update(tex_entries(a.room_tex))
    pw = ['dc/native/%s/ps2-world.re4mesh' % room, 'dc/native/%s/ps2-world.r4pw' % room]
    if a.ps2:
        own[pw[0]] = a.ps2 / 'ps2-world.re4mesh'
        own[pw[1]] = a.ps2 / 'ps2-world.r4pw'
        tex.update(tex_entries(a.ps2 / 'tex'))
    else:
        for k in pw:
            rep.pop(k, None)
            if k not in remove:
                remove.append(k)
    for k, v in own.items():
        if not Path(v).is_file():
            raise SystemExit('missing source %s for %s' % (v, k))
        rep[k] = str(Path(v).resolve())
    shadowed = sorted(k for k in tex if k in rep and rep[k] != tex[k])
    rep.update(tex)

    a.output.parent.mkdir(parents=True, exist_ok=True)
    w = a.output.with_name(a.output.stem + '-warp.txt')
    w.write_text(warp.lines_for(dict(warp.PRESETS[a.preset]), door=False, dump=False, name=a.preset))
    rep['dc/warp.txt'] = str(w.resolve())
    a.output.write_text(json.dumps(dict(base, replace=rep, remove=remove), indent=1) + '\n')
    src = dict(room=room, preset=a.preset, base=str(a.base.resolve()), ps2=bool(a.ps2), shadowed_base_tex=shadowed,
               files={k: dict(src=str(Path(v).resolve()), sha256=sha(v)) for k, v in sorted(own.items())},
               tex_count=len(tex), tex_sha256=hashlib.sha256(''.join(
                   '%s %s\n' % (k, sha(v)) for k, v in sorted(tex.items())).encode()).hexdigest(),
               removed=[k for k in pw if not a.ps2])
    Path(str(a.output) + '.sources').write_text(json.dumps(src, indent=1) + '\n')
    print(a.output, len(rep), 'replaced', len(remove), 'removed', len(tex), 'room textures',
          len(shadowed), 'base textures shadowed')
    return 0


if __name__ == '__main__':
    sys.exit(main())
