#!/usr/bin/env python3
"""Dump a GameCube room's LIT cut (env + lights) as JSON, read straight from the GC debug disc. Same fields and
layout as world-agent ps2-rooms-20260929/tools/gc_lit_dump.py (which reads orig/G4BE08/rooms/<room>/<room>.das,
present only for a few rooms): ambient_scr, fog, contrast, lights_cut. ps2_room_r4im.py reads the output as
<inputs>/<room>/gc-lit-cut0.json for NORMAL groups and for --color-light gc.

usage: gc_room_lit.py <room> <out.json> [--cut 0] [--iso PATH]   (WSL)
"""
import argparse, json, struct, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import room_smd  # noqa: E402
from assetpipe.rooms import GcIso  # noqa: E402

DEFAULT_ISO = "/root/work/re4-dreamcast/orig/G4BE08/re4_debug_disc1.iso"


def dump(LIT, room, cut):
    be32 = lambda o: struct.unpack_from(">I", LIT, o)[0]
    fB = lambda o: struct.unpack_from(">f", LIT, o)[0]
    cutnum = struct.unpack_from(">H", LIT, 0)[0]
    o = struct.unpack_from(">%dI" % cutnum, LIT, 4)[cut]
    env = dict(ambient_scr=list(LIT[o:o + 3]), fog_type=struct.unpack_from(">i", LIT, o + 8)[0], fog_start=fB(o + 12),
               fog_end=fB(o + 16), fog_rgba=LIT[o + 0x14:o + 0x18].hex(),
               contrast=list(struct.unpack_from(">3b", LIT, o + 0xF5)))
    lights = []
    for j in range(be32(o + 4)):
        w = o + 0x104 + 0x12C * j
        be, xD, ty, xF = LIT[w:w + 4]
        lights.append(dict(i=j, be=be, xD=xD, type=ty, xF=xF, pos=list(struct.unpack_from(">3f", LIT, w + 4)),
                           R=fB(w + 0x10), col=list(LIT[w + 0x14:w + 0x18]), intensity=fB(w + 0x18),
                           n=list(struct.unpack_from(">3f", LIT, w + 0x2C)), A0=fB(w + 0x38), A1=fB(w + 0x3C)))
    return dict(room=room, cut=cut, cuts=cutnum, env=env, lights_cut=lights)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('room')
    ap.add_argument('out', type=Path)
    ap.add_argument('--cut', type=int, default=0)
    ap.add_argument('--iso', default=DEFAULT_ISO)
    a = ap.parse_args()
    iso = GcIso(a.iso)
    rel = dict(iso.rooms()).get(a.room)
    if rel is None:
        raise SystemExit('%s not on the GC disc' % a.room)
    data = room_smd.decode_das(iso.read(rel))
    e = room_smd.archive_endian(data)
    LIT = [data[s:t] for tag, s, t in room_smd.tagged_entries(data, e) if tag == b"LIT\0"][0]
    d = dump(LIT, a.room, a.cut)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(d, indent=1))
    print(json.dumps(d['env']))
    for l in d['lights_cut']:
        print(l['i'], 'be', l['be'], 'xD', l['xD'], 'type', l['type'], 'col', l['col'], 'I', round(l['intensity'], 3),
              'pos', [round(x) for x in l['pos']], 'n', [round(x, 3) for x in l['n']], 'R', round(l['R']),
              'A0', round(l['A0'], 3), 'A1', round(l['A1'], 3))


if __name__ == '__main__':
    main()
